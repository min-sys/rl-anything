"""Auto-evolve trigger engine — セッション終了・corrections 蓄積時のトリガー評価。

トリガー条件の統合判定、クールダウン管理、ユーザー設定の読み込みを提供する。
LLM 呼び出しは行わない（MUST NOT）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path.home() / ".claude" / "rl-anything"
EVOLVE_STATE_FILE = DATA_DIR / "evolve-state.json"
PENDING_TRIGGER_FILE = DATA_DIR / "pending-trigger.json"

# History pruning limit
_MAX_HISTORY_ENTRIES = 100

# Default trigger config
DEFAULT_TRIGGER_CONFIG: dict[str, Any] = {
    "enabled": True,
    "triggers": {
        "session_end": {"enabled": True, "min_sessions": 10, "max_days": 7},
        "corrections": {"enabled": True, "threshold": 10},
        "audit_overdue": {"enabled": True, "interval_days": 30},
        "bloat": {"enabled": True},
    },
    "cooldown_hours": 24,
}

# First-run threshold (evolve-state.json missing)
_FIRST_RUN_MIN_SESSIONS = 3


@dataclass
class TriggerResult:
    """トリガー評価結果。"""

    triggered: bool = False
    reason: str = ""
    action: str = ""
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def _load_state() -> dict[str, Any]:
    """evolve-state.json を読み込む。存在しない場合は空 dict。"""
    if not EVOLVE_STATE_FILE.exists():
        return {}
    try:
        return json.loads(EVOLVE_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    """evolve-state.json に保存する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVOLVE_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_trigger_config(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """trigger_config を読み込み、デフォルト値とマージして返す。"""
    if state is None:
        state = _load_state()
    user_config = state.get("trigger_config", {})
    # Deep merge: default <- user
    config = _deep_merge(DEFAULT_TRIGGER_CONFIG, user_config)
    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (shallow copy)."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


# --- Cooldown management ---


def _is_in_cooldown(
    state: dict[str, Any], reason: str, cooldown_hours: float
) -> bool:
    """同一 reason のトリガーがクールダウン期間内に発火済みか判定する。"""
    history = state.get("trigger_history", [])
    now = datetime.now(timezone.utc)
    for entry in reversed(history):
        if entry.get("reason") != reason:
            continue
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            elapsed_hours = (now - ts).total_seconds() / 3600
            if elapsed_hours < cooldown_hours:
                return True
        except (KeyError, ValueError):
            continue
    return False


def _record_trigger(state: dict[str, Any], result: TriggerResult) -> dict[str, Any]:
    """トリガー発火を trigger_history に記録し、pruning する。"""
    history = state.get("trigger_history", [])
    history.append(
        {
            "reason": result.reason,
            "action": result.action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    # Pruning: keep only the latest entries
    if len(history) > _MAX_HISTORY_ENTRIES:
        history = history[-_MAX_HISTORY_ENTRIES:]
    state["trigger_history"] = history
    return state


# --- Session count helper ---


def _count_sessions_since(last_run: str) -> int:
    """前回 evolve 以降のセッション数をカウントする。"""
    sessions_file = DATA_DIR / "sessions.jsonl"
    if not sessions_file.exists():
        return 0
    session_ids: set[str] = set()
    for line in sessions_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "")
            if ts > last_run:
                sid = rec.get("session_id", "")
                if sid:
                    session_ids.add(sid)
        except json.JSONDecodeError:
            continue
    return len(session_ids)


# --- Evaluate: session end ---


def _evaluate_bloat(project_dir: str, config: dict[str, Any]) -> dict[str, Any] | None:
    """bloat_check() を呼び出し、警告を返す。ImportError/例外時は None。"""
    triggers_cfg = config.get("triggers", {})
    bloat_cfg = triggers_cfg.get("bloat", {})
    if not bloat_cfg.get("enabled", True):
        return None
    try:
        from scripts.bloat_control import bloat_check
    except ImportError:
        return None
    try:
        result = bloat_check(project_dir)
        if result and result.get("warning_count", 0) > 0:
            return result
        return None
    except Exception:
        return None


def _build_bloat_message(bloat_result: dict[str, Any]) -> str:
    """bloat 警告から日本語メッセージを生成する。"""
    parts: list[str] = []
    for w in bloat_result.get("warnings", []):
        t = w.get("type", "")
        if t == "memory":
            parts.append(f"MEMORY.md が {w['lines']}/{w['threshold']} 行で超過")
        elif t == "claude_md":
            parts.append(f"CLAUDE.md が {w['lines']}/{w['threshold']} 行で超過")
        elif t == "rules_count":
            parts.append(f"rules が {w['count']}/{w['threshold']} 件で超過")
        elif t == "skills_count":
            parts.append(f"skills が {w['count']}/{w['threshold']} 件で超過")
    return "、".join(parts)


def evaluate_session_end(state: dict[str, Any] | None = None, *, project_dir: str | None = None) -> TriggerResult:
    """セッション終了時のトリガー条件を評価する。

    条件 (OR):
    1. 前回 evolve からのセッション数 >= min_sessions
    2. 前回 evolve からの経過日数 >= max_days
    3. 前回 audit からの経過日数 >= interval_days (audit_overdue)
    """
    if state is None:
        state = _load_state()

    config = load_trigger_config(state)
    if not config.get("enabled", True):
        return TriggerResult(triggered=False)

    cooldown_hours = config.get("cooldown_hours", 24)
    triggers_cfg = config.get("triggers", {})
    last_run = state.get("last_run_timestamp", "")
    now = datetime.now(timezone.utc)
    reasons: list[str] = []
    actions: list[str] = []
    details: dict[str, Any] = {}

    # --- audit_overdue (check first, independent action) ---
    audit_cfg = triggers_cfg.get("audit_overdue", {})
    audit_triggered = False
    if audit_cfg.get("enabled", True):
        interval_days = audit_cfg.get("interval_days", 30)
        last_audit = state.get("last_audit_timestamp", "")
        if not last_audit:
            # No previous audit → overdue
            audit_triggered = True
            details["audit_overdue"] = True
        else:
            try:
                last_audit_dt = datetime.fromisoformat(last_audit)
                elapsed = (now - last_audit_dt).total_seconds() / 86400
                if elapsed >= interval_days:
                    audit_triggered = True
                    details["audit_days_elapsed"] = round(elapsed, 1)
            except ValueError:
                audit_triggered = True

        if audit_triggered and not _is_in_cooldown(state, "audit_overdue", cooldown_hours):
            reasons.append("audit_overdue")
            actions.append("/rl-anything:audit")

    # --- session_end conditions ---
    se_cfg = triggers_cfg.get("session_end", {})
    if se_cfg.get("enabled", True):
        min_sessions = se_cfg.get("min_sessions", 10)
        max_days = se_cfg.get("max_days", 7)

        # Handle first run (no evolve-state.json)
        if not last_run:
            min_sessions = _FIRST_RUN_MIN_SESSIONS

        session_count = _count_sessions_since(last_run)
        details["session_count"] = session_count

        session_triggered = session_count >= min_sessions
        days_triggered = False

        if last_run:
            try:
                last_run_dt = datetime.fromisoformat(last_run)
                elapsed = (now - last_run_dt).total_seconds() / 86400
                details["days_since_evolve"] = round(elapsed, 1)
                if elapsed >= max_days:
                    days_triggered = True
            except ValueError:
                pass

        if session_triggered and not _is_in_cooldown(state, "session_count", cooldown_hours):
            reasons.append("session_count")
            actions.append("/rl-anything:evolve")
        if days_triggered and not _is_in_cooldown(state, "days_elapsed", cooldown_hours):
            reasons.append("days_elapsed")
            actions.append("/rl-anything:evolve")

    # --- bloat ---
    if project_dir and not _is_in_cooldown(state, "bloat", cooldown_hours):
        bloat_result = _evaluate_bloat(project_dir, config)
        if bloat_result:
            reasons.append("bloat")
            actions.append("/rl-anything:evolve")
            details["bloat_warnings"] = bloat_result["warnings"]

    if not reasons:
        return TriggerResult(triggered=False)

    # Build message
    primary_action = actions[0]
    unique_actions = list(dict.fromkeys(actions))
    msg_parts = []
    if "session_count" in reasons:
        msg_parts.append(f"前回 evolve から {details.get('session_count', '?')} セッション経過")
    if "days_elapsed" in reasons:
        msg_parts.append(f"前回 evolve から {details.get('days_since_evolve', '?')} 日経過")
    if "audit_overdue" in reasons:
        msg_parts.append("前回 audit から規定日数を超過")
    if "bloat" in reasons and "bloat_warnings" in details:
        msg_parts.append(f"肥大化検出: {_build_bloat_message({'warnings': details['bloat_warnings']})}")
    message = "。".join(msg_parts) + f"。推奨: {', '.join(unique_actions)}"

    result = TriggerResult(
        triggered=True,
        reason=reasons[0],  # primary reason
        action=primary_action,
        message=message,
        details={**details, "all_reasons": reasons, "all_actions": unique_actions},
    )

    # Record and save
    state = _record_trigger(state, result)
    _save_state(state)
    return result


# --- Evaluate: corrections ---


def evaluate_corrections(state: dict[str, Any] | None = None) -> TriggerResult:
    """Corrections 蓄積閾値のトリガーを評価する。"""
    if state is None:
        state = _load_state()

    config = load_trigger_config(state)
    if not config.get("enabled", True):
        return TriggerResult(triggered=False)

    triggers_cfg = config.get("triggers", {})
    corr_cfg = triggers_cfg.get("corrections", {})
    if not corr_cfg.get("enabled", True):
        return TriggerResult(triggered=False)

    cooldown_hours = config.get("cooldown_hours", 24)
    if _is_in_cooldown(state, "corrections_threshold", cooldown_hours):
        return TriggerResult(triggered=False, reason="cooldown")

    threshold = corr_cfg.get("threshold", 10)
    last_run = state.get("last_run_timestamp", "")

    # Count corrections since last evolve/reflect
    corrections_file = DATA_DIR / "corrections.jsonl"
    if not corrections_file.exists():
        return TriggerResult(triggered=False)

    count = 0
    skill_counts: dict[str, int] = {}
    for line in corrections_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "")
            if ts > last_run:
                count += 1
                skill = rec.get("last_skill", "")
                if skill:
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1
        except json.JSONDecodeError:
            continue

    if count < threshold:
        return TriggerResult(triggered=False, details={"corrections_count": count})

    # Top 3 skills
    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    skill_names = [s[0] for s in top_skills]

    if skill_names:
        action = f"/rl-anything:optimize {skill_names[0]}"
        skill_list = ", ".join(skill_names)
        message = f"Corrections が {count} 件蓄積。関連スキル: {skill_list}。推奨: {action}"
    else:
        action = "/rl-anything:evolve"
        message = f"Corrections が {count} 件蓄積。推奨: {action}"

    result = TriggerResult(
        triggered=True,
        reason="corrections_threshold",
        action=action,
        message=message,
        details={
            "corrections_count": count,
            "top_skills": skill_names,
        },
    )

    state = _record_trigger(state, result)
    _save_state(state)
    return result


# --- Evaluate: self-evolution ---


def _evaluate_self_evolution(state: dict[str, Any] | None = None) -> TriggerResult:
    """False positive 蓄積に基づく self-evolution トリガーを評価する。"""
    if state is None:
        state = _load_state()

    config = load_trigger_config(state)
    if not config.get("enabled", True):
        return TriggerResult(triggered=False)

    # Load self-evolution config
    se_config = state.get("trigger_config", {}).get("self_evolution", {})
    fp_threshold = se_config.get("false_positive_rate_threshold", 0.3)
    min_per_type = se_config.get("min_outcomes_per_type", 10)
    cooldown_hours = se_config.get("self_evolution_cooldown_hours", 72)
    lookback_days = se_config.get("analysis_lookback_days", 30)

    if _is_in_cooldown(state, "self_evolution", cooldown_hours):
        return TriggerResult(triggered=False, reason="cooldown")

    # Load outcomes
    outcomes_file = DATA_DIR / "remediation-outcomes.jsonl"
    if not outcomes_file.exists():
        return TriggerResult(triggered=False)

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=lookback_days)).isoformat()

    by_type: dict[str, dict[str, int]] = {}
    for line in outcomes_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("timestamp", "") < cutoff:
            continue
        it = rec.get("issue_type", "unknown")
        if it not in by_type:
            by_type[it] = {"total": 0, "rejected": 0, "skipped": 0}
        by_type[it]["total"] += 1
        decision = rec.get("user_decision", rec.get("result", ""))
        if decision == "rejected":
            by_type[it]["rejected"] += 1
        elif decision == "skipped":
            by_type[it]["skipped"] += 1

    # Check if any type exceeds threshold
    triggered_types: list[str] = []
    for it, stats in by_type.items():
        if stats["total"] < min_per_type:
            continue
        fp_rate = (stats["rejected"] + stats["skipped"]) / stats["total"]
        if fp_rate >= fp_threshold:
            triggered_types.append(it)

    if not triggered_types:
        return TriggerResult(triggered=False)

    result = TriggerResult(
        triggered=True,
        reason="self_evolution",
        action="/rl-anything:evolve",
        message=f"False positive 蓄積検出: {', '.join(triggered_types)}。self-evolution を推奨。",
        details={"triggered_types": triggered_types},
    )
    state = _record_trigger(state, result)
    _save_state(state)
    return result


