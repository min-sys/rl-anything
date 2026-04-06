#!/usr/bin/env python3
"""セッショントランスクリプトから Skill/Agent ツール呼び出しを抽出し usage.jsonl にバックフィルする。

トランスクリプト（~/.claude/projects/<encoded-path>/*.jsonl）内の
type: "assistant" レコードから tool_use ブロック（Skill/Agent）を検出し、
observe hooks と同形式で usage.jsonl に追記する。
"""
import argparse
import json
import os
import re
import secrets
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from plugin_root import PLUGIN_ROOT
sys.path.insert(0, str(PLUGIN_ROOT / "scripts" / "lib"))

import rl_common as common

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
MAX_PROMPT_LENGTH = 500
AGENT_BURST_GAP_SECONDS = 300
BACKFILL_CORRECTION_CONFIDENCE = 0.60

# <command-name> タグからコマンド名を抽出する正規表現
_COMMAND_NAME_RE = re.compile(r"<command-name>(.*?)</command-name>")

# ビルトイン CLI コマンド（スキルではない）
_BUILTIN_COMMANDS = frozenset({
    "clear", "compact", "mcp", "init", "model", "login", "logout",
    "help", "config", "cost", "doctor", "memory", "permissions",
    "status", "terminal-setup", "bug", "listen", "review", "fast",
    "vim", "tasks",
})


def _classify_system_message(
    content: str,
) -> Union[None, Tuple[str, str]]:
    """human メッセージをシステムメッセージかどうか分類する。

    Returns:
        None — 除外（user_prompts / user_intents に記録しない）
        ("skill-invocation", name) — コマンド名を抽出して記録
        ("passthrough", content) — 通常のユーザープロンプトとして処理
    """
    stripped = content.strip()

    # 中断シグナル（prefix マッチ）
    if stripped.startswith("[Request interrupted"):
        return None

    # ローカルコマンド出力
    if "<local-command-" in stripped:
        return None

    # タスク通知
    if "<task-notification>" in stripped:
        return None

    # コマンドタグ → スキル名抽出
    if "<command-name>" in stripped:
        m = _COMMAND_NAME_RE.search(stripped)
        if m and m.group(1).strip():
            cmd = m.group(1).strip().lstrip("/")
            # ビルトイン CLI コマンドはスキルではない
            if cmd in _BUILTIN_COMMANDS:
                return None
            return ("skill-invocation", m.group(1).strip())
        # パース失敗 → 除外
        return None

    # 通常のユーザープロンプト
    return ("passthrough", content)


@dataclass
class ParseResult:
    """parse_transcript() の戻り値。"""
    usage_records: list = field(default_factory=list)
    workflow_records: list = field(default_factory=list)
    error_records: list = field(default_factory=list)
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


def remove_backfill_errors(session_ids: Set[str]) -> None:
    """errors.jsonl から対象プロジェクトの backfill レコードを削除する。"""
    _remove_backfill_from_jsonl(common.DATA_DIR / "errors.jsonl", session_ids)


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


