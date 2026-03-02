#!/usr/bin/env python3
"""Stop async hook — セッション要約を sessions.jsonl に追記する。

セッション終了時に使用スキル数・エラー数のサマリを記録する。
LLM 呼び出しは行わない（MUST NOT）。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".claude" / "rl-anything"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def append_jsonl(filepath: Path, record: dict) -> None:
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[rl-anything:session_summary] write failed: {e}", file=sys.stderr)


def count_session_usage(session_id: str) -> dict:
    """当該セッションの使用スキル数・エラー数を集計する。"""
    skill_count = 0
    error_count = 0

    usage_file = DATA_DIR / "usage.jsonl"
    if usage_file.exists():
        for line in usage_file.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("session_id") == session_id:
                    skill_count += 1
            except json.JSONDecodeError:
                continue

    errors_file = DATA_DIR / "errors.jsonl"
    if errors_file.exists():
        for line in errors_file.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("session_id") == session_id:
                    error_count += 1
            except json.JSONDecodeError:
                continue

    return {"skill_count": skill_count, "error_count": error_count}


def handle_stop(event: dict) -> None:
    """Stop イベントを処理する。"""
    ensure_data_dir()

    session_id = event.get("session_id", "")
    stats = count_session_usage(session_id)

    session_record = {
        "session_id": session_id,
        "skill_count": stats["skill_count"],
        "error_count": stats["error_count"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    append_jsonl(DATA_DIR / "sessions.jsonl", session_record)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
        handle_stop(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:session_summary] parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[rl-anything:session_summary] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
