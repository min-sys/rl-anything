"""スキルライフサイクル triage エンジン。

テレメトリ + trigger eval 結果を統合し、各スキルに対して
CREATE / UPDATE / SPLIT / MERGE / OK の5択アクション判定を行う。
LLM 不使用。
"""
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from similarity import jaccard_coefficient, tokenize
from skill_triggers import extract_skill_triggers, normalize_skill_name
from trigger_eval_generator import (
    EVAL_SETS_DIR,
    MIN_EVAL_QUERIES,
    generate_eval_set,
)

# ── discover の MISSED_SKILL_THRESHOLD を参照 ────────
MISSED_SKILL_THRESHOLD = 2

# ── confidence 計算定数（D10）────────────────────────

BASE_CONFIDENCE = {
    "CREATE": 0.70,
    "UPDATE": 0.65,
    "SPLIT": 0.60,
    "MERGE": 0.55,
}
SESSION_BONUS_RATE = 0.05
EVIDENCE_BONUS_RATE = 0.03
MAX_SESSION_BONUS = 0.25
MAX_EVIDENCE_BONUS = 0.10

# ── SPLIT / MERGE 定数 ──────────────────────────────

SPLIT_CATEGORY_THRESHOLD = 3
CLUSTER_DISTANCE_THRESHOLD = 0.70
MERGE_OVERLAP_THRESHOLD = 0.40


def compute_confidence(
    action: str,
    session_count: int = 0,
    near_miss_count: int = 0,
) -> float:
    """D10 計算式に基づく confidence スコアを算出する。"""
    base = BASE_CONFIDENCE.get(action, 0.50)
    session_bonus = min(
        MAX_SESSION_BONUS,
        max(0, (session_count - MISSED_SKILL_THRESHOLD) * SESSION_BONUS_RATE),
    )
    evidence_bonus = 0.0
    if action == "UPDATE":
        evidence_bonus = min(MAX_EVIDENCE_BONUS, near_miss_count * EVIDENCE_BONUS_RATE)
    return min(1.0, base + session_bonus + evidence_bonus)