def _finalize_burst(
    burst_buffer: List[Dict[str, Any]],
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """burst バッファからワークフローレコードを生成する。2 Agent 未満なら None。"""
    if len(burst_buffer) < 2:
        return None
    workflow = {
        "workflow_id": _generate_workflow_id(),
        "workflow_type": "agent-burst",
        "skill_name": None,
        "team_name": None,
        "session_id": session_id,
        "started_at": burst_buffer[0].get("timestamp", ""),
    }
    return _finalize_workflow(workflow, burst_buffer)


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

    # Team-driven ワークフロー追跡
    in_team: bool = False
    team_name_val: Optional[str] = None
    team_workflow: Optional[Dict[str, Any]] = None
    team_steps: List[Dict[str, Any]] = []
    team_workflow_id: Optional[str] = None

    # Agent-burst 追跡
    burst_buffer: List[Dict[str, Any]] = []

    # セッションメタデータ収集
    tool_sequence: List[str] = []
    tool_counts: Counter = Counter()
    timestamps: List[str] = []
    error_count = 0
    human_message_count = 0
    user_intents: List[str] = []
    user_prompts: List[str] = []
    filtered_messages = 0
    thinking_count = 0
    compact_count = 0
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
                # content からテキストを取り出す
                raw_text = ""
                if isinstance(content, str) and content.strip():
                    raw_text = content
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text.strip():
                                raw_text = text
                                break  # 最初の text ブロックのみ

                if raw_text:
                    classification = _classify_system_message(raw_text)
                    if classification is None:
                        # システムメッセージ → 除外
                        filtered_messages += 1
                    elif classification[0] == "skill-invocation":
                        # コマンドタグ → スキル名を記録
                        user_intents.append("skill-invocation")
                        user_prompts.append(classification[1])

                        # ワークフローアンカー: command-name もスキル起動として扱う
                        cmd_skill = classification[1].lstrip("/")
                        if cmd_skill and not in_team:
                            # pending burst を確定
                            burst_wf = _finalize_burst(burst_buffer, session_id)
                            if burst_wf is not None:
                                result.workflow_records.append(burst_wf)
                            burst_buffer = []

                            # 前の skill-driven ワークフローを確定
                            if current_workflow is not None:
                                wf_rec = _finalize_workflow(current_workflow, current_steps)
                                if wf_rec is not None:
                                    result.workflow_records.append(wf_rec)

                            # 新しい skill-driven ワークフロー開始
                            current_workflow_id = _generate_workflow_id()
                            current_skill_name = cmd_skill
                            current_workflow = {
                                "workflow_id": current_workflow_id,
                                "workflow_type": "skill-driven",
                                "skill_name": cmd_skill,
                                "session_id": session_id,
                                "started_at": timestamp,
                            }
                            current_steps = []

                            # usage レコード
                            result.usage_records.append({
                                "skill_name": cmd_skill,
                                "timestamp": timestamp,
                                "session_id": session_id,
                                "file_path": "",
                                "source": "backfill",
                            })
                    else:
                        # 通常プロンプト → 従来どおり分類
                        truncated = classification[1][:MAX_PROMPT_LENGTH]
                        user_intents.append(common.classify_prompt(truncated))
                        user_prompts.append(truncated)
            continue

        # system レコードからエラー・コンパクト情報を収集
        if record_type == "system":
            subtype = record.get("subtype", "")
            if subtype == "api_error":
                error_count += 1
                result.error_records.append({
                    "tool_name": "",
                    "skill_name": "",
                    "error": str(record.get("message", ""))[:500],
                    "timestamp": timestamp,
                    "session_id": session_id,
                    "source": "backfill",
                })
            elif subtype == "compact_boundary":
                compact_count += 1
            continue

        # tool_result の is_error チェック（旧フォーマット互換）
        if record_type == "tool_result":
            if record.get("is_error"):
                error_count += 1
                # tool_name は直前の assistant ターンの tool_use から推定
                error_content = record.get("content", "")
                if isinstance(error_content, list):
                    error_content = " ".join(
                        b.get("text", "") for b in error_content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                result.error_records.append({
                    "tool_name": record.get("tool_use_id", ""),
                    "skill_name": "",
                    "error": str(error_content)[:500],
                    "timestamp": timestamp,
                    "session_id": session_id,
                    "source": "backfill",
                })
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
            if not isinstance(block, dict):
                continue
            if block.get("type") == "thinking":
                thinking_count += 1
                continue
            if block.get("type") != "tool_use":
                continue

            tool_name = block.get("name", "")
            tool_input = block.get("input", {})
            if not isinstance(tool_input, dict):
                continue

            # 全ツール名を記録
            tool_sequence.append(tool_name)
            tool_counts[tool_name] += 1

            if tool_name == "TeamCreate":
                # pending burst を確定
                burst_wf = _finalize_burst(burst_buffer, session_id)
                if burst_wf is not None:
                    result.workflow_records.append(burst_wf)
                burst_buffer = []

                # skill-driven を確定
                if current_workflow is not None:
                    wf_rec = _finalize_workflow(current_workflow, current_steps)
                    if wf_rec is not None:
                        result.workflow_records.append(wf_rec)
                    current_workflow = None
                    current_steps = []
                    current_workflow_id = None
                    current_skill_name = None

                # team-driven モード開始
                in_team = True
                team_name_val = tool_input.get("team_name", "unknown")
                team_workflow_id = _generate_workflow_id()
                team_workflow = {
                    "workflow_id": team_workflow_id,
                    "workflow_type": "team-driven",
                    "skill_name": None,
                    "team_name": team_name_val,
                    "session_id": session_id,
                    "started_at": timestamp,
                }
                team_steps = []

            elif tool_name == "TeamDelete":
                # team-driven を確定
                if in_team and team_workflow is not None:
                    wf_rec = _finalize_workflow(team_workflow, team_steps)
                    if wf_rec is not None:
                        result.workflow_records.append(wf_rec)
                in_team = False
                team_name_val = None
                team_workflow = None
                team_steps = []
                team_workflow_id = None

            elif tool_name == "Skill":
                skill_name = tool_input.get("skill", "unknown")

                if in_team:
                    # Team 内の Skill → usage レコードのみ（skill-driven ワークフロー不生成）
                    result.usage_records.append({
                        "skill_name": skill_name,
                        "timestamp": timestamp,
                        "session_id": session_id,
                        "file_path": tool_input.get("args", ""),
                        "source": "backfill",
                    })
                elif (current_workflow is not None
                      and current_skill_name == skill_name
                      and not current_steps):
                    # command-name で既にアンカー済み → 重複スキップ
                    pass
                else:
                    # pending burst を確定
                    burst_wf = _finalize_burst(burst_buffer, session_id)
                    if burst_wf is not None:
                        result.workflow_records.append(burst_wf)
                    burst_buffer = []

                    # 前の skill-driven ワークフローを確定
                    if current_workflow is not None:
                        wf_rec = _finalize_workflow(current_workflow, current_steps)
                        if wf_rec is not None:
                            result.workflow_records.append(wf_rec)

                    # 新しい skill-driven ワークフロー開始
                    current_workflow_id = _generate_workflow_id()
                    current_skill_name = skill_name
                    current_workflow = {
                        "workflow_id": current_workflow_id,
                        "workflow_type": "skill-driven",
                        "skill_name": skill_name,
                        "session_id": session_id,
                        "started_at": timestamp,
                    }
                    current_steps = []

                    # Skill 自身の usage レコード
                    result.usage_records.append({
                        "skill_name": skill_name,
                        "timestamp": timestamp,
                        "session_id": session_id,
                        "file_path": tool_input.get("args", ""),
                        "source": "backfill",
                    })

            elif tool_name in ("Agent", "Task"):
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

                step_info = {
                    "tool": f"Agent:{subagent_type}",
                    "intent_category": common.classify_prompt(prompt),
                    "timestamp": timestamp,
                }

                if in_team:
                    # Team-driven Agent
                    agent_record["parent_skill"] = None
                    agent_record["workflow_id"] = team_workflow_id
                    team_steps.append(step_info)
                elif current_workflow is not None:
                    # Skill-driven Agent（既存動作）
                    agent_record["parent_skill"] = current_skill_name
                    agent_record["workflow_id"] = current_workflow_id
                    current_steps.append(step_info)
                else:
                    # Ad-hoc Agent → burst 候補
                    agent_record["parent_skill"] = None
                    agent_record["workflow_id"] = None

                    if burst_buffer:
                        last_ts = _parse_iso_timestamp(burst_buffer[-1]["timestamp"])
                        curr_ts = _parse_iso_timestamp(timestamp)
                        if last_ts and curr_ts:
                            gap = (curr_ts - last_ts).total_seconds()
                            if gap > AGENT_BURST_GAP_SECONDS:
                                # gap が閾値超過 → 現在の burst を確定
                                burst_wf = _finalize_burst(burst_buffer, session_id)
                                if burst_wf is not None:
                                    result.workflow_records.append(burst_wf)
                                burst_buffer = [step_info]
                            else:
                                burst_buffer.append(step_info)
                        else:
                            burst_buffer.append(step_info)
                    else:
                        burst_buffer.append(step_info)

                result.usage_records.append(agent_record)

    # 最後の team-driven ワークフローを確定
    if in_team and team_workflow is not None:
        wf_rec = _finalize_workflow(team_workflow, team_steps)
        if wf_rec is not None:
            result.workflow_records.append(wf_rec)

    # 最後の skill-driven ワークフローを確定
    if current_workflow is not None:
        wf_rec = _finalize_workflow(current_workflow, current_steps)
        if wf_rec is not None:
            result.workflow_records.append(wf_rec)

    # 最後の agent-burst を確定
    burst_wf = _finalize_burst(burst_buffer, session_id)
    if burst_wf is not None:
        result.workflow_records.append(burst_wf)

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
            "user_prompts": user_prompts,
            "filtered_messages": filtered_messages,
            "thinking_count": thinking_count,
            "compact_count": compact_count,
            "plan_mode_count": tool_counts.get("EnterPlanMode", 0),
            "source": "backfill",
        }

    return result


def _extract_human_text(record: Dict[str, Any]) -> str:
    """human/user レコードからテキストを抽出する。"""
    message = record.get("message", {})
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text.strip():
                    return text
    return ""


# ツール拒否検出マーカー
_TOOL_REJECTION_MARKERS = [
    "The user doesn't want to proceed",
    "the user said:",
]


def extract_corrections_from_transcript(filepath: Path) -> List[Dict[str, Any]]:
    """トランスクリプトから修正パターンを遡及抽出する。

    human メッセージに修正パターンが検出された場合、直前の assistant ターンで
    使われた Skill を特定して correction レコードを生成する。
    拡張スキーマ: matched_patterns, project_path, sentiment, decay_days,
    routing_hint, guardrail, reflect_status, extracted_learning を含む。

    ツール拒否（"The user doesn't want to proceed" + "the user said:"）も
    correction_type: "tool-rejection" として抽出する。
    """
    corrections = []
    last_skill_name: Optional[str] = None
    session_id = ""
    project_path = str(filepath.parent)

    for line in filepath.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        record_type = record.get("type", "")
        timestamp = record.get("timestamp", "")
        if not session_id:
            session_id = record.get("sessionId", "")

        # assistant ターンから最後の Skill 呼び出しを追跡 + ツール拒否検出
        if record_type == "assistant":
            message = record.get("message", {})
            if isinstance(message, dict):
                content = message.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "tool_use":
                            tool_name = block.get("name", "")
                            tool_input = block.get("input", {})
                            if tool_name == "Skill" and isinstance(tool_input, dict):
                                last_skill_name = tool_input.get("skill")
                        elif block.get("type") == "text":
                            text_content = block.get("text", "")
                            if all(marker in text_content for marker in _TOOL_REJECTION_MARKERS):
                                corrections.append({
                                    "correction_type": "tool-rejection",
                                    "matched_patterns": ["tool-rejection"],
                                    "message": text_content[:MAX_PROMPT_LENGTH].strip(),
                                    "last_skill": last_skill_name,
                                    "confidence": 0.80,
                                    "decay_days": 60,
                                    "sentiment": "negative",
                                    "routing_hint": "guardrail",
                                    "guardrail": True,
                                    "reflect_status": "pending",
                                    "extracted_learning": "",
                                    "project_path": project_path,
                                    "timestamp": timestamp,
                                    "session_id": session_id,
                                    "source": "backfill",
                                })

        # human メッセージから修正パターンを検出
        elif record_type in ("human", "user"):
            raw_text = _extract_human_text(record)

            if raw_text and common.should_include_message(raw_text):
                matched_patterns = common.detect_all_patterns(raw_text)
                if matched_patterns:
                    # 最初のマッチから correction_type を決定（後方互換）
                    result = common.detect_correction(raw_text)
                    if result is not None:
                        correction_type, base_confidence = result

                        # パターン情報を取得
                        pattern_info = common.CORRECTION_PATTERNS.get(correction_type, {})
                        pattern_type = pattern_info.get("type", "correction")
                        has_strong = any(
                            common.CORRECTION_PATTERNS.get(p, {}).get("strong", False)
                            for p in matched_patterns
                        )
                        has_i_told_you = "I-told-you" in matched_patterns

                        # 信頼度計算
                        confidence, decay_days = common.calculate_confidence(
                            base_confidence, raw_text,
                            matched_count=len(matched_patterns),
                            has_strong=has_strong,
                            has_i_told_you=has_i_told_you,
                        )

                        # sentiment 判定
                        if pattern_type == "positive":
                            sentiment = "positive"
                        elif pattern_type in ("guardrail", "explicit"):
                            sentiment = "negative"
                        else:
                            sentiment = "negative"

                        # routing_hint 判定
                        if pattern_type == "guardrail":
                            routing_hint = "guardrail"
                        elif pattern_type == "explicit":
                            routing_hint = "rule"
                        elif pattern_type == "positive":
                            routing_hint = "reinforce"
                        else:
                            routing_hint = "correction"

                        corrections.append({
                            "correction_type": correction_type,
                            "matched_patterns": matched_patterns,
                            "message": raw_text.strip(),
                            "last_skill": last_skill_name,
                            "confidence": confidence,
                            "decay_days": decay_days,
                            "sentiment": sentiment,
                            "routing_hint": routing_hint,
                            "guardrail": pattern_type == "guardrail",
                            "reflect_status": "pending",
                            "extracted_learning": "",
                            "project_path": project_path,
                            "timestamp": timestamp,
                            "session_id": session_id,
                            "source": "backfill",
                        })

    return corrections


def backfill(project_dir: Optional[str] = None, force: bool = False, corrections: bool = False) -> Dict[str, int]:
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
        remove_backfill_errors(project_session_ids)
        backfilled_sessions: Set[str] = set()
    else:
        backfilled_sessions = get_backfilled_session_ids()

    summary: Dict[str, Any] = {
        "sessions_processed": 0,
        "skill_calls": 0,
        "agent_calls": 0,
        "workflows": 0,
        "workflows_by_type": {"skill-driven": 0, "team-driven": 0, "agent-burst": 0},
        "sessions": 0,
        "errors": 0,
        "error_records": 0,
        "skipped_sessions": 0,
        "filtered_messages": 0,
        "corrections_extracted": 0,
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
            rec["project"] = proj_name
            if rec.get("skill_name", "").startswith("Agent:"):
                summary["agent_calls"] += 1
            else:
                summary["skill_calls"] += 1
            common.append_jsonl(common.DATA_DIR / "usage.jsonl", rec)

        for wf_rec in parse_result.workflow_records:
            wf_rec["project"] = proj_name
            summary["workflows"] += 1
            wf_type = wf_rec.get("workflow_type", "skill-driven")
            if wf_type in summary["workflows_by_type"]:
                summary["workflows_by_type"][wf_type] += 1
            common.append_jsonl(common.DATA_DIR / "workflows.jsonl", wf_rec)

        for err_rec in parse_result.error_records:
            err_rec["project"] = proj_name
            summary["error_records"] += 1
            common.append_jsonl(common.DATA_DIR / "errors.jsonl", err_rec)

        if parse_result.session_meta is not None:
            parse_result.session_meta["project_name"] = proj_name
            parse_result.session_meta["project"] = proj_name
            summary["sessions"] += 1
            summary["filtered_messages"] += parse_result.session_meta.get("filtered_messages", 0)
            common.append_jsonl(common.DATA_DIR / "sessions.jsonl", parse_result.session_meta)

        # --corrections: 修正パターンの遡及抽出
        if corrections:
            corr_records = extract_corrections_from_transcript(tf)
            for corr in corr_records:
                common.append_jsonl(common.DATA_DIR / "corrections.jsonl", corr)
                summary["corrections_extracted"] += 1

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
    parser.add_argument(
        "--corrections",
        action="store_true",
        help="修正パターンを遡及抽出し corrections.jsonl に追記する",
    )
    args = parser.parse_args()

    try:
        summary = backfill(project_dir=args.project_dir, force=args.force, corrections=args.corrections)
        print(json.dumps(summary, ensure_ascii=False))
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
