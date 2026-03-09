#!/usr/bin/env python3
"""PreCompact async hook — 進化状態をチェックポイントする。

コンテキスト圧縮前に evolve 関連の中間状態を checkpoint.json に保存する。
JSON シリアライズのみ（10-100ms 程度）。LLM 呼び出しなし。
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import common

_MAX_UNCOMMITTED_FILES = 30
_MAX_RECENT_COMMITS = 5
_GIT_TIMEOUT_SECONDS = 2


def _run_git(args: list[str], timeout: float) -> str:
    """git コマンドを実行し stdout を返す。失敗時は空文字列。"""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _collect_work_context() -> dict:
    """git から作業コンテキストを収集する。合計 3.5s 超過で残りを skip。"""
    context: dict = {
        "recent_commits": [],
        "uncommitted_files": [],
        "git_branch": "",
    }
    start = time.monotonic()

    # git branch
    branch_out = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], _GIT_TIMEOUT_SECONDS)
    context["git_branch"] = branch_out.strip()

    if time.monotonic() - start > 3.5:
        return context

    # recent commits
    log_out = _run_git(
        ["log", "--oneline", f"-{_MAX_RECENT_COMMITS}"], _GIT_TIMEOUT_SECONDS
    )
    if log_out:
        context["recent_commits"] = [
            line for line in log_out.strip().splitlines() if line.strip()
        ]

    if time.monotonic() - start > 3.5:
        return context

    # uncommitted files
    status_out = _run_git(["status", "--short"], _GIT_TIMEOUT_SECONDS)
    if status_out:
        files = [line.strip() for line in status_out.strip().splitlines() if line.strip()]
        context["uncommitted_files"] = files[:_MAX_UNCOMMITTED_FILES]

    return context


def _load_corrections_snapshot() -> list:
    """corrections.jsonl のスナップショットを読み込む。存在しない場合は空リスト。"""
    corrections_file = common.DATA_DIR / "corrections.jsonl"
    if not corrections_file.exists():
        return []
    records = []
    try:
        for line in corrections_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return records


def handle_pre_compact(event: dict) -> None:
    """PreCompact イベントを処理し、進化状態を保存する。"""
    common.ensure_data_dir()

    checkpoint = {
        "session_id": event.get("session_id", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "evolve_state": event.get("evolve_state", {}),
        "context_summary": event.get("context_summary", ""),
        "corrections_snapshot": _load_corrections_snapshot(),
        "work_context": _collect_work_context(),
    }

    checkpoint_file = common.DATA_DIR / "checkpoint.json"
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