def _evaluate_approval_rate_decline(state: dict[str, Any] | None = None) -> TriggerResult:
    """承認率の継続的低下に基づくトリガーを評価する。"""
    if state is None:
        state = _load_state()

    config = load_trigger_config(state)
    if not config.get("enabled", True):
        return TriggerResult(triggered=False)

    se_config = state.get("trigger_config", {}).get("self_evolution", {})
    decline_threshold = se_config.get("approval_rate_decline_threshold", 0.2)
    sample_size = se_config.get("decline_sample_size", 10)
    cooldown_hours = se_config.get("self_evolution_cooldown_hours", 72)

    if _is_in_cooldown(state, "approval_rate_decline", cooldown_hours):
        return TriggerResult(triggered=False, reason="cooldown")

    outcomes_file = DATA_DIR / "remediation-outcomes.jsonl"
    if not outcomes_file.exists():
        return TriggerResult(triggered=False)

    records: list[dict[str, Any]] = []
    for line in outcomes_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # Need at least 2 * sample_size records
    if len(records) < 2 * sample_size:
        return TriggerResult(triggered=False)

    recent = records[-sample_size:]
    previous = records[-(2 * sample_size):-sample_size]

    def _approval_rate(recs: list[dict[str, Any]]) -> float:
        if not recs:
            return 0.0
        approved = sum(
            1 for r in recs
            if r.get("user_decision") == "approved" or r.get("result") == "success"
        )
        return approved / len(recs)

    recent_rate = _approval_rate(recent)
    previous_rate = _approval_rate(previous)
    decline = previous_rate - recent_rate

    if decline < decline_threshold:
        return TriggerResult(triggered=False)

    result = TriggerResult(
        triggered=True,
        reason="approval_rate_decline",
        action="/rl-anything:evolve",
        message=(
            f"承認率低下検出: {previous_rate:.0%} → {recent_rate:.0%} "
            f"(Δ{decline:.0%})。self-evolution を推奨。"
        ),
        details={
            "previous_rate": round(previous_rate, 4),
            "recent_rate": round(recent_rate, 4),
            "decline": round(decline, 4),
        },
    )
    state = _record_trigger(state, result)
    _save_state(state)
    return result


