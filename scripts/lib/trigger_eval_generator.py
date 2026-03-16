"""テレメトリデータから skill-creator 互換の trigger eval set を自動生成する。

sessions.jsonl の user_prompts + usage.jsonl のスキル使用実績を組み合わせて、
各スキルの should_trigger / should_not_trigger クエリセットを生成する。
"""
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from skill_triggers import extract_skill_triggers, normalize_skill_name

# ── 定数 ──────────────────────────────────────────────

MIN_EVAL_QUERIES = 3
TARGET_EVAL_QUERIES = 10
NEAR_MISS_CONFIDENCE_WEIGHT = 1.0
UNRELATED_CONFIDENCE_WEIGHT = 0.6
EVAL_SETS_DIR = Path.home() / ".claude" / "rl-anything" / "eval-sets"


def generate_eval_set(
    skill_name: str,
    *,
    sessions: List[Dict[str, Any]],
    usage: List[Dict[str, Any]],
    skill_triggers_list: Optional[List[Dict[str, Any]]] = None,
    project_root: Optional[Path] = None,
    save: bool = True,
) -> Dict[str, Any]:
    """スキルの trigger eval set を生成する。

    Args:
        skill_name: 対象スキル名（正規化済み）
        sessions: sessions.jsonl のレコードリスト
        usage: usage.jsonl のレコードリスト
        skill_triggers_list: スキルトリガー情報。None の場合は CLAUDE.md から取得。
        project_root: プロジェクトルート。
        save: True の場合、ファイルに保存する。

    Returns:
        {
            "skill": str,
            "eval_set": [{"query": str, "should_trigger": bool}, ...],
            "eval_set_path": str or None,
            "skipped": bool,
            "reason": str or None,
            "stats": {"should_trigger": int, "should_not_trigger": int},
        }
    """
    if skill_triggers_list is None:
        skill_triggers_list = extract_skill_triggers(project_root=project_root)

    # 対象スキルのトリガーワードを取得
    triggers = _get_triggers_for_skill(skill_name, skill_triggers_list)
    if not triggers:
        return _skipped_result(skill_name, "no_triggers", 0)

    # session_id → 使用スキル集合
    used_skills_by_session = _build_used_skills_map(usage)

    # should_trigger クエリ抽出
    should_trigger = _extract_should_trigger(
        skill_name, triggers, sessions, used_skills_by_session,
    )

    # should_not_trigger クエリ抽出
    should_not_trigger = _extract_should_not_trigger(
        skill_name, triggers, sessions, used_skills_by_session,
    )

    # 最小データ要件チェック
    if len(should_trigger) < MIN_EVAL_QUERIES:
        return _skipped_result(skill_name, "insufficient_data", len(should_trigger))
    if len(should_not_trigger) < MIN_EVAL_QUERIES:
        return _skipped_result(skill_name, "insufficient_data", len(should_not_trigger))

    # バランス調整
    should_trigger = _balance_queries(should_trigger, TARGET_EVAL_QUERIES)
    should_not_trigger = _balance_should_not_trigger(should_not_trigger, TARGET_EVAL_QUERIES)

    # eval set 構築（skill-creator 互換フォーマット）
    eval_set = []
    for q in should_trigger:
        eval_set.append({"query": q, "should_trigger": True})
    for entry in should_not_trigger:
        query = entry["query"] if isinstance(entry, dict) else entry
        eval_set.append({"query": query, "should_trigger": False})

    # ファイル出力
    eval_set_path = None
    if save:
        eval_set_path = _save_eval_set(skill_name, eval_set)

    return {
        "skill": skill_name,
        "eval_set": eval_set,
        "eval_set_path": str(eval_set_path) if eval_set_path else None,
        "skipped": False,
        "reason": None,
        "stats": {
            "should_trigger": len(should_trigger),
            "should_not_trigger": len(should_not_trigger),
        },
    }


