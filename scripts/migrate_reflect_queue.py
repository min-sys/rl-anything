#!/usr/bin/env python3
"""learnings-queue.json → corrections.jsonl 変換マイグレーションスクリプト。

claude-reflect の learnings-queue.json を rl-anything の corrections.jsonl に変換する。
冪等: 重複判定キー = (timestamp, SHA256(message[:100])) で二重追記を防止。
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

LEARNINGS_QUEUE = Path.home() / ".claude" / "learnings-queue.json"
CORRECTIONS_FILE = Path.home() / ".claude" / "rl-anything" / "corrections.jsonl"


def _dedup_key(timestamp: str, message: str) -> str:
    """重複判定キーを生成する。"""
    msg_hash = hashlib.sha256(message[:100].encode("utf-8")).hexdigest()[:16]
    return f"{timestamp}:{msg_hash}"


def load_existing_keys() -> Set[str]:
    """corrections.jsonl の既存レコードから重複判定キーセットを取得する。"""
    keys: Set[str] = set()
    if not CORRECTIONS_FILE.exists():
        return keys
    for line in CORRECTIONS_FILE.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "")
            msg = rec.get("original_text", "") or rec.get("message", "")
            if ts:
                keys.add(_dedup_key(ts, msg))
        except json.JSONDecodeError:
            continue
    return keys


def convert_learning(learning: Dict[str, Any]) -> Dict[str, Any]:
    """learnings-queue.json のエントリを corrections.jsonl 形式に変換する。"""
    now = datetime.now(timezone.utc).isoformat()
    timestamp = learning.get("timestamp", now)
    message = learning.get("message", "")

    return {
        "timestamp": timestamp,
        "original_text": message,
        "correction_type": learning.get("type", "correction"),
        "source": "migrate_learnings_queue",
        "confidence": 0.70,
        "reflect_status": "pending",
        "target_type": learning.get("target_type", "unknown"),
        "target_path": learning.get("target_path"),
        "session_id": learning.get("session_id"),
    }


def migrate(dry_run: bool = False) -> Dict[str, Any]:
    """マイグレーションを実行する。

    Returns:
        結果サマリ辞書
    """
    result: Dict[str, Any] = {
        "source": str(LEARNINGS_QUEUE),
        "destination": str(CORRECTIONS_FILE),
        "dry_run": dry_run,
    }

    if not LEARNINGS_QUEUE.exists():
        result["status"] = "skipped"
        result["reason"] = "learnings-queue.json not found"
        return result

    try:
        content = LEARNINGS_QUEUE.read_text(encoding="utf-8").strip()
        if not content or content == "[]":
            result["status"] = "skipped"
            result["reason"] = "learnings-queue.json is empty"
            return result
        learnings = json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        result["status"] = "error"
        result["reason"] = f"Failed to read learnings-queue.json: {e}"
        return result

    if not isinstance(learnings, list):
        result["status"] = "error"
        result["reason"] = "learnings-queue.json is not a JSON array"
        return result

    existing_keys = load_existing_keys()
    converted: List[Dict[str, Any]] = []
    skipped_duplicates = 0

    for learning in learnings:
        if not isinstance(learning, dict):
            continue
        ts = learning.get("timestamp", "")
        msg = learning.get("message", "")
        key = _dedup_key(ts, msg)
        if key in existing_keys:
            skipped_duplicates += 1
            continue
        converted.append(convert_learning(learning))
        existing_keys.add(key)

    result["total_learnings"] = len(learnings)
    result["converted"] = len(converted)
    result["skipped_duplicates"] = skipped_duplicates

    if dry_run:
        result["status"] = "dry_run"
        return result

    if converted:
        CORRECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CORRECTIONS_FILE, "a", encoding="utf-8") as f:
            for rec in converted:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 元ファイルを空配列にする
    LEARNINGS_QUEUE.write_text("[]", encoding="utf-8")

    result["status"] = "completed"
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="learnings-queue.json → corrections.jsonl マイグレーション"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変換結果を表示するが書き込みは行わない",
    )
    args = parser.parse_args()

    result = migrate(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
