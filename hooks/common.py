#!/usr/bin/env python3
"""hooks 共通ユーティリティ — DATA_DIR, ensure_data_dir, append_jsonl, read_workflow_context, classify_prompt を提供する。"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".claude" / "rl-anything"

# ワークフロー文脈ファイルの有効期限（秒）
_WORKFLOW_CONTEXT_EXPIRE_SECONDS = 24 * 60 * 60  # 24時間


def ensure_data_dir() -> None:
    """ディレクトリが存在しない場合 MUST 自動作成する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def workflow_context_path(session_id: str) -> Path:
    """ワークフロー文脈ファイルのパスを返す。"""
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    return Path(tmpdir) / f"rl-anything-workflow-{session_id}.json"


def read_workflow_context(session_id: str) -> dict:
    """ワークフロー文脈ファイルを読み取り parent_skill/workflow_id を返す。

    文脈ファイルが存在しない、24時間以上経過、破損の場合は
    {"parent_skill": null, "workflow_id": null} を返す。
    セッションをブロックしない（MUST NOT）。
    """
    null_result = {"parent_skill": None, "workflow_id": None}
    try:
        ctx_path = workflow_context_path(session_id)
        if not ctx_path.exists():
            return null_result

        # 24時間 expire チェック
        mtime = ctx_path.stat().st_mtime
        age = datetime.now(timezone.utc).timestamp() - mtime
        if age > _WORKFLOW_CONTEXT_EXPIRE_SECONDS:
            return null_result

        ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
        return {
            "parent_skill": ctx.get("skill_name"),
            "workflow_id": ctx.get("workflow_id"),
        }
    except Exception as e:
        print(f"[rl-anything] read_workflow_context error: {e}", file=sys.stderr)
        return null_result


# Agent prompt を簡易分類するキーワードマップ
PROMPT_CATEGORIES = {
    "spec-review": ["spec", "requirement", "MUST", "quality check", r"review.*spec"],
    "code-exploration": ["structure", "explore", "codebase", "directory", r"find.*file"],
    "research": ["research", "best practice", "latest", "how to", "pattern"],
    "code-review": [r"review.*code", r"review.*change", r"review.*impl", "alignment", "verify"],
    "implementation": ["implement", "create", "build", r"write.*code", r"add.*feature"],
}


def classify_prompt(prompt: str) -> str:
    """prompt をキーワードベースで簡易分類する。"""
    prompt_lower = prompt.lower()
    for category, keywords in PROMPT_CATEGORIES.items():
        for kw in keywords:
            if re.search(kw, prompt_lower):
                return category
    return "other"


def append_jsonl(filepath: Path, record: dict) -> None:
    """JSONL ファイルに1行追記する。失敗時はサイレント。"""
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[rl-anything] write failed: {e}", file=sys.stderr)
