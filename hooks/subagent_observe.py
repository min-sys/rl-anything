#!/usr/bin/env python3
"""SubagentStop async hook — subagent の完了データを記録する。

stdin から Claude Code の SubagentStop イベント JSON を受け取り、
~/.claude/rl-anything/subagents.jsonl に追記する。

LLM 呼び出しは行わない（MUST NOT）。
書き込み失敗時はセッションをブロックしない（MUST NOT）。
"""
import json
import os
import sys
from datetime import datetime, timezone

import common

MAX_MESSAGE_LENGTH = 500


def handle_subagent_stop(event: dict) -> None:
    """SubagentStop イベントを処理する。"""
    common.ensure_data_dir()

    last_message = event.get("last_assistant_message") or ""
    if len(last_message) > MAX_MESSAGE_LENGTH:
        last_message = last_message[:MAX_MESSAGE_LENGTH]

    session_id = event.get("session_id", "")
    wf_ctx = common.read_workflow_context(session_id)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    project = common.project_name_from_dir(project_dir) if project_dir else None

    record = {
        "agent_type": event.get("agent_type", ""),
        "agent_id": event.get("agent_id", ""),
        "last_assistant_message": last_message,
        "agent_transcript_path": event.get("agent_transcript_path", ""),
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "parent_skill": wf_ctx["parent_skill"],
        "workflow_id": wf_ctx["workflow_id"],
        "project": project,
    }
    wt = common.extract_worktree_info(event)
    if wt:
        record["worktree"] = wt
    common.append_jsonl(common.DATA_DIR / "subagents.jsonl", record)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
        handle_subagent_stop(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:subagent_observe] parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[rl-anything:subagent_observe] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
