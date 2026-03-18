#!/usr/bin/env python3
"""InstructionsLoaded hook — CLAUDE.md/rules ロードを sessions.jsonl に記録する。

セッション内で最初の 1 回のみ記録（flag file で dedup）。
stale flag（STALE_FLAG_TTL_HOURS 超過）は自動削除。
LLM 呼び出しは行わない（MUST NOT）。
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import common


def _flag_path(session_id: str) -> Path:
    """dedup フラグファイルのパスを返す。"""
    tmp = common.DATA_DIR / "tmp"
    return tmp / f"{common.INSTRUCTIONS_LOADED_FLAG_PREFIX}{session_id}"


def _cleanup_stale_flags() -> None:
    """STALE_FLAG_TTL_HOURS 超過のフラグファイルを削除する。"""
    tmp = common.DATA_DIR / "tmp"
    if not tmp.exists():
        return
    ttl_seconds = common.STALE_FLAG_TTL_HOURS * 3600
    now = time.time()
    for f in tmp.glob(f"{common.INSTRUCTIONS_LOADED_FLAG_PREFIX}*"):
        try:
            if now - f.stat().st_mtime > ttl_seconds:
                f.unlink()
        except OSError:
            pass


def handle_instructions_loaded(event: dict) -> None:
    """InstructionsLoaded イベントを処理する。"""
    common.ensure_data_dir()
    session_id = event.get("session_id", "")
    if not session_id:
        return

    # stale flag cleanup
    _cleanup_stale_flags()

    # dedup: セッション内で 1 回のみ
    flag = _flag_path(session_id)
    if flag.exists():
        return

    # フラグディレクトリ作成 & フラグ書き込み
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text(session_id, encoding="utf-8")

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    project = common.project_name_from_dir(project_dir) if project_dir else None

    record = {
        "type": "instructions_loaded",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project": project,
    }
    common.append_jsonl(common.DATA_DIR / "sessions.jsonl", record)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
        handle_instructions_loaded(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:instructions_loaded] parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[rl-anything:instructions_loaded] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
