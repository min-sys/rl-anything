#!/usr/bin/env python3
"""FileChanged hook — CLAUDE.md/SKILL.md/rules 変更を検知し audit を提案する。

CC v2.1.83 で追加された FileChanged イベントを処理する。
クールダウンは trigger_engine に一元化（hook 側 dedup なし）。
LLM 呼び出しは行わない（MUST NOT）。
"""
import json
import sys
from pathlib import Path

# trigger_engine のパスを通す
_scripts_lib = str(Path(__file__).resolve().parent.parent / "scripts" / "lib")
if _scripts_lib not in sys.path:
    sys.path.insert(0, _scripts_lib)

from trigger_engine import evaluate_file_changed, is_watched_file


def _discover_rule_files(cwd: str) -> list[str]:
    """cwd 配下の .claude/rules/*.md を発見して絶対パスリストを返す。"""
    rules_dir = Path(cwd) / ".claude" / "rules"
    if not rules_dir.is_dir():
        return []
    return [str(p) for p in sorted(rules_dir.glob("*.md"))]


def handle_file_changed(event: dict) -> dict | None:
    """FileChanged イベントを処理する。

    Returns:
        CC hook 出力 dict（systemMessage + watchPaths）、または None（スキップ時）。
    """
    file_path = event.get("file_path", "")
    cwd = event.get("cwd", "")

    # watched ファイルかチェック
    category = is_watched_file(file_path)
    if category is None:
        return None

    # trigger_engine に委譲
    result = evaluate_file_changed(file_path)

    # watchPaths: .claude/rules/*.md を動的登録（常に出力）
    watch_paths = _discover_rule_files(cwd) if cwd else []

    output: dict = {}
    if watch_paths:
        output["watchPaths"] = watch_paths

    if result.triggered:
        output["systemMessage"] = f"[rl-anything:auto-trigger] {result.message}"

    return output if output else None


def main() -> None:
    """stdin から JSON を読み取り FileChanged イベントを処理する。"""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return

    result = handle_file_changed(event)
    if result:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
