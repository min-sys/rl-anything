#!/usr/bin/env python3
"""淘汰スクリプト。

dead glob・zero invocation・重複の3基準でアーティファクトを検出し、
アーカイブを提案する。直接削除は行わない（MUST NOT）。
"""
import json
import math
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "scripts"))

from lib.frontmatter import extract_description

from audit import (
    DATA_DIR,
    classify_artifact_origin,
    find_artifacts,
    load_usage_data,
    aggregate_usage,
    load_usage_registry,
    semantic_similarity_check,
)

ARCHIVE_DIR = DATA_DIR / "archive"
ZERO_INVOCATION_DAYS = 30
DEFAULT_DECAY_DAYS = 90
DEFAULT_DECAY_THRESHOLD = 0.2
CORRECTION_PENALTY = 0.15


def _count_triggers(skill_path: Path) -> int:
    """SKILL.md の frontmatter から Trigger 数を取得する。"""
    from lib.frontmatter import parse_frontmatter

    p = Path(skill_path)
    if p.name != "SKILL.md":
        candidate = p.parent / "SKILL.md" if p.is_file() else p / "SKILL.md"
        p = candidate
    fm = parse_frontmatter(p)
    desc = fm.get("description", "")
    if not isinstance(desc, str):
        return 0
    # "Trigger:" 行のカンマ区切りアイテム数をカウント
    for line in desc.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("trigger"):
            # "Trigger: a, b, c" → 3
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                return len([t.strip() for t in parts[1].split(",") if t.strip()])
    return 0


def _enrich_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """候補に description と recommendation を付与する。"""
    path = Path(candidate["file"])
    candidate["description"] = extract_skill_summary(path)
    candidate["trigger_count"] = _count_triggers(path)
    candidate["recommendation"] = suggest_recommendation(candidate)
    return candidate


def extract_skill_summary(skill_path: Path) -> str:
    """SKILL.md の frontmatter から description を抽出する。

    extract_description() のラッパー。skill_path が SKILL.md でない場合は
    同ディレクトリの SKILL.md を探す。
    """
    p = Path(skill_path)
    if p.name != "SKILL.md":
        candidate = p.parent / "SKILL.md" if p.is_file() else p / "SKILL.md"
        p = candidate
    return extract_description(p)


_ARCHIVE_KEYWORDS = ["debug", "temp", "hotfix", "workaround", "test-"]
_KEEP_KEYWORDS = ["daily", "pipeline", "utility"]
_KEEP_TRIGGER_THRESHOLD = 3


def suggest_recommendation(skill_info: Dict[str, Any]) -> str:
    """キーワードベースの一次推薦ラベルを返す。

    Args:
        skill_info: skill_name, description, trigger_count を含む辞書

    Returns:
        "archive推奨", "keep推奨", "要確認" のいずれか
    """
    name = skill_info.get("skill_name", "").lower()
    desc = skill_info.get("description", "").lower()
    trigger_count = skill_info.get("trigger_count", 0)
    text = f"{name} {desc}"

    if any(kw in text for kw in _ARCHIVE_KEYWORDS):
        return "archive推奨"
    if any(kw in text for kw in _KEEP_KEYWORDS) or trigger_count >= _KEEP_TRIGGER_THRESHOLD:
        return "keep推奨"
    return "要確認"


def load_corrections() -> Dict[str, List[Dict]]:
    """corrections.jsonl を読み込み、skill_name 別にグループ化して返す。

    corrections.jsonl が存在しない場合は空辞書を返す。
    新旧フィールド両対応: matched_patterns, sentiment, decay_days, routing_hint,
    guardrail, reflect_status, extracted_learning, project_path がなくても読める。
    """
    corrections_file = DATA_DIR / "corrections.jsonl"
    if not corrections_file.exists():
        return {}

    by_skill: Dict[str, List[Dict]] = {}
    for line in corrections_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            skill = record.get("last_skill")
            if skill:
                # 新フィールドにデフォルト値を設定（後方互換）
                record.setdefault("matched_patterns", [record.get("correction_type", "unknown")])
                record.setdefault("sentiment", "negative")
                record.setdefault("decay_days", DEFAULT_DECAY_DAYS)
                record.setdefault("routing_hint", "correction")
                record.setdefault("guardrail", False)
                record.setdefault("reflect_status", "pending")
                record.setdefault("extracted_learning", "")
                record.setdefault("project_path", "")
                by_skill.setdefault(skill, []).append(record)
        except json.JSONDecodeError:
            continue
    return by_skill


