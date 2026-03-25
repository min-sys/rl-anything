#!/usr/bin/env python3
"""SessionStart hook — チェックポイントから進化状態を復元する。

保存済み checkpoint.json が存在する場合、前回の進化状態を復元して
stdout に JSON で出力する。
"""
import json
import os
import sys
import time
from pathlib import Path

import common

HANDOVER_STALE_HOURS = 48.0
_HANDOVER_PREVIEW_LINES = 15
_PRIORITY_SECTIONS = ("Deploy State", "Next Actions")

# handover import (optional — for section extraction)
_handover_extract_section = None
try:
    _plugin_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_plugin_root / "skills" / "handover" / "scripts"))
    from handover import extract_section as _handover_extract_section
except ImportError:
    pass

# trigger_engine import (optional)
_trigger_engine = None
try:
    if _plugin_root is None:
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


def _extract_section(content: str, section_name: str) -> str:
    """Markdown の ## セクションを名前で抽出する。handover.py に委譲。"""
    if _handover_extract_section is not None:
        return _handover_extract_section(content, section_name)
    # フォールバック: handover.py が import できない場合
    import re
    pattern = rf"^## {re.escape(section_name)}\s*\n"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    next_header = re.search(r"^## ", content[start:], re.MULTILINE)
    if next_header:
        body = content[start : start + next_header.start()]
    else:
        body = content[start:]
    return body.strip()


def _detect_handover() -> None:
    """最新の handover ノートを検出しプレビュー表示する。

    Deploy State / Next Actions がある場合はそれらを優先表示し、
    なければ従来通り先頭行をプレビューする。
    """
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return
    handover_dir = Path(project_dir) / ".claude" / "handovers"
    if not handover_dir.exists():
        return
    files = sorted(handover_dir.glob("*.md"), reverse=True)
    if not files:
        return
    latest = files[0]
    try:
        age_hours = (time.time() - latest.stat().st_mtime) / 3600
    except OSError:
        return
    if age_hours > HANDOVER_STALE_HOURS:
        return
    try:
        content = latest.read_text(encoding="utf-8")
    except OSError:
        return

    # 優先セクションを抽出
    priority_parts: list[str] = []
    for section_name in _PRIORITY_SECTIONS:
        body = _extract_section(content, section_name)
        if body:
            priority_parts.append(f"## {section_name}\n{body}")

    if priority_parts:
        # タイトル行 + 優先セクション
        title_line = content.splitlines()[0] if content.splitlines() else latest.name
        preview = f"{title_line}\n\n" + "\n\n".join(priority_parts)
    else:
        # フォールバック: 先頭行プレビュー
        lines = content.splitlines()[:_HANDOVER_PREVIEW_LINES]
        preview = "\n".join(lines)

    print(f"[rl-anything:handover] 引き継ぎノートあり ({latest.name}):\n{preview}\n...")


def handle_session_start(event: dict) -> None:
    """SessionStart イベントを処理する。"""
    # Deliver pending trigger messages first
    _deliver_pending_trigger()

    # Handover ノート検出
    _detect_handover()

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
