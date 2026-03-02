#!/usr/bin/env python3
"""セッショントランスクリプトから Skill/Agent ツール呼び出しを抽出し usage.jsonl にバックフィルする。

トランスクリプト（~/.claude/projects/<encoded-path>/*.jsonl）内の
type: "assistant" レコードから tool_use ブロック（Skill/Agent）を検出し、
observe hooks と同形式で usage.jsonl に追記する。
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# プラグインルートを sys.path に追加して hooks/common.py を import
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "hooks"))

import common

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
MAX_PROMPT_LENGTH = 200


def resolve_project_dir(project_dir: Optional[str] = None) -> Path:
    """プロジェクトディレクトリ → ~/.claude/projects/ パスを解決する。

    エンコード規則: pwd のパスを `-` 区切りに変換（例: /Users/foo/bar → -Users-foo-bar）。
    一致するディレクトリが見つからない場合は部分一致で検索する。
    """
    if project_dir is None:
        project_dir = os.getcwd()
    project_dir = os.path.abspath(project_dir)

    # エンコード: / を - に変換
    encoded = project_dir.replace("/", "-")

    # 完全一致チェック
    exact_path = CLAUDE_PROJECTS_DIR / encoded
    if exact_path.is_dir():
        return exact_path

    # 部分一致で検索
    if CLAUDE_PROJECTS_DIR.is_dir():
        for d in CLAUDE_PROJECTS_DIR.iterdir():
            if d.is_dir() and encoded in d.name:
                return d

    raise FileNotFoundError(
        f"プロジェクトディレクトリが見つかりません: {project_dir} "
        f"(encoded: {encoded}, search dir: {CLAUDE_PROJECTS_DIR})"
    )


def get_backfilled_session_ids() -> Set[str]:
    """既に usage.jsonl にバックフィル済みの session_id セットを取得する。"""
    usage_file = common.DATA_DIR / "usage.jsonl"
    session_ids: Set[str] = set()
    if not usage_file.exists():
        return session_ids

    for line in usage_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            if record.get("source") == "backfill":
                sid = record.get("session_id", "")
                if sid:
                    session_ids.add(sid)
        except (json.JSONDecodeError, KeyError):
            continue
    return session_ids


def remove_backfill_records() -> None:
    """usage.jsonl から source=backfill のレコードを全て削除する。"""
    usage_file = common.DATA_DIR / "usage.jsonl"
    if not usage_file.exists():
        return

    lines = usage_file.read_text(encoding="utf-8").splitlines()
    kept: List[str] = []
    for line in lines:
        try:
            record = json.loads(line)
            if record.get("source") != "backfill":
                kept.append(line)
        except json.JSONDecodeError:
            kept.append(line)

    usage_file.write_text("\n".join(kept) + "\n" if kept else "", encoding="utf-8")


def parse_transcript(filepath: Path) -> List[Dict[str, Any]]:
    """トランスクリプト JSONL をパースし、Skill/Agent ツール呼び出しを抽出する。

    Returns:
        List of dicts: extracted tool calls with skill_name, session_id, timestamp, source, etc.
    """
    results: List[Dict[str, Any]] = []
    errors = 0

    for line in filepath.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue

        if record.get("type") != "assistant":
            continue

        message = record.get("message", {})
        if not isinstance(message, dict):
            continue

        content = message.get("content", [])
        if not isinstance(content, list):
            continue

        timestamp = record.get("timestamp", "")
        session_id = record.get("sessionId", "")

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue

            tool_name = block.get("name", "")
            tool_input = block.get("input", {})
            if not isinstance(tool_input, dict):
                continue

            if tool_name == "Skill":
                skill_name = tool_input.get("skill", "unknown")
                results.append({
                    "skill_name": skill_name,
                    "timestamp": timestamp,
                    "session_id": session_id,
                    "file_path": tool_input.get("args", ""),
                    "source": "backfill",
                })

            elif tool_name == "Agent":
                subagent_type = tool_input.get("subagent_type", "unknown") or "unknown"
                prompt = tool_input.get("prompt", "") or ""
                if len(prompt) > MAX_PROMPT_LENGTH:
                    prompt = prompt[:MAX_PROMPT_LENGTH]
                results.append({
                    "skill_name": f"Agent:{subagent_type}",
                    "subagent_type": subagent_type,
                    "prompt": prompt,
                    "timestamp": timestamp,
                    "session_id": session_id,
                    "source": "backfill",
                })

    return results, errors


def backfill(project_dir: Optional[str] = None, force: bool = False) -> Dict[str, int]:
    """メインのバックフィル処理。"""
    common.ensure_data_dir()

    project_path = resolve_project_dir(project_dir)

    # --force 時は既存バックフィルレコードを削除
    if force:
        remove_backfill_records()
        backfilled_sessions: Set[str] = set()
    else:
        backfilled_sessions = get_backfilled_session_ids()

    summary = {
        "sessions_processed": 0,
        "skill_calls": 0,
        "agent_calls": 0,
        "errors": 0,
        "skipped_sessions": 0,
    }

    # トランスクリプト JSONL ファイルを収集
    transcript_files = sorted(project_path.glob("*.jsonl"))

    for tf in transcript_files:
        # ファイル名（拡張子なし）= session_id
        session_id = tf.stem

        # 重複チェック
        if session_id in backfilled_sessions:
            summary["skipped_sessions"] += 1
            continue

        records, parse_errors = parse_transcript(tf)
        summary["errors"] += parse_errors

        if not records:
            continue

        summary["sessions_processed"] += 1

        for rec in records:
            if rec.get("skill_name", "").startswith("Agent:"):
                summary["agent_calls"] += 1
            else:
                summary["skill_calls"] += 1
            common.append_jsonl(common.DATA_DIR / "usage.jsonl", rec)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="セッショントランスクリプトから Skill/Agent 呼び出しをバックフィル"
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="バックフィル対象のプロジェクトディレクトリ（デフォルト: カレントディレクトリ）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存のバックフィルレコードを削除して全セッションを再処理する",
    )
    args = parser.parse_args()

    try:
        summary = backfill(project_dir=args.project_dir, force=args.force)
        print(json.dumps(summary, ensure_ascii=False))
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
