#!/usr/bin/env python3
"""NFD Growth Journal — 結晶化イベント記録・照会 + backfill。

evolve/reflect が rule/skill を生成・更新するたびに結晶化イベントを記録。
growth-journal.jsonl に蓄積し、成長ストーリーの素材にする。
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "hooks"))

try:
    import common as _common

    _DATA_DIR_VAL = _common.DATA_DIR
except ImportError:
    _DATA_DIR_VAL = Path.home() / ".claude" / "rl-anything"

JOURNAL_FILENAME = "growth-journal.jsonl"

# backfill 対象のコミットメッセージパターン
_CRYSTALLIZATION_PATTERNS = re.compile(
    r"(evolve|reflect|remediation)", re.IGNORECASE
)


def _data_dir() -> Path:
    return _DATA_DIR_VAL


# ── 結晶化イベント記録 ─────────────────────────────────────────


def emit_crystallization(
    project: str,
    targets: List[str],
    evidence_count: int,
    phase: str,
    *,
    source: str = "evolve",
    commit: Optional[str] = None,
) -> None:
    """結晶化イベントを growth-journal.jsonl に追記。"""
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "type": "crystallization",
        "ts": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "targets": targets,
        "evidence_count": evidence_count,
        "phase": phase,
        "source": source,
    }
    if commit:
        record["commit"] = commit

    journal_path = data_dir / JOURNAL_FILENAME
    with open(journal_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── 結晶化イベント照会 ─────────────────────────────────────────


def query_crystallizations(
    project: Optional[str] = None,
    since: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """growth-journal.jsonl から結晶化イベントを照会。"""
    journal_path = _data_dir() / JOURNAL_FILENAME
    if not journal_path.exists():
        return []

    results = []
    try:
        with open(journal_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if record.get("type") != "crystallization":
                    continue
                if project and record.get("project") != project:
                    continue
                if since and record.get("ts", "") < since:
                    continue

                results.append(record)
    except OSError:
        return []

    return results


def count_crystallized_rules(project: Optional[str] = None) -> int:
    """distinct target パスの数を返す。"""
    events = query_crystallizations(project=project)
    all_targets: set[str] = set()
    for ev in events:
        for t in ev.get("targets", []):
            all_targets.add(t)
    return len(all_targets)


# ── Backfill ────────────────────────────────────────────────────


def _run_git_log(project_dir: str) -> str:
    """git log からコミット情報を取得。"""
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--format=%H|%aI|%s",
                "--all",
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def backfill_from_git_log(project_dir: str) -> int:
    """git log から evolve/reflect/remediation コミットを抽出し結晶化イベントを生成。

    Returns:
        追加されたイベント数。
    """
    git_output = _run_git_log(project_dir)
    if not git_output.strip():
        return 0

    # 既存の commit hash を収集（重複排除）
    existing_commits: set[str] = set()
    for ev in query_crystallizations():
        c = ev.get("commit", "")
        if c:
            existing_commits.add(c)

    project_name = Path(project_dir).name
    count = 0

    for line in git_output.strip().split("\n"):
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue

        commit_hash, date_str, message = parts

        # evolve/reflect/remediation を含むコミットのみ
        if not _CRYSTALLIZATION_PATTERNS.search(message):
            continue

        # 重複排除
        if commit_hash in existing_commits:
            continue

        emit_crystallization(
            project=project_name,
            targets=[],  # git log からは具体的な target を特定できない
            evidence_count=0,
            phase="unknown",
            source="backfill",
            commit=commit_hash,
        )
        # ts を上書き（backfill 時はコミット日時を使用）
        _patch_last_event_ts(date_str)
        existing_commits.add(commit_hash)
        count += 1

    return count


def _patch_last_event_ts(ts: str) -> None:
    """最後に書き込んだイベントの ts をコミット日時に置換。"""
    journal_path = _data_dir() / JOURNAL_FILENAME
    if not journal_path.exists():
        return
    try:
        lines = journal_path.read_text(encoding="utf-8").strip().split("\n")
        if not lines:
            return
        last = json.loads(lines[-1])
        last["ts"] = ts
        lines[-1] = json.dumps(last, ensure_ascii=False)
        journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except (json.JSONDecodeError, OSError, IndexError):
        pass