def cleanup_corrections() -> Dict[str, int]:
    """corrections.jsonl から decay_days 超過の applied/skipped レコードを削除する。

    - applied/skipped で decay_days 超過 → 削除
    - pending レコード → 保持（削除しない）
    - decay_days 未設定のレコードは DEFAULT_DECAY_DAYS を使用

    Returns:
        {"removed": int, "kept": int} の統計情報。
    """
    corrections_file = DATA_DIR / "corrections.jsonl"
    if not corrections_file.exists():
        return {"removed": 0, "kept": 0}

    now = datetime.now(timezone.utc)
    kept_lines: List[str] = []
    removed = 0

    for line in corrections_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            kept_lines.append(line)
            continue

        status = record.get("reflect_status", "pending")
        # pending レコードは常に保持
        if status not in ("applied", "skipped"):
            kept_lines.append(line)
            continue

        # decay_days 超過チェック
        decay_days = record.get("decay_days", DEFAULT_DECAY_DAYS)
        timestamp = record.get("timestamp", "")
        if not timestamp:
            kept_lines.append(line)
            continue

        try:
            ts_clean = timestamp.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_clean)
            age_days = (now - dt).total_seconds() / 86400
        except (ValueError, TypeError):
            kept_lines.append(line)
            continue

        if age_days > decay_days:
            removed += 1
        else:
            kept_lines.append(line)

    # ファイルを書き戻し
    corrections_file.write_text(
        "\n".join(kept_lines) + "\n" if kept_lines else "",
        encoding="utf-8",
    )

    return {"removed": removed, "kept": len(kept_lines)}


def load_decay_threshold() -> float:
    """evolve-state.json から decay_threshold を読み込む。未設定時はデフォルト 0.2。"""
    state_file = DATA_DIR / "evolve-state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            return float(state.get("decay_threshold", DEFAULT_DECAY_THRESHOLD))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return DEFAULT_DECAY_THRESHOLD


def compute_decay_score(
    age_days: float,
    correction_count: int = 0,
    decay_days: float = DEFAULT_DECAY_DAYS,
) -> float:
    """confidence = base_score * exp(-age_days / decay_days) を計算する。

    base_score = max(0.0, 1.0 - CORRECTION_PENALTY * correction_count)
    """
    base_score = max(0.0, 1.0 - CORRECTION_PENALTY * correction_count)
    return base_score * math.exp(-age_days / decay_days)


def is_pinned(skill_path: Path) -> bool:
    """.pin ファイルが存在するかチェックする。"""
    skill_dir = skill_path.parent if skill_path.is_file() else skill_path
    return (skill_dir / ".pin").exists()


def _expand_glob_pattern(pattern: str) -> List[str]:
    """ブレース展開とカンマ区切りを処理して個別パターンのリストを返す。

    例: "src/**/*.{ts,tsx}" → ["src/**/*.ts", "src/**/*.tsx"]
    例: "a/*.ts, b/*.ts" → ["a/*.ts", "b/*.ts"]
    """
    import re

    # 1. まずブレース展開（カンマ分割より先に処理）
    def expand_braces(s: str) -> List[str]:
        m = re.search(r"\{([^}]+)\}", s)
        if not m:
            return [s]
        alternatives = m.group(1).split(",")
        results = []
        for alt in alternatives:
            results.append(s[: m.start()] + alt.strip() + s[m.end() :])
        return results

    # 2. ブレースを含まないカンマでのみ分割
    # ブレース内のカンマは分割しない
    parts = []
    depth = 0
    current = []
    for ch in pattern:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    parts.append("".join(current).strip())

    # 3. 各パートでブレース展開
    expanded = []
    for part in parts:
        if not part:
            continue
        expanded.extend(expand_braces(part))
    return expanded