def generate_all_eval_sets(
    *,
    sessions: List[Dict[str, Any]],
    usage: List[Dict[str, Any]],
    project_root: Optional[Path] = None,
    save: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """全スキルの eval set を一括生成する。

    Returns:
        {skill_name: generate_eval_set() の結果, ...}
    """
    skill_triggers_list = extract_skill_triggers(project_root=project_root)
    results: Dict[str, Dict[str, Any]] = {}
    for entry in skill_triggers_list:
        skill = entry["skill"]
        results[skill] = generate_eval_set(
            skill,
            sessions=sessions,
            usage=usage,
            skill_triggers_list=skill_triggers_list,
            project_root=project_root,
            save=save,
        )
    return results


# ── 内部関数 ──────────────────────────────────────────


def _get_triggers_for_skill(
    skill_name: str,
    skill_triggers_list: List[Dict[str, Any]],
) -> List[str]:
    """スキルのトリガーワードを取得する。"""
    for entry in skill_triggers_list:
        if entry["skill"] == skill_name:
            return entry.get("triggers", [])
    return []


def _build_used_skills_map(
    usage: List[Dict[str, Any]],
) -> Dict[str, Set[str]]:
    """session_id → 使用スキル名の集合を構築する。"""
    result: Dict[str, Set[str]] = defaultdict(set)
    for rec in usage:
        sid = rec.get("session_id", "")
        skill = rec.get("skill_name", "")
        if sid and skill:
            result[sid].add(normalize_skill_name(skill))
    return result


def _match_trigger_score(
    text: str,
    triggers: List[str],
) -> int:
    """テキストに含まれるトリガーワードの数を返す。"""
    text_lower = text.lower()
    return sum(1 for t in triggers if t.lower() in text_lower)


def _select_best_prompt(
    prompts: List[str],
    triggers: List[str],
) -> str:
    """マルチプロンプトから最もトリガーワードにマッチするものを選択する。

    一致度が同じ場合は先頭のプロンプトを優先（フォールバック）。
    """
    if not prompts:
        return ""
    if len(prompts) == 1:
        return prompts[0]

    best_prompt = prompts[0]
    best_score = _match_trigger_score(prompts[0], triggers)

    for prompt in prompts[1:]:
        score = _match_trigger_score(prompt, triggers)
        if score > best_score:
            best_score = score
            best_prompt = prompt

    return best_prompt


def _extract_should_trigger(
    skill_name: str,
    triggers: List[str],
    sessions: List[Dict[str, Any]],
    used_skills_by_session: Dict[str, Set[str]],
) -> List[str]:
    """should_trigger クエリを抽出する。

    対象スキルが実際に使用されたセッションの user_prompts から、
    トリガーワードとの一致度が最も高いプロンプトを選択する。
    """
    queries: List[str] = []
    seen: Set[str] = set()

    for session in sessions:
        sid = session.get("session_id", "")
        if not sid:
            continue

        used_in_session = used_skills_by_session.get(sid, set())
        if skill_name not in used_in_session:
            continue

        prompts = session.get("user_prompts", [])
        if not prompts:
            continue

        best = _select_best_prompt(prompts, triggers)
        if best and best not in seen:
            queries.append(best)
            seen.add(best)

    return queries


def _extract_should_not_trigger(
    skill_name: str,
    triggers: List[str],
    sessions: List[Dict[str, Any]],
    used_skills_by_session: Dict[str, Set[str]],
) -> List[Dict[str, Any]]:
    """should_not_trigger クエリを抽出する。

    2ソース:
    1. Near-miss (confidence_weight: 1.0): トリガーワードにマッチするが別スキルが使用された
    2. Unrelated (confidence_weight: 0.6): トリガーワードにマッチするがスキル未使用

    near-miss を優先的に採用する。
    """
    near_miss: List[Dict[str, Any]] = []
    unrelated: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for session in sessions:
        sid = session.get("session_id", "")
        prompts = session.get("user_prompts", [])
        if not sid or not prompts:
            continue

        used_in_session = used_skills_by_session.get(sid, set())
        if skill_name in used_in_session:
            continue

        # トリガーワードにマッチするプロンプトを探す
        for prompt in prompts:
            if _match_trigger_score(prompt, triggers) == 0:
                continue
            if prompt in seen:
                continue
            seen.add(prompt)

            if used_in_session:
                # 別スキルが使われた → near-miss
                near_miss.append({
                    "query": prompt,
                    "confidence_weight": NEAR_MISS_CONFIDENCE_WEIGHT,
                    "source": "near_miss",
                })
            else:
                # スキル未使用 → unrelated
                unrelated.append({
                    "query": prompt,
                    "confidence_weight": UNRELATED_CONFIDENCE_WEIGHT,
                    "source": "unrelated",
                })

    return near_miss + unrelated


def _balance_queries(queries: List[str], target: int) -> List[str]:
    """クエリ数をターゲットに調整する。"""
    if len(queries) <= target:
        return queries
    return random.sample(queries, target)


def _balance_should_not_trigger(
    entries: List[Dict[str, Any]],
    target: int,
) -> List[Dict[str, Any]]:
    """should_not_trigger エントリをターゲットに調整する。near-miss 優先。"""
    if len(entries) <= target:
        return entries

    near_miss = [e for e in entries if e.get("source") == "near_miss"]
    unrelated = [e for e in entries if e.get("source") == "unrelated"]

    if len(near_miss) >= target:
        return random.sample(near_miss, target)

    result = near_miss[:]
    remaining = target - len(result)
    if remaining > 0 and unrelated:
        result.extend(random.sample(unrelated, min(remaining, len(unrelated))))

    return result


def _save_eval_set(skill_name: str, eval_set: List[Dict[str, Any]]) -> Path:
    """eval set をファイルに保存する。"""
    EVAL_SETS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVAL_SETS_DIR / f"{skill_name}.json"
    # skill-creator 互換: query + should_trigger のみ出力
    clean_set = [{"query": e["query"], "should_trigger": e["should_trigger"]} for e in eval_set]
    path.write_text(json.dumps(clean_set, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _skipped_result(skill_name: str, reason: str, available: int) -> Dict[str, Any]:
    """スキップ結果を返す。"""
    return {
        "skill": skill_name,
        "eval_set": [],
        "eval_set_path": None,
        "skipped": True,
        "reason": reason,
        "available": available,
        "stats": {"should_trigger": 0, "should_not_trigger": 0},
    }
