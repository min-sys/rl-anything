#!/usr/bin/env python3
"""PreToolUse async hook — Skill 呼び出し時にワークフロー文脈ファイルを書き出す。

stdin から Claude Code の PreToolUse イベント JSON を受け取り、
$TMPDIR/rl-anything-workflow-{session_id}.json に文脈を書き出す。

LLM 呼び出しは行わない（MUST NOT）。
書き込み失敗時はセッションをブロックしない（サイレント失敗）。
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _context_file_path(session_id: str) -> Path:
    """ワークフロー文脈ファイルのパスを返す。"""
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    return Path(tmpdir) / f"rl-anything-workflow-{session_id}.json"


def handle_pre_tool_use(event: dict) -> None:
    """PreToolUse イベントを処理する。Skill 呼び出し時に文脈ファイルを書き出す。"""
    tool_input = event.get("tool_input", {})
    session_id = event.get("session_id", "")
    if not session_id:
        return

    skill_name = tool_input.get("skill", "")
    if not skill_name:
        return

    workflow_id = f"wf-{uuid.uuid4().hex[:8]}"
    context = {
        "skill_name": skill_name,
        "session_id": session_id,
        "workflow_id": workflow_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    context_path = _context_file_path(session_id)
    context_path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
        handle_pre_tool_use(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:workflow_context] parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[rl-anything:workflow_context] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