def detect_dead_globs(project_dir: Path) -> List[Dict[str, Any]]:
    """rules の paths 対象がマッチするファイルが存在しないものを検出。"""
    dead = []
    rules_dir = project_dir / ".claude" / "rules"
    if not rules_dir.exists():
        return dead

    for rule_file in rules_dir.glob("*.md"):
        content = rule_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("paths:"):
                raw_pattern = line.split("paths:", 1)[1].strip()
                if not raw_pattern:
                    continue
                patterns = _expand_glob_pattern(raw_pattern)
                # いずれかのパターンがマッチすればOK
                any_match = any(
                    list(project_dir.glob(p))[:1] for p in patterns
                )
                if not any_match:
                    dead.append({
                        "file": str(rule_file),
                        "pattern": raw_pattern,
                        "reason": "dead_glob",
                    })
    return dead


def detect_zero_invocations(
    artifacts: Dict[str, List[Path]], days: int = ZERO_INVOCATION_DAYS
) -> List[Dict[str, Any]]:
    """usage.jsonl で指定日数間使用記録がないアーティファクトを検出。

    直接の Skill tool_use に加えて、usage.jsonl の parent_skill として
    参照されている回数もカウントする（MUST）。
    subagents.jsonl は参照対象外。
    """
    usage_records = load_usage_data(days=days)
    used_skills = set()
    for rec in usage_records:
        used_skills.add(rec.get("skill_name", ""))
        # parent_skill 経由の使用もカウント
        parent = rec.get("parent_skill")
        if parent:
            used_skills.add(parent)

    zero = []
    plugin_unused = []
    for path in artifacts.get("skills", []):
        skill_name = path.parent.name
        origin = classify_artifact_origin(path)
        # global スキルはここでは検出しない（safe_global_check で処理）
        if origin == "global":
            continue
        # .pin ファイルによる淘汰保護
        if is_pinned(path):
            continue
        if skill_name not in used_skills:
            if origin == "plugin":
                plugin_unused.append({
                    "file": str(path),
                    "skill_name": skill_name,
                    "reason": "plugin_unused",
                })
            else:
                zero.append(_enrich_candidate({
                    "file": str(path),
                    "skill_name": skill_name,
                    "reason": "zero_invocation",
                    "days": days,
                }))

    # rules は毎ターン system prompt に注入されるため使用回数を測定できない。
    # 淘汰対象にしない。

    return zero, plugin_unused


def safe_global_check(artifacts: Dict[str, List[Path]]) -> List[Dict[str, Any]]:
    """global スキルの安全な判断。Usage Registry を参照して cross-PJ 使用状況を確認。

    usage-registry.jsonl（hooks が書き込む）のデータのみ使用する。
    データがない場合は空リストを返し、蓄積を待つ。
    """
    registry = load_usage_registry()
    if not registry:
        return []

    candidates = []

    for path in artifacts.get("skills", []):
        if not str(path).startswith(str(Path.home() / ".claude" / "skills")):
            continue
        # .pin ファイルによる淘汰保護
        if is_pinned(path):
            continue
        skill_name = path.parent.name
        usages = registry.get(skill_name, [])
        projects = set(r.get("project_path", "") for r in usages)
        projects.discard("")

        if len(projects) == 0:
            candidates.append(_enrich_candidate({
                "file": str(path),
                "skill_name": skill_name,
                "reason": "no_usage_in_registry",
                "project_count": 0,
            }))
        elif len(projects) == 1:
            candidates.append(_enrich_candidate({
                "file": str(path),
                "skill_name": skill_name,
                "reason": "single_project_only",
                "project_count": 1,
                "projects": list(projects),
            }))

    return candidates


def detect_duplicates(artifacts: Dict[str, List[Path]]) -> List[Dict[str, Any]]:
    """audit-report の重複検出結果（意味的類似度判定、閾値 80%）を利用する。

    audit.py の semantic_similarity_check() を再利用。
    """
    return semantic_similarity_check(artifacts, threshold=0.80)