def triage_skill(
    skill_name: str,
    *,
    sessions: List[Dict[str, Any]],
    usage: List[Dict[str, Any]],
    missed_skills: List[Dict[str, Any]],
    existing_skills: Set[str],
    skill_triggers_list: Optional[List[Dict[str, Any]]] = None,
    project_root: Optional[Path] = None,
    all_eval_sets: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """単一スキルの triage 判定を行う。

    Args:
        skill_name: 対象スキル名
        sessions: sessions.jsonl レコード
        usage: usage.jsonl レコード
        missed_skills: discover の missed_skill 結果
        existing_skills: 既存スキル名の集合
        skill_triggers_list: スキルトリガー情報
        project_root: プロジェクトルート
        all_eval_sets: 事前生成済み eval set。None の場合は内部で生成。

    Returns:
        {"action": str, "skill": str, "confidence": float, "evidence": dict, ...}
    """
    # missed_skill 情報取得
    missed_info = _find_missed_info(skill_name, missed_skills)
    missed_session_count = missed_info.get("session_count", 0) if missed_info else 0

    # eval set 取得/生成
    eval_result = None
    if all_eval_sets and skill_name in all_eval_sets:
        eval_result = all_eval_sets[skill_name]
    elif skill_triggers_list:
        eval_result = generate_eval_set(
            skill_name,
            sessions=sessions,
            usage=usage,
            skill_triggers_list=skill_triggers_list,
            project_root=project_root,
            save=False,
        )

    # near-miss カウント
    near_miss_count = 0
    if eval_result and not eval_result.get("skipped"):
        near_miss_count = sum(
            1 for e in eval_result.get("eval_set", [])
            if not e.get("should_trigger", True)
        )

    eval_set_path = eval_result.get("eval_set_path") if eval_result else None

    # CREATE 判定: missed_skill 高 + 既存スキルなし
    if missed_info and missed_session_count >= MISSED_SKILL_THRESHOLD and skill_name not in existing_skills:
        confidence = compute_confidence("CREATE", session_count=missed_session_count)
        return {
            "action": "CREATE",
            "skill": skill_name,
            "confidence": round(confidence, 2),
            "evidence": {
                "missed_sessions": missed_session_count,
                "triggers_matched": missed_info.get("triggers_matched", []),
            },
            "eval_set_path": eval_set_path,
        }

    # UPDATE 判定: missed_skill 高 + 既存スキルあり + near-miss
    if missed_info and missed_session_count >= MISSED_SKILL_THRESHOLD and skill_name in existing_skills:
        confidence = compute_confidence(
            "UPDATE",
            session_count=missed_session_count,
            near_miss_count=near_miss_count,
        )
        return {
            "action": "UPDATE",
            "skill": skill_name,
            "confidence": round(confidence, 2),
            "evidence": {
                "missed_sessions": missed_session_count,
                "near_miss_count": near_miss_count,
            },
            "suggestion": "description の trigger 精度を改善",
            "eval_set_path": eval_set_path,
        }

    # OK 判定（missed 未検出スキル）
    return {
        "action": "OK",
        "skill": skill_name,
        "confidence": 0.90,
        "eval_set_path": eval_set_path,
    }


def detect_split_candidates(
    skill_name: str,
    eval_set: List[Dict[str, Any]],
    skill_triggers_list: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """SPLIT 判定: should_trigger クエリのカテゴリ分散を検出する。

    トリガーワードでグループ化し、Jaccard 距離で階層クラスタリング。
    SPLIT_CATEGORY_THRESHOLD 以上のクラスタに分散している場合に提案する。
    """
    should_trigger_queries = [
        e["query"] for e in eval_set if e.get("should_trigger", False)
    ]
    if len(should_trigger_queries) < SPLIT_CATEGORY_THRESHOLD:
        return None

    # 各スキルのトリガーワードを全て収集
    all_triggers: List[str] = []
    for entry in skill_triggers_list:
        all_triggers.extend(entry.get("triggers", []))
    all_triggers = list(set(all_triggers))

    if not all_triggers:
        return None

    # 各クエリのトリガーワードセットを取得
    query_trigger_sets: List[Tuple[str, Set[str]]] = []
    for query in should_trigger_queries:
        matched = set()
        q_lower = query.lower()
        for trigger in all_triggers:
            if trigger.lower() in q_lower:
                matched.add(trigger.lower())
        if matched:
            query_trigger_sets.append((query, matched))

    if len(query_trigger_sets) < SPLIT_CATEGORY_THRESHOLD:
        return None

    # 階層クラスタリング（アグロメレーション）
    clusters = _agglomerative_cluster(query_trigger_sets)

    if len(clusters) < SPLIT_CATEGORY_THRESHOLD:
        return None

    # クラスタラベル生成
    category_labels = []
    for cluster in clusters:
        # クラスタ内の共通トリガーワードをラベルに使用
        if cluster:
            common = cluster[0][1].copy()
            for _, trigger_set in cluster[1:]:
                common &= trigger_set
            label = sorted(common)[0] if common else sorted(cluster[0][1])[0]
            category_labels.append(label)

    session_count = len(should_trigger_queries)
    confidence = compute_confidence("SPLIT", session_count=session_count)

    return {
        "action": "SPLIT",
        "skill": skill_name,
        "confidence": round(confidence, 2),
        "evidence": {
            "categories": category_labels,
            "cluster_count": len(clusters),
            "source": "triage",
        },
    }


def _agglomerative_cluster(
    items: List[Tuple[str, Set[str]]],
) -> List[List[Tuple[str, Set[str]]]]:
    """単純な凝集型クラスタリング。

    Jaccard 距離が CLUSTER_DISTANCE_THRESHOLD 未満のペアをマージする。
    """
    # 各アイテムを1要素クラスタとして開始
    clusters: List[List[Tuple[str, Set[str]]]] = [[item] for item in items]

    while True:
        best_sim = 0.0
        best_pair = (-1, -1)

        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                # 平均リンケージ
                sim = _cluster_similarity(clusters[i], clusters[j])
                if sim > best_sim:
                    best_sim = sim
                    best_pair = (i, j)

        # Jaccard 距離 = 1 - 類似度。距離 < threshold → 類似度 > 1 - threshold
        if best_sim < (1.0 - CLUSTER_DISTANCE_THRESHOLD):
            break

        i, j = best_pair
        clusters[i] = clusters[i] + clusters[j]
        clusters.pop(j)

        if len(clusters) <= 1:
            break

    return clusters


def _cluster_similarity(
    cluster_a: List[Tuple[str, Set[str]]],
    cluster_b: List[Tuple[str, Set[str]]],
) -> float:
    """2クラスタ間の平均 Jaccard 類似度を計算する。"""
    total = 0.0
    count = 0
    for _, set_a in cluster_a:
        for _, set_b in cluster_b:
            total += jaccard_coefficient(set_a, set_b)
            count += 1
    return total / count if count > 0 else 0.0


def detect_merge_candidates(
    eval_sets: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """MERGE 判定: 2スキル間の should_trigger クエリの Jaccard 類似度を検出する。

    MERGE_OVERLAP_THRESHOLD 以上の類似度のペアを返す。
    """
    results: List[Dict[str, Any]] = []
    skills_with_queries: Dict[str, Set[str]] = {}

    for skill, eval_result in eval_sets.items():
        if eval_result.get("skipped"):
            continue
        queries = set()
        for e in eval_result.get("eval_set", []):
            if e.get("should_trigger", False):
                queries.add(e["query"].lower().strip())
        if queries:
            skills_with_queries[skill] = queries

    skill_names = list(skills_with_queries.keys())
    for i in range(len(skill_names)):
        for j in range(i + 1, len(skill_names)):
            name_a = skill_names[i]
            name_b = skill_names[j]
            overlap = jaccard_coefficient(
                skills_with_queries[name_a],
                skills_with_queries[name_b],
            )
            if overlap >= MERGE_OVERLAP_THRESHOLD:
                session_count = len(skills_with_queries[name_a]) + len(skills_with_queries[name_b])
                confidence = compute_confidence("MERGE", session_count=session_count)
                results.append({
                    "action": "MERGE",
                    "skills": sorted([name_a, name_b]),
                    "skill": "",
                    "confidence": round(confidence, 2),
                    "evidence": {
                        "overlap_ratio": round(overlap, 4),
                        "source": "triage",
                    },
                })

    return results


def triage_all_skills(
    *,
    sessions: List[Dict[str, Any]],
    usage: List[Dict[str, Any]],
    missed_skills: List[Dict[str, Any]],
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """全スキルに対して triage を実行する。

    Returns:
        {
            "CREATE": [...], "UPDATE": [...], "SPLIT": [...],
            "MERGE": [...], "OK": [...],
            "skipped": bool, "reason": str or None,
        }
    """
    skill_triggers_list = extract_skill_triggers(project_root=project_root)
    if not skill_triggers_list:
        return _empty_result(reason="no_skills_found")

    existing_skills = {entry["skill"] for entry in skill_triggers_list}

    # missed_skills から存在しないスキル名も追加
    all_skill_names = set(existing_skills)
    for ms in missed_skills:
        all_skill_names.add(ms.get("skill", ""))
    all_skill_names.discard("")

    # eval set 一括生成
    all_eval_sets = {}
    for entry in skill_triggers_list:
        skill = entry["skill"]
        all_eval_sets[skill] = generate_eval_set(
            skill,
            sessions=sessions,
            usage=usage,
            skill_triggers_list=skill_triggers_list,
            project_root=project_root,
            save=True,
        )

    # 各スキルの基本 triage
    result: Dict[str, List[Dict[str, Any]]] = {
        "CREATE": [],
        "UPDATE": [],
        "SPLIT": [],
        "MERGE": [],
        "OK": [],
    }

    for skill_name in sorted(all_skill_names):
        triage = triage_skill(
            skill_name,
            sessions=sessions,
            usage=usage,
            missed_skills=missed_skills,
            existing_skills=existing_skills,
            skill_triggers_list=skill_triggers_list,
            project_root=project_root,
            all_eval_sets=all_eval_sets,
        )
        action = triage.get("action", "OK")
        result[action].append(triage)

    # SPLIT 検出（既存スキルのみ）
    for skill_name, eval_result in all_eval_sets.items():
        if eval_result.get("skipped"):
            continue
        split = detect_split_candidates(
            skill_name,
            eval_result.get("eval_set", []),
            skill_triggers_list,
        )
        if split:
            # OK にいた場合は OK から除去して SPLIT に移動
            result["OK"] = [r for r in result["OK"] if r.get("skill") != skill_name]
            result["SPLIT"].append(split)

    # MERGE 検出
    merge_candidates = detect_merge_candidates(all_eval_sets)
    result["MERGE"].extend(merge_candidates)

    result["skipped"] = False
    result["reason"] = None

    return result


def generate_skill_creator_suggestion(
    triage_result: Dict[str, Any],
) -> Dict[str, Any]:
    """UPDATE 判定時の skill-creator 連携提案を生成する。"""
    skill = triage_result.get("skill", "")
    eval_set_path = triage_result.get("eval_set_path", "")

    return {
        "skill": skill,
        "eval_set_path": eval_set_path,
        "command_example": f"/skill-creator で {skill} の description を最適化",
        "estimated_trigger_accuracy": _estimate_accuracy(triage_result),
    }


def _estimate_accuracy(triage_result: Dict[str, Any]) -> str:
    """テレメトリベースの推定 trigger 精度。"""
    evidence = triage_result.get("evidence", {})
    missed = evidence.get("missed_sessions", 0)
    near_miss = evidence.get("near_miss_count", 0)
    if missed > 5 or near_miss > 3:
        return "low"
    if missed > 2 or near_miss > 1:
        return "medium"
    return "high"


def _find_missed_info(
    skill_name: str,
    missed_skills: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """missed_skills リストから該当スキルを検索する。"""
    for ms in missed_skills:
        if ms.get("skill") == skill_name:
            return ms
    return None


def _empty_result(reason: str = "") -> Dict[str, Any]:
    """空の triage 結果を返す。"""
    return {
        "CREATE": [],
        "UPDATE": [],
        "SPLIT": [],
        "MERGE": [],
        "OK": [],
        "skipped": True,
        "reason": reason,
    }
