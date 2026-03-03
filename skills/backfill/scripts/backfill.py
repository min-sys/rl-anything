#!/usr/bin/env python3
"""セッショントランスクリプトから Skill/Agent ツール呼び出しを抽出し usage.jsonl にバックフィルする。

トランスクリプト（~/.claude/projects/<encoded-path>/*.jsonl）内の
type: "assistant" レコードから tool_use ブロック（Skill/Agent）を検出し、
observe hooks と同形式で usage.jsonl に追記する。
"""
import argparse
import json
import os
import secrets
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# プラグインルートを sys.path に追加して hooks/common.py を import
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "hooks"))

import common

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
MAX_PROMPT_LENGTH = 200


@dataclass
class ParseResult:
    """parse_transcript() の戻り値。"""
    usage_records: list = field(default_factory=list)
    workflow_records: list = field(default_factory=list)
    session_meta: Optional[Dict[str, Any]] = None
    errors: int = 0


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


def _remove_backfill_from_jsonl(filepath: Path, session_ids: Set[str]) -> None:
    """JSONL ファイルから、指定 session_ids に該当する source=backfill レコードを削除する。"""
    if not filepath.exists():
        return

    lines = filepath.read_text(encoding="utf-8").splitlines()
    kept: List[str] = []
    for line in lines:
        try:
            record = json.loads(line)
            if record.get("source") == "backfill" and record.get("session_id", "") in session_ids:
                continue  # 削除対象
            kept.append(line)
        except json.JSONDecodeError:
            kept.append(line)

    filepath.write_text("\n".join(kept) + "\n" if kept else "", encoding="utf-8")


def remove_backfill_records(session_ids: Set[str]) -> None:
    """usage.jsonl から対象プロジェクトの backfill レコードを削除する。"""
    _remove_backfill_from_jsonl(common.DATA_DIR / "usage.jsonl", session_ids)


def remove_backfill_workflows(session_ids: Set[str]) -> None:
    """workflows.jsonl から対象プロジェクトの backfill レコードを削除する。"""
    _remove_backfill_from_jsonl(common.DATA_DIR / "workflows.jsonl", session_ids)


def remove_backfill_sessions(session_ids: Set[str]) -> None:
    """sessions.jsonl から対象プロジェクトの backfill レコードを削除する。"""
    _remove_backfill_from_jsonl(common.DATA_DIR / "sessions.jsonl", session_ids)


def _generate_workflow_id() -> str:
    """wf-{8 hex chars} 形式のワークフロー ID を生成する。"""
    return f"wf-{secrets.token_hex(4)}"


