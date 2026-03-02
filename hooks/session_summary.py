#!/usr/bin/env python3
"""Stop async hook — セッション要約・ワークフローシーケンスを記録する。

セッション終了時に使用スキル数・エラー数のサマリと、
ワークフローシーケンスを workflows.jsonl に書き出す。
LLM 呼び出しは行わない（MUST NOT）。
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import common


def count_session_usage(session_id: str) -> dict:
    """当該セッションの使用スキル数・エラー数を集計する。"""
    skill_count = 0
    error_count = 0

    usage_file = common.DATA_DIR / "usage.jsonl"
    if usage_file.exists():
        for line in usage_file.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("session_id") == session_id:
                    skill_count += 1
            except json.JSONDecodeError:
                continue

    errors_file = common.DATA_DIR / "errors.jsonl"
    if errors_file.exists():
        for line in errors_file.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("session_id") == session_id:
                    error_count += 1
            except json.JSONDecodeError:
                continue

    return {"skill_count": skill_count, "error_count": error_count}


def build_workflow_sequences(session_id: str) -> list:
    """usage.jsonl から当該セッションのワークフローシーケンスを組み立てる。"""
    usage_file = common.DATA_DIR / "usage.jsonl"
    if not usage_file.exists():
        return []

    # workflow_id ごとにレコードを収集
    workflows: dict = {}  # workflow_id -> {meta, steps}
    for line in usage_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("session_id") != session_id:
            continue
        wf_id = rec.get("workflow_id")
        if not wf_id:
            continue

        if wf_id not in workflows:
            workflows[wf_id] = {
                "workflow_id": wf_id,
                "skill_name": rec.get("parent_skill", ""),
                "session_id": session_id,
                "steps": [],
            }

        step = {
            "tool": rec.get("skill_name", ""),
            "intent_category": common.classify_prompt(rec.get("prompt", "")),
            "timestamp": rec.get("timestamp", ""),
        }
        workflows[wf_id]["steps"].append(step)

    # シーケンスレコードを組み立て
    now = datetime.now(timezone.utc).isoformat()
    sequences = []
    for wf in workflows.values():
        wf["step_count"] = len(wf["steps"])
        wf["source"] = "trace"
        wf["ended_at"] = now
        # started_at は文脈ファイルから取得（なければ最初のステップの timestamp）
        if wf["steps"]:
            wf["started_at"] = wf["steps"][0].get("timestamp", now)
        else:
            wf["started_at"] = now
        sequences.append(wf)

    return sequences


def cleanup_context_file(session_id: str) -> None:
    """ワークフロー文脈ファイルを削除する。存在しない場合はサイレントスキップ。"""
    ctx_path = common.workflow_context_path(session_id)
    try:
        if ctx_path.exists():
            ctx_path.unlink()
    except OSError as e:
        print(f"[rl-anything:session_summary] cleanup error: {e}", file=sys.stderr)


def handle_stop(event: dict) -> None:
    """Stop イベントを処理する。"""
    common.ensure_data_dir()

    session_id = event.get("session_id", "")
    stats = count_session_usage(session_id)

    session_record = {
        "session_id": session_id,
        "skill_count": stats["skill_count"],
        "error_count": stats["error_count"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    common.append_jsonl(common.DATA_DIR / "sessions.jsonl", session_record)

    # ワークフローシーケンスを workflows.jsonl に書き出す
    sequences = build_workflow_sequences(session_id)
    for seq in sequences:
        common.append_jsonl(common.DATA_DIR / "workflows.jsonl", seq)

    # 文脈ファイルのクリーンアップ
    cleanup_context_file(session_id)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        event = json.loads(raw)
        handle_stop(event)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[rl-anything:session_summary] parse error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[rl-anything:session_summary] unexpected error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
