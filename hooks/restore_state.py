#!/usr/bin/env python3
"""SessionStart hook — チェックポイントから進化状態を復元する。

保存済み checkpoint.json が存在する場合、前回の進化状態を復元して
stdout に JSON で出力する。
"""
import json
import sys
from pathlib import Path

DATA_DIR = Path.home() / ".claude" / "rl-anything"


def handle_session_start(event: dict) -> None:
    """SessionStart イベントを処理する。"""
    checkpoint_file = DATA_DIR / "checkpoint.json"

    if not checkpoint_file.exists():
        return

    try:
        checkpoint = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        # 復元した状態を stdout に出力（Claude Code が利用可能）
        print(json.dumps({
            "restored": True,
            "checkpoint": checkpoint,
        }, ensure_ascii=False))
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