def _finalize_workflow(
    workflow: Dict[str, Any],
    steps: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """ワークフローを確定し workflows.jsonl レコードとして返す。steps が空なら None。"""
    if not steps:
        return None
    workflow["steps"] = steps
    workflow["step_count"] = len(steps)
    workflow["ended_at"] = steps[-1].get("timestamp", workflow.get("started_at", ""))
    workflow["source"] = "backfill"
    return workflow


def _parse_iso_timestamp(ts: str) -> Optional[datetime]:
    """ISO 8601 タイムスタンプを datetime に変換する。失敗時は None。"""
    if not ts:
        return None
    try:
        # "2025-06-15T10:30:00Z" or "2025-06-15T10:30:00.123Z"
        ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def parse_transcript(filepath: Path) -> ParseResult:
    """トランスクリプト JSONL をパースし、Skill/Agent ツール呼び出しを抽出する。

    ワークフロー境界判定ルール（1パス処理）:
    - Skill tool_use 検出 → 新しいワークフロー開始（前のワークフローを確定）
    - 次の Skill or トランスクリプト終了まで → Agent は current_workflow に属する
    - Skill 前の Agent → ad-hoc（parent_skill: null, workflow_id: null）
    - Skill だけで Agent がない場合 → workflow_records に追加しない（step_count=0）

    セッションメタデータも同時に収集する:
    - tool_sequence: 全 tool_use の名前を順序付きで記録
    - tool_counts: ツール名ごとの呼び出し回数
    - session_duration_seconds: セッション開始〜終了の秒数
    - error_count: tool_result の is_error=true の回数
    - human_message_count: type=human のレコード数
    - user_intents: human メッセージの intent_category 分類

    Returns:
        ParseResult with usage_records, workflow_records, session_meta, errors
    """
    result = ParseResult()

    # ワークフロー追跡の状態
    current_workflow: Optional[Dict[str, Any]] = None
    current_steps: List[Dict[str, Any]] = []
    current_workflow_id: Optional[str] = None
    current_skill_name: Optional[str] = None

    # セッションメタデータ収集
    tool_sequence: List[str] = []
    tool_counts: Counter = Counter()
    timestamps: List[str] = []
    error_count = 0
    human_message_count = 0
    user_intents: List[str] = []
    session_id = ""

    for line in filepath.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            result.errors += 1
            continue

        record_type = record.get("type", "")
        timestamp = record.get("timestamp", "")
        if not session_id:
            session_id = record.get("sessionId", "")

        # タイムスタンプを収集（全レコードタイプ）
        if timestamp:
            timestamps.append(timestamp)

        # ユーザーメッセージの intent 分類（type: "human" or "user"）
        if record_type in ("human", "user"):
            human_message_count += 1
            message = record.get("message", {})
            if isinstance(message, dict):
                content = message.get("content", "")
                # content が文字列の場合
                if isinstance(content, str) and content.strip():
                    user_intents.append(common.classify_prompt(content[:MAX_PROMPT_LENGTH]))
                # content がリストの場合（text ブロック）
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text.strip():
                                user_intents.append(common.classify_prompt(text[:MAX_PROMPT_LENGTH]))
                                break  # 最初の text ブロックのみ
            continue

        # tool_result の is_error チェック
        if record_type == "tool_result":
            if record.get("is_error"):
                error_count += 1
            continue

        if record_type != "assistant":
            continue

        message = record.get("message", {})
        if not isinstance(message, dict):
            continue

        content = message.get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue

            tool_name = block.get("name", "")
            tool_input = block.get("input", {})
            if not isinstance(tool_input, dict):
                continue

            # 全ツール名を記録
            tool_sequence.append(tool_name)
            tool_counts[tool_name] += 1

            if tool_name == "Skill":
                # 前のワークフローを確定
                if current_workflow is not None:
                    wf_rec = _finalize_workflow(current_workflow, current_steps)
                    if wf_rec is not None:
                        result.workflow_records.append(wf_rec)

                # 新しいワークフロー開始
                skill_name = tool_input.get("skill", "unknown")
                current_workflow_id = _generate_workflow_id()
                current_skill_name = skill_name
                current_workflow = {
                    "workflow_id": current_workflow_id,
                    "skill_name": skill_name,
                    "session_id": session_id,
                    "started_at": timestamp,
                }
                current_steps = []

                # Skill 自身の usage レコード（parent_skill/workflow_id なし）
                result.usage_records.append({
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

                agent_record: Dict[str, Any] = {
                    "skill_name": f"Agent:{subagent_type}",
                    "subagent_type": subagent_type,
                    "prompt": prompt,
                    "timestamp": timestamp,
                    "session_id": session_id,
                    "source": "backfill",
                }

                if current_workflow is not None:
                    # Skill ワークフロー内の Agent
                    agent_record["parent_skill"] = current_skill_name
                    agent_record["workflow_id"] = current_workflow_id
                    # ステップとしても記録
                    current_steps.append({
                        "tool": f"Agent:{subagent_type}",
                        "intent_category": common.classify_prompt(prompt),
                        "timestamp": timestamp,
                    })
                else:
                    # ad-hoc Agent（Skill 前）
                    agent_record["parent_skill"] = None
                    agent_record["workflow_id"] = None

                result.usage_records.append(agent_record)

    # 最後のワークフローを確定
    if current_workflow is not None:
        wf_rec = _finalize_workflow(current_workflow, current_steps)
        if wf_rec is not None:
            result.workflow_records.append(wf_rec)

    # セッションメタデータを構築
    duration_seconds = 0.0
    if len(timestamps) >= 2:
        first_dt = _parse_iso_timestamp(timestamps[0])
        last_dt = _parse_iso_timestamp(timestamps[-1])
        if first_dt and last_dt:
            duration_seconds = (last_dt - first_dt).total_seconds()

    if tool_sequence or human_message_count > 0:
        result.session_meta = {
            "session_id": session_id,
            "project_name": "",  # backfill() から設定
            "tool_sequence": tool_sequence,
            "tool_counts": dict(tool_counts.most_common()),
            "total_tool_calls": len(tool_sequence),
            "session_duration_seconds": round(duration_seconds, 1),
            "first_timestamp": timestamps[0] if timestamps else "",
            "last_timestamp": timestamps[-1] if timestamps else "",
            "error_count": error_count,
            "human_message_count": human_message_count,
            "user_intents": user_intents,
            "source": "backfill",
        }

    return result


def backfill(project_dir: Optional[str] = None, force: bool = False) -> Dict[str, int]:
    """メインのバックフィル処理。"""
    common.ensure_data_dir()

    project_path = resolve_project_dir(project_dir)
    proj_name = common.project_name_from_dir(project_dir or os.getcwd())

    # 対象プロジェクトの session_id を特定（トランスクリプトのファイル名 = session_id）
    project_session_ids = {tf.stem for tf in project_path.glob("*.jsonl")}

    # --force 時は対象プロジェクトの backfill レコードのみ削除（他プロジェクトは保持）
    if force:
        remove_backfill_records(project_session_ids)
        remove_backfill_workflows(project_session_ids)
        remove_backfill_sessions(project_session_ids)
        backfilled_sessions: Set[str] = set()
    else:
        backfilled_sessions = get_backfilled_session_ids()

    summary = {
        "sessions_processed": 0,
        "skill_calls": 0,
        "agent_calls": 0,
        "workflows": 0,
        "sessions": 0,
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

        parse_result = parse_transcript(tf)
        summary["errors"] += parse_result.errors

        if not parse_result.usage_records and not parse_result.workflow_records and parse_result.session_meta is None:
            continue

        summary["sessions_processed"] += 1

        for rec in parse_result.usage_records:
            if rec.get("skill_name", "").startswith("Agent:"):
                summary["agent_calls"] += 1
            else:
                summary["skill_calls"] += 1
            common.append_jsonl(common.DATA_DIR / "usage.jsonl", rec)

        for wf_rec in parse_result.workflow_records:
            summary["workflows"] += 1
            common.append_jsonl(common.DATA_DIR / "workflows.jsonl", wf_rec)

        if parse_result.session_meta is not None:
            parse_result.session_meta["project_name"] = proj_name
            summary["sessions"] += 1
            common.append_jsonl(common.DATA_DIR / "sessions.jsonl", parse_result.session_meta)

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
