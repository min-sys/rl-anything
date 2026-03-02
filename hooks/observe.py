#!/usr/bin/env python3
"""PostToolUse async hook — スキル使用・ファイルパス・エラーを記録する。

stdin から Claude Code の PostToolUse イベント JSON を受け取り、
~/.claude/rl-anything/ 配下の JSONL ファイルに追記する。

LLM 呼び出しは行わない（MUST NOT）。
書き込み失敗時はセッションをブロックしない（サイレント失敗）。
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".claude" / "rl-anything"
GLOBAL_SKILLS_PREFIX = str(Path.home() / ".claude" / "skills")


def ensure_data_dir() -> None:
    """ディレクトリが存在しない場合 MUST 自動作成する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def append_jsonl(filepath: Path, record: dict) -> None:
    """JSONL ファイルに1行追記する。失敗時はサイレント。"""
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[rl-anything:observe] write failed: {e}", file=sys.stderr)


def is_global_skill(skill_name: str, tool_input: dict) -> bool:
    """global スキル（~/.claude/skills/ 配下）かどうかを判定する。"""
    skill_path = tool_input.get("skill", "")
    return skill_path.startswith(GLOBAL_SKILLS_PREFIX) or skill_path.startswith("~/.claude/skills/")


def handle_post_tool_use(event: dict) -> None:
    """PostToolUse イベントを処理する。"""
    ensure_data_dir()
    now = datetime.now(timezone.utc).isoformat()

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    tool_result = event.get("tool_result", {})
    session_id = event.get("session_id", "")

    # Skill ツール呼び出し時のみ usage を記録
    if tool_name == "Skill":
        skill_name = tool_input.get("skill", "unknown")
        usage_record = {
            "skill_name": skill_name,
            "timestamp": now,
            "session_id": session_id,
            "file_path": tool_input.get("args", ""),
        }
        append_jsonl(DATA_DIR / "usage.jsonl", usage_record)

        # global スキルの場合、Usage Registry にも記録
        if is_global_skill(skill_name, tool_input):
            project_path = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            registry_record = {
                "skill_name": skill_name,
                "project_path": project_path,
                "timestamp": now,
            }
            append_jsonl(DATA_DIR / "usage-registry.jsonl", registry_record)

    # エラーの記録
    is_error = tool_result.get("is_error", False) if isinstance(tool_result, dict) else False
    if is_error:
        error_record = {
            "tool_name": tool_name,
            "skill_name": tool_input.get("skill", "") if tool_name == "Skill" else "",
            "error": str(tool_result.get("content", ""))[:500],
            "timestamp": now,
            "session_id": session_id,
        }
        append_jsonl(DATA_DIR / "errors.jsonl", error_record)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
        handle_post_tool_use(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:observe] parse error: {e}", file=sys.stderr)
    except Exception as e:
        # サイレント失敗: セッションをブロックしない
        print(f"[rl-anything:observe] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
