#!/usr/bin/env python3
"""PostCompact hook — Compact 後にチェックポイントから作業コンテキストを注入する。

PreCompact (save_state.py) が保存した checkpoint を読み込み、
systemMessage としてブランチ・直近コミット・未コミットファイルを注入する。
これにより Compact 後のコンテキスト復元精度が向上する。
"""
import json
import os
import sys

import common


def _build_context_message(checkpoint: dict) -> str:
    """checkpoint から人間可読なコンテキストサマリーを構築する。"""
    parts = ["[rl-anything:post_compact] Compact 後の作業コンテキスト:"]

    work_context = checkpoint.get("work_context", {})

    branch = work_context.get("git_branch", "")
    if branch:
        parts.append(f"  ブランチ: {branch}")

    commits = work_context.get("recent_commits", [])
    if commits:
        parts.append(f"  直近コミット: {', '.join(commits[:5])}")

    files = work_context.get("uncommitted_files", [])
    if files:
        parts.append(f"  未コミット: {', '.join(files[:15])}")

    corrections = checkpoint.get("corrections_snapshot", [])
    if corrections:
        parts.append(f"  蓄積 corrections: {len(corrections)}件")

    return "\n".join(parts)


def handle_post_compact(event: dict) -> None:
    """PostCompact イベントを処理し、systemMessage を出力する。"""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "") or None
    checkpoint = common.find_latest_checkpoint(project_dir)

    if not checkpoint:
        return

    message = _build_context_message(checkpoint)
    result = {"systemMessage": message}
    json.dump(result, sys.stdout, ensure_ascii=False)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            handle_post_compact({})
            return
        event = json.loads(raw)
        handle_post_compact(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:post_compact] parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[rl-anything:post_compact] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
