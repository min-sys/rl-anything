#!/usr/bin/env python3
"""StopFailure hook — API エラーによるセッション中断を errors.jsonl に記録する。

rate limit、認証失敗等の API エラーでターンが終了した際に発火する。
LLM 呼び出しは行わない（MUST NOT）。
"""
import json
import os
import sys
from datetime import datetime, timezone

import common


def handle_stop_failure(event: dict) -> None:
    """StopFailure イベントを処理する。"""
    common.ensure_data_dir()

    session_id = event.get("session_id", "")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    project = common.project_name_from_dir(project_dir) if project_dir else None

    record = {
        "type": "api_error",
        "tool_name": "",
        "skill_name": "",
        "error_type": event.get("error_type", "unknown"),
        "error": str(event.get("error_message", "") or event.get("error", ""))[:500],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "project": project,
    }
    wt = common.extract_worktree_info(event)
    if wt:
        record["worktree"] = wt
    common.append_jsonl(common.DATA_DIR / "errors.jsonl", record)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
        handle_stop_failure(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:stop_failure] parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[rl-anything:stop_failure] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