def archive_file(filepath: str, reason: str) -> Optional[str]:
    """ファイルをアーカイブする。直接削除は行わない（MUST NOT）。"""
    src = Path(filepath)
    if not src.exists():
        return None

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # タイムスタンプ付きでアーカイブ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ARCHIVE_DIR / f"{timestamp}_{src.name}"
    shutil.move(str(src), str(dest))

    # メタデータを保存
    meta = {
        "original_path": str(src),
        "archive_path": str(dest),
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    meta_file = dest.with_suffix(dest.suffix + ".meta.json")
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return str(dest)


def restore_file(archive_path: str) -> Optional[str]:
    """アーカイブからファイルを復元する。"""
    arch = Path(archive_path)
    if not arch.exists():
        return None

    # メタデータから元のパスを取得
    meta_file = arch.with_suffix(arch.suffix + ".meta.json")
    if not meta_file.exists():
        return None

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    original_path = meta.get("original_path")
    if not original_path:
        return None

    dest = Path(original_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(arch), str(dest))
    meta_file.unlink()

    return str(dest)


def list_archive() -> List[Dict[str, Any]]:
    """アーカイブの一覧を取得する。"""
    if not ARCHIVE_DIR.exists():
        return []

    items = []
    for meta_file in ARCHIVE_DIR.glob("*.meta.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            archive_file_path = str(meta_file).replace(".meta.json", "")
            meta["archive_file"] = archive_file_path
            meta["exists"] = Path(archive_file_path).exists()
            items.append(meta)
        except (json.JSONDecodeError, OSError):
            continue

    return sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)


def detect_decay_candidates(
    artifacts: Dict[str, List[Path]],
    decay_days: float = DEFAULT_DECAY_DAYS,
) -> List[Dict[str, Any]]:
    """decay スコアが閾値以下のスキルを検出する。"""
    threshold = load_decay_threshold()
    corrections_by_skill = load_corrections()
    usage_records = load_usage_data()
    now = datetime.now(timezone.utc)

    # スキルごとの最新使用日を計算
    last_used: Dict[str, datetime] = {}
    for rec in usage_records:
        skill = rec.get("skill_name", "")
        parent = rec.get("parent_skill")
        ts = rec.get("timestamp", "")
        if not ts:
            continue
        try:
            ts_clean = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_clean)
        except (ValueError, TypeError):
            continue
        for name in [skill, parent]:
            if name and (name not in last_used or dt > last_used[name]):
                last_used[name] = dt

    candidates = []
    for path in artifacts.get("skills", []):
        skill_name = path.parent.name
        if is_pinned(path):
            continue
        if skill_name not in last_used:
            continue  # zero_invocations で処理済み
        age_days = (now - last_used[skill_name]).total_seconds() / 86400
        correction_count = len(corrections_by_skill.get(skill_name, []))
        score = compute_decay_score(age_days, correction_count, decay_days)
        if score < threshold:
            candidates.append(_enrich_candidate({
                "file": str(path),
                "skill_name": skill_name,
                "reason": "decay_below_threshold",
                "decay_score": round(score, 4),
                "age_days": round(age_days, 1),
                "correction_count": correction_count,
                "threshold": threshold,
            }))

    return candidates


def determine_primary(skill_a: str, skill_b: str) -> tuple:
    """どちらのスキルが primary（使用頻度が高い）かを判定する。

    Returns:
        (primary_path, secondary_path, primary_count, secondary_count)
    """
    usage_records = load_usage_data()
    usage_counts = aggregate_usage(usage_records)

    count_a = usage_counts.get(skill_a, 0)
    count_b = usage_counts.get(skill_b, 0)

    if count_a > count_b:
        return (skill_a, skill_b, count_a, count_b)
    elif count_b > count_a:
        return (skill_b, skill_a, count_b, count_a)
    else:
        # 同数の場合はアルファベット順（早い方が primary）
        if skill_a <= skill_b:
            return (skill_a, skill_b, count_a, count_b)
        else:
            return (skill_b, skill_a, count_b, count_a)


def merge_duplicates(
    duplicate_candidates: List[Dict[str, Any]],
    reorganize_merge_groups: Optional[List[Dict[str, Any]]] = None,
    project_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """重複候補とreorganizeマージグループを統合し、マージ提案を生成する。

    Args:
        duplicate_candidates: detect_duplicates() の結果。各要素は path_a, path_b を持つ。
        reorganize_merge_groups: reorganize フェーズからのマージグループ。
            各要素は skills: [name_list] を持つ。
        project_dir: プロジェクトディレクトリ。

    Returns:
        merge_proposals と total_proposals を含む辞書。
    """
    proj = Path(project_dir) if project_dir else Path.cwd()
    artifacts = find_artifacts(proj)

    # スキル名→パスのマッピングを構築
    skill_path_map: Dict[str, str] = {}
    for path in artifacts.get("skills", []):
        skill_name = path.parent.name
        skill_path_map[skill_name] = str(path)

    # 重複ペアを frozenset で収集（重複排除）
    pairs: set = set()

    # duplicate_candidates からペアを抽出
    for item in duplicate_candidates:
        path_a = item.get("path_a", "")
        path_b = item.get("path_b", "")
        # パスからスキル名を取得
        name_a = Path(path_a).parent.name if path_a else ""
        name_b = Path(path_b).parent.name if path_b else ""
        if name_a and name_b and name_a != name_b:
            pairs.add(frozenset([name_a, name_b]))

    # reorganize_merge_groups からペアを抽出
    if reorganize_merge_groups:
        for group in reorganize_merge_groups:
            skills = group.get("skills", [])
            for i in range(len(skills)):
                for j in range(i + 1, len(skills)):
                    if skills[i] != skills[j]:
                        pairs.add(frozenset([skills[i], skills[j]]))

    # 各ペアに対してマージ提案を生成
    merge_proposals: List[Dict[str, Any]] = []
    for pair in sorted(pairs, key=lambda p: sorted(p)):
        names = sorted(pair)
        skill_a, skill_b = names[0], names[1]

        path_a_str = skill_path_map.get(skill_a, "")
        path_b_str = skill_path_map.get(skill_b, "")

        # .pin チェック
        if (path_a_str and is_pinned(Path(path_a_str))) or (
            path_b_str and is_pinned(Path(path_b_str))
        ):
            merge_proposals.append({
                "primary": {"path": path_a_str, "skill_name": skill_a, "usage_count": 0},
                "secondary": {"path": path_b_str, "skill_name": skill_b, "usage_count": 0},
                "status": "skipped_pinned",
            })
            continue

        # プラグイン由来チェック
        origin_a = classify_artifact_origin(Path(path_a_str)) if path_a_str else "custom"
        origin_b = classify_artifact_origin(Path(path_b_str)) if path_b_str else "custom"
        if origin_a == "plugin" or origin_b == "plugin":
            merge_proposals.append({
                "primary": {"path": path_a_str, "skill_name": skill_a, "usage_count": 0},
                "secondary": {"path": path_b_str, "skill_name": skill_b, "usage_count": 0},
                "status": "skipped_plugin",
            })
            continue

        # primary/secondary を判定
        primary_name, secondary_name, primary_count, secondary_count = determine_primary(
            skill_a, skill_b
        )
        merge_proposals.append({
            "primary": {
                "path": skill_path_map.get(primary_name, ""),
                "skill_name": primary_name,
                "usage_count": primary_count,
            },
            "secondary": {
                "path": skill_path_map.get(secondary_name, ""),
                "skill_name": secondary_name,
                "usage_count": secondary_count,
            },
            "status": "proposed",
        })

    return {
        "merge_proposals": merge_proposals,
        "total_proposals": len(merge_proposals),
    }


def run_prune(
    project_dir: Optional[str] = None,
    reorganize_merge_groups: Optional[list] = None,
) -> Dict[str, Any]:
    """Prune を実行して候補を返す。"""
    proj = Path(project_dir) if project_dir else Path.cwd()
    artifacts = find_artifacts(proj)

    zero_invocations, plugin_unused = detect_zero_invocations(artifacts)

    candidates = {
        "dead_globs": detect_dead_globs(proj),
        "zero_invocations": zero_invocations,
        "plugin_unused": plugin_unused,
        "global_candidates": safe_global_check(artifacts),
        "duplicate_candidates": detect_duplicates(artifacts),
        "decay_candidates": detect_decay_candidates(artifacts),
    }

    total = sum(len(v) for v in candidates.values() if isinstance(v, list))
    candidates["total_candidates"] = total

    # rules は淘汰対象外。情報提供のみ。
    rules = artifacts.get("rules", [])
    candidates["rules_info"] = [
        {"name": p.stem, "scope": "global" if ".claude/rules" in str(p) and "projects" not in str(p) else "project"}
        for p in rules
    ]

    # corrections.jsonl クリーンアップ
    cleanup_result = cleanup_corrections()
    candidates["corrections_cleanup"] = cleanup_result

    # マージ提案を生成
    merge_result = merge_duplicates(
        candidates["duplicate_candidates"],
        reorganize_merge_groups=reorganize_merge_groups,
        project_dir=project_dir,
    )
    candidates["merge_result"] = merge_result

    return candidates


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_prune(project)
    print(json.dumps(result, ensure_ascii=False, indent=2))
