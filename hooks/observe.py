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

import common

GLOBAL_SKILLS_PREFIX = str(Path.home() / ".claude" / "skills")
MAX_PROMPT_LENGTH = 200


def is_global_skill(skill_name: str, tool_input: dict) -> bool:
    """global スキル（~/.claude/skills/ 配下）かどうかを判定する。"""
    skill_path = tool_input.get("skill", "")
    return skill_path.startswith(GLOBAL_SKILLS_PREFIX) or skill_path.startswith("~/.claude/skills/")


def _get_project() -> str | None:
    """CLAUDE_PROJECT_DIR から末尾ディレクトリ名を取得する。未設定・空文字列時は None。"""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return None
    return common.project_name_from_dir(project_dir)


def handle_post_tool_use(event: dict) -> None:
    """PostToolUse イベントを処理する。"""
    common.ensure_data_dir()
    now = datetime.now(timezone.utc).isoformat()
    project = _get_project()

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    tool_result = event.get("tool_result", {})
    session_id = event.get("session_id", "")

    # Skill ツール呼び出し時の usage 記録
    if tool_name == "Skill":
        skill_name = tool_input.get("skill", "unknown")
        usage_record = {
            "skill_name": skill_name,
            "timestamp": now,
            "session_id": session_id,
            "file_path": tool_input.get("args", ""),
            "project": project,
        }
        wt_skill = common.extract_worktree_info(event)
        if wt_skill:
            usage_record["worktree"] = wt_skill
        common.append_jsonl(common.DATA_DIR / "usage.jsonl", usage_record)

        # 直前スキル名を一時ファイルに記録（correction_detect.py が参照）
        common.write_last_skill(session_id, skill_name)

        # global スキルの場合、Usage Registry にも記録
        if is_global_skill(skill_name, tool_input):
            project_path = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            registry_record = {
                "skill_name": skill_name,
                "project_path": project_path,
                "timestamp": now,
            }
            common.append_jsonl(common.DATA_DIR / "usage-registry.jsonl", registry_record)

    # Agent ツール呼び出し時の usage 記録
    elif tool_name == "Agent":
        subagent_type = tool_input.get("subagent_type", "unknown") or "unknown"
        prompt = tool_input.get("prompt", "") or ""
        if len(prompt) > MAX_PROMPT_LENGTH:
            prompt = prompt[:MAX_PROMPT_LENGTH]
        wf_ctx = common.read_workflow_context(session_id)
        usage_record = {
            "skill_name": f"Agent:{subagent_type}",
            "subagent_type": subagent_type,
            "agent_id": event.get("agent_id", ""),
            "prompt": prompt,
            "session_id": session_id,
            "timestamp": now,
            "parent_skill": wf_ctx["parent_skill"],
            "workflow_id": wf_ctx["workflow_id"],
            "project": project,
        }
        wt = common.extract_worktree_info(event)
        if wt:
            usage_record["worktree"] = wt
        common.append_jsonl(common.DATA_DIR / "usage.jsonl", usage_record)

    # エラーの記録
    is_error = tool_result.get("is_error", False) if isinstance(tool_result, dict) else False
    if is_error:
        error_record = {
            "tool_name": tool_name,
            "skill_name": tool_input.get("skill", "") if tool_name == "Skill" else "",
            "error": str(tool_result.get("content", ""))[:500],
            "timestamp": now,
            "session_id": session_id,
            "project": project,
        }
        wt_err = common.extract_worktree_info(event)
        if wt_err:
            error_record["worktree"] = wt_err
        common.append_jsonl(common.DATA_DIR / "errors.jsonl", error_record)


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
