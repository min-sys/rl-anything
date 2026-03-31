"""implement スキルのテレメトリ記録モジュール."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _data_dir() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_DATA", os.path.expanduser("~/.claude/rl-anything"))
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p


def record_usage(
    *,
    project: str,
    tasks_total: int,
    tasks_completed: int,
    mode: str,
    conformance_rate: float,
    lanes: int = 1,
    outcome: str = "success",
) -> dict:
    """usage.jsonl にスキル使用を記録し、書き込んだレコードを返す."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "skill": "implement",
        "project": project,
        "tasks_total": tasks_total,
        "tasks_completed": tasks_completed,
        "mode": mode,
        "conformance_rate": round(conformance_rate, 2),
        "lanes": lanes,
        "outcome": outcome,
    }
    path = _data_dir() / "usage.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def record_growth_journal(
    *,
    tasks_completed: int,
    conformance_rate: float,
    mode: str,
) -> dict:
    """growth-journal.jsonl に実装イベントを記録し、書き込んだレコードを返す."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": "implementation",
        "source": "implement-skill",
        "tasks_completed": tasks_completed,
        "conformance_rate": round(conformance_rate, 2),
        "mode": mode,
        "phase": "unknown",
    }
    path = _data_dir() / "growth-journal.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
