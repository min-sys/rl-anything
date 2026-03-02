#!/usr/bin/env python3
"""PreCompact async hook — 進化状態をチェックポイントする。

コンテキスト圧縮前に evolve 関連の中間状態を checkpoint.json に保存する。
JSON シリアライズのみ（10-100ms 程度）。LLM 呼び出しなし。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".claude" / "rl-anything"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def handle_pre_compact(event: dict) -> None:
    """PreCompact イベントを処理し、進化状態を保存する。"""
    ensure_data_dir()

    checkpoint = {
        "session_id": event.get("session_id", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "evolve_state": event.get("evolve_state", {}),
        "context_summary": event.get("context_summary", ""),
    }

    checkpoint_file = DATA_DIR / "checkpoint.json"
    try:
        checkpoint_file.write_text(
            json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        print(f"[rl-anything:save_state] write failed: {e}", file=sys.stderr)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
        handle_pre_compact(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:save_state] parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[rl-anything:save_state] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
