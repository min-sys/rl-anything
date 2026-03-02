#!/usr/bin/env python3
"""hooks 共通ユーティリティ — DATA_DIR, ensure_data_dir, append_jsonl を提供する。"""
import json
import sys
from pathlib import Path

DATA_DIR = Path.home() / ".claude" / "rl-anything"


def ensure_data_dir() -> None:
    """ディレクトリが存在しない場合 MUST 自動作成する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def append_jsonl(filepath: Path, record: dict) -> None:
    """JSONL ファイルに1行追記する。失敗時はサイレント。"""
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[rl-anything] write failed: {e}", file=sys.stderr)
