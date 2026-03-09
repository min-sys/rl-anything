#!/usr/bin/env python3
"""SessionStart hook — チェックポイントから進化状態を復元する。

保存済み checkpoint.json が存在する場合、前回の進化状態を復元して
stdout に JSON で出力する。
"""
import json
import sys
from pathlib import Path

import common

# trigger_engine import (optional)
_trigger_engine = None
try:
    _plugin_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
    from trigger_engine import read_and_delete_pending_trigger
    _trigger_engine = True
except ImportError:
    pass


def _format_work_context_summary(work_context: dict) -> str:
    """work_context から人間可読なサマリーを生成する。"""
    parts = ["[rl-anything:restore_state] 作業コンテキスト復元:"]

    branch = work_context.get("git_branch", "")
    if branch:
        parts.append(f"  ブランチ: {branch}")

    commits = work_context.get("recent_commits", [])
    if commits:
        parts.append(f"  完了: {', '.join(commits)}")

    files = work_context.get("uncommitted_files", [])
    if files:
        parts.append(f"  作業中: {', '.join(files)}")

    if len(parts) == 1:
        return ""
    return "\n".join(parts)


def _deliver_pending_trigger() -> None:
    """pending-trigger.json があれば読み取り、提案メッセージを stdout に出力する。"""
    if _trigger_engine is None:
        return
    try:
        data = read_and_delete_pending_trigger()
        if data is None:
            return
        message = data.get("message", "")
        if message:
            print(f"[rl-anything:auto-trigger] {message}")
    except Exception as e:
        print(f"[rl-anything:restore_state] trigger delivery error: {e}", file=sys.stderr)


def handle_session_start(event: dict) -> None:
    """SessionStart イベントを処理する。"""
    # Deliver pending trigger messages first
    _deliver_pending_trigger()

    checkpoint_file = common.DATA_DIR / "checkpoint.json"

    if not checkpoint_file.exists():
        return

    try:
        checkpoint = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        # 復元した状態を stdout に出力（Claude Code が利用可能）
        print(json.dumps({
            "restored": True,
            "checkpoint": checkpoint,
        }, ensure_ascii=False))

        # work_context がある場合はサマリーも出力
        work_context = checkpoint.get("work_context")
        if work_context:
            summary = _format_work_context_summary(work_context)
            if summary:
                print(summary)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[rl-anything:restore_state] restore failed: {e}", file=sys.stderr)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            # stdin なしでも checkpoint 復元は試みる
            handle_session_start({})
            return
        event = json.loads(raw)
        handle_session_start(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:restore_state] parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[rl-anything:restore_state] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