# --- Pending trigger file management ---


def write_pending_trigger(result: TriggerResult) -> None:
    """pending-trigger.json にトリガー結果を書き出す。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "triggered": result.triggered,
        "reason": result.reason,
        "action": result.action,
        "message": result.message,
        "details": result.details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    PENDING_TRIGGER_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_and_delete_pending_trigger() -> dict[str, Any] | None:
    """pending-trigger.json を読み取り、削除する。存在しない場合は None。"""
    if not PENDING_TRIGGER_FILE.exists():
        return None
    try:
        data = json.loads(PENDING_TRIGGER_FILE.read_text(encoding="utf-8"))
        PENDING_TRIGGER_FILE.unlink()
        return data
    except (json.JSONDecodeError, OSError):
        # Read error: delete and return None
        try:
            PENDING_TRIGGER_FILE.unlink()
        except OSError:
            pass
        return None


# --- Skill change detection ---


def detect_skill_changes() -> list[str]:
    """git diff で .claude/skills/*/SKILL.md の変更を検出する。"""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--", ".claude/skills/*/SKILL.md"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        changed = []
        for line in result.stdout.strip().splitlines():
            # Extract skill name from path like .claude/skills/my-skill/SKILL.md
            parts = line.split("/")
            if len(parts) >= 4:
                changed.append(parts[2])
        return changed
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []
