#!/usr/bin/env python3
"""淘汰スクリプト。

dead glob・zero invocation・重複の3基準でアーティファクトを検出し、
アーカイブを提案する。直接削除は行わない（MUST NOT）。
"""
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))

from audit import (
    DATA_DIR,
    find_artifacts,
    load_usage_data,
    aggregate_usage,
    load_usage_registry,
    semantic_similarity_check,
)

ARCHIVE_DIR = DATA_DIR / "archive"
ZERO_INVOCATION_DAYS = 30


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
    for path in artifacts.get("skills", []):
        skill_name = path.parent.name
        # global スキルはここでは検出しない（safe_global_check で処理）
        if str(path).startswith(str(Path.home() / ".claude" / "skills")):
            continue
        if skill_name not in used_skills:
            zero.append({
                "file": str(path),
                "skill_name": skill_name,
                "reason": "zero_invocation",
                "days": days,
            })

    for path in artifacts.get("rules", []):
        rule_name = path.stem
        if rule_name not in used_skills:
            zero.append({
                "file": str(path),
                "skill_name": rule_name,
                "reason": "zero_invocation",
                "days": days,
            })

    return zero


def safe_global_check(artifacts: Dict[str, List[Path]]) -> List[Dict[str, Any]]:
    """global スキルの安全な判断。Usage Registry を参照して cross-PJ 使用状況を確認。"""
    registry = load_usage_registry()
    candidates = []

    for path in artifacts.get("skills", []):
        if not str(path).startswith(str(Path.home() / ".claude" / "skills")):
            continue
        skill_name = path.parent.name
        usages = registry.get(skill_name, [])
        projects = set(r.get("project_path", "") for r in usages)

        if len(projects) == 0:
            candidates.append({
                "file": str(path),
                "skill_name": skill_name,
                "reason": "global_unused",
                "project_count": 0,
            })
        elif len(projects) == 1:
            candidates.append({
                "file": str(path),
                "skill_name": skill_name,
                "reason": "global_single_project",
                "project_count": 1,
                "projects": list(projects),
            })

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


def run_prune(project_dir: Optional[str] = None) -> Dict[str, Any]:
    """Prune を実行して候補を返す。"""
    proj = Path(project_dir) if project_dir else Path.cwd()
    artifacts = find_artifacts(proj)

    candidates = {
        "dead_globs": detect_dead_globs(proj),
        "zero_invocations": detect_zero_invocations(artifacts),
        "global_candidates": safe_global_check(artifacts),
        "duplicate_candidates": detect_duplicates(artifacts),
    }

    total = sum(len(v) for v in candidates.values())
    candidates["total_candidates"] = total

    return candidates


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_prune(project)
    print(json.dumps(result, ensure_ascii=False, indent=2))
