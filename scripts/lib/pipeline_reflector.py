"""Pipeline Reflector — evolve パイプラインの自己改善モジュール。

remediation-outcomes.jsonl の分析、confidence キャリブレーション、
パイプラインパラメータ調整提案を提供する。LLM 呼び出しは診断生成時のみ。
"""
from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path.home() / ".claude" / "rl-anything"
OUTCOMES_FILE = DATA_DIR / "remediation-outcomes.jsonl"
CALIBRATION_FILE = DATA_DIR / "confidence-calibration.json"
PROPOSALS_FILE = DATA_DIR / "pipeline-proposals.jsonl"

# --- D6: Default self-evolution config ---

DEFAULT_SELF_EVOLUTION_CONFIG: dict[str, Any] = {
    "min_outcomes_for_analysis": 20,
    "min_outcomes_per_type": 10,
    "calibration_sample_threshold": 30,
    "max_calibration_alpha": 0.7,
    "false_positive_rate_threshold": 0.3,
    "approval_rate_healthy_threshold": 0.8,
    "approval_rate_degraded_threshold": 0.7,
    "approval_rate_decline_threshold": 0.2,
    "self_evolution_cooldown_hours": 72,
    "decline_sample_size": 10,
    "regression_fp_increase_threshold": 0.1,
    "analysis_lookback_days": 30,
    "systematic_rejection_threshold": 3,
    "minor_line_excess": 2,
}


def load_self_evolution_config(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """self_evolution config を evolve-state.json から読み込み、デフォルトとマージして返す。

    trigger_engine.py の load_trigger_config() パターン準拠。
    """
    if state is None:
        state = _load_state()
    user_config = state.get("trigger_config", {}).get("self_evolution", {})
    config = dict(DEFAULT_SELF_EVOLUTION_CONFIG)
    config.update(user_config)
    return config


def _load_state() -> dict[str, Any]:
    """evolve-state.json を読み込む。"""
    state_file = DATA_DIR / "evolve-state.json"
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# --- Outcome loading ---


def load_outcomes(*, lookback_days: int | None = None) -> list[dict[str, Any]]:
    """remediation-outcomes.jsonl を読み込む。"""
    if not OUTCOMES_FILE.exists():
        return []
    records = []
    cutoff = None
    if lookback_days is not None:
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        cutoff_dt = now - timedelta(days=lookback_days)
        cutoff = cutoff_dt.isoformat()
    for line in OUTCOMES_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            if cutoff and rec.get("timestamp", "") < cutoff:
                continue
            records.append(rec)
        except json.JSONDecodeError:
            continue
    return records


# --- 2.1: Trajectory Analysis ---


def analyze_trajectory(
    outcomes: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """remediation-outcomes を issue_type 別に集計し、パイプラインの弱点を分析する。

    Returns:
        {"sufficient": bool, "total": int, "by_type": {issue_type: {...}}, "diagnosis": str}
    """
    if config is None:
        config = load_self_evolution_config()
    if outcomes is None:
        lookback = config.get("analysis_lookback_days", 30)
        outcomes = load_outcomes(lookback_days=lookback)

    min_outcomes = config["min_outcomes_for_analysis"]
    total = len(outcomes)

    if total < min_outcomes:
        return {
            "sufficient": False,
            "total": total,
            "min_required": min_outcomes,
            "by_type": {},
            "diagnosis": f"データ不足（{total}/{min_outcomes} 件）",
        }

    by_type: dict[str, dict[str, Any]] = {}
    for rec in outcomes:
        it = rec.get("issue_type", "unknown")
        if it not in by_type:
            by_type[it] = {"total": 0, "approved": 0, "rejected": 0, "skipped": 0, "fix_failed": 0}
        by_type[it]["total"] += 1
        decision = rec.get("user_decision", rec.get("result", ""))
        if decision == "approved" or rec.get("result") == "success":
            by_type[it]["approved"] += 1
        elif decision == "rejected" or rec.get("result") == "rejected":
            by_type[it]["rejected"] += 1
        elif decision == "skipped" or rec.get("result") == "skipped":
            by_type[it]["skipped"] += 1
        if rec.get("result") == "fix_failed":
            by_type[it]["fix_failed"] += 1

    # Compute metrics
    for it, stats in by_type.items():
        t = stats["total"]
        if t > 0:
            stats["approval_rate"] = stats["approved"] / t
            stats["false_positive_rate"] = (stats["rejected"] + stats["skipped"]) / t
            stats["precision"] = stats["approved"] / t
        else:
            stats["approval_rate"] = 0.0
            stats["false_positive_rate"] = 0.0
            stats["precision"] = 0.0

    # Generate diagnosis
    diagnosis = _generate_diagnosis(by_type, config)

    return {
        "sufficient": True,
        "total": total,
        "min_required": min_outcomes,
        "by_type": by_type,
        "diagnosis": diagnosis,
    }


# --- 2.2: False positive detection ---


def detect_false_positives(
    outcomes: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """High-confidence rejection と systematic rejection パターンを検出する。"""
    if config is None:
        config = load_self_evolution_config()

    high_confidence_rejections: list[dict[str, Any]] = []
    systematic_rejections: dict[str, list[dict[str, Any]]] = {}
    threshold = config.get("systematic_rejection_threshold", 3)

    for rec in outcomes:
        confidence = rec.get("confidence_score", 0.0)
        decision = rec.get("user_decision", rec.get("result", ""))
        it = rec.get("issue_type", "unknown")
        category = rec.get("category", "")

        # High-confidence rejection
        if confidence >= 0.9 and decision in ("rejected", "skipped"):
            high_confidence_rejections.append(rec)

        # Systematic rejection tracking (proposable category)
        if category == "proposable" and decision in ("rejected", "skipped"):
            if it not in systematic_rejections:
                systematic_rejections[it] = []
            systematic_rejections[it].append(rec)

    # Check for consecutive systematic rejections
    systematic_flags: dict[str, int] = {}
    for it, recs in systematic_rejections.items():
        # Count consecutive rejections from the end
        consecutive = 0
        for rec in reversed(recs):
            if rec.get("user_decision", rec.get("result", "")) in ("rejected", "skipped"):
                consecutive += 1
            else:
                break
        if consecutive >= threshold:
            systematic_flags[it] = consecutive

    return {
        "high_confidence_rejections": high_confidence_rejections,
        "systematic_rejections": systematic_flags,
    }


# --- 2.3: Natural language diagnosis ---


def _generate_diagnosis(
    by_type: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> str:
    """分析結果をもとに自然言語診断を生成する。"""
    fp_threshold = config.get("false_positive_rate_threshold", 0.3)
    healthy_threshold = config.get("approval_rate_healthy_threshold", 0.8)

    problematic: list[str] = []
    for it, stats in by_type.items():
        if stats.get("false_positive_rate", 0) >= fp_threshold:
            rate = stats.get("approval_rate", 0)
            problematic.append(
                f"{it} の confidence_score が過大評価されています。"
                f"実績 approval_rate: {rate:.0%}。confidence の引き下げを推奨します。"
            )

    if not problematic:
        all_healthy = all(
            stats.get("approval_rate", 0) >= healthy_threshold
            for stats in by_type.values()
            if stats.get("total", 0) > 0
        )
        if all_healthy:
            return (
                "パイプラインは健全です。全 issue_type で承認率 "
                f"{healthy_threshold:.0%} 以上を維持しています。"
            )
        return "パイプラインは概ね健全です。"

    return "\n".join(problematic)


# --- 3.1: EWA Calibration ---


def calibrate_confidence(
    outcomes: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """issue_type 別の EWA キャリブレーションを算出する。

    Returns:
        {"calibrations": {issue_type: {current, calibrated, alpha, sample_size, approval_rate}}}
    """
    if config is None:
        config = load_self_evolution_config()
    if outcomes is None:
        lookback = config.get("analysis_lookback_days", 30)
        outcomes = load_outcomes(lookback_days=lookback)

    min_per_type = config["min_outcomes_per_type"]
    sample_threshold = config["calibration_sample_threshold"]
    max_alpha = config["max_calibration_alpha"]

    # Group by issue_type
    by_type: dict[str, list[dict[str, Any]]] = {}
    for rec in outcomes:
        it = rec.get("issue_type", "unknown")
        if it not in by_type:
            by_type[it] = []
        by_type[it].append(rec)

    calibrations: dict[str, dict[str, Any]] = {}
    for it, recs in by_type.items():
        if len(recs) < min_per_type:
            continue

        # Observed approval rate
        approved = sum(
            1 for r in recs
            if r.get("user_decision") == "approved" or r.get("result") == "success"
        )
        observed_rate = approved / len(recs)

        # Current confidence (average from records)
        confidences = [r.get("confidence_score", 0.5) for r in recs]
        current = statistics.mean(confidences) if confidences else 0.5

        # EWA: α = min(sample_size / threshold, max_alpha)
        alpha = min(len(recs) / sample_threshold, max_alpha)
        calibrated = alpha * observed_rate + (1 - alpha) * current

        calibrations[it] = {
            "current": round(current, 4),
            "calibrated": round(calibrated, 4),
            "alpha": round(alpha, 4),
            "sample_size": len(recs),
            "approval_rate": round(observed_rate, 4),
        }

    return {"calibrations": calibrations}


# --- 3.2: Calibration file I/O ---


def load_calibration() -> dict[str, Any]:
    """confidence-calibration.json を読み込む。"""
    if not CALIBRATION_FILE.exists():
        return {}
    try:
        return json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_calibration(data: dict[str, Any]) -> None:
    """confidence-calibration.json に保存する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CALIBRATION_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# --- 3.3: Control chart check ---


def check_control_chart(
    calibrations: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """μ ± 2σ 範囲外の delta に risk_level: "high" を付与する。

    Returns:
        {issue_type: {delta, mean_delta, std_delta, risk_level}}
    """
    deltas = []
    for it, cal in calibrations.items():
        delta = cal["calibrated"] - cal["current"]
        deltas.append((it, delta))

    if len(deltas) < 2:
        # 2件未満では標準偏差を計算できない → 全て low
        return {
            it: {"delta": d, "mean_delta": d, "std_delta": 0.0, "risk_level": "low"}
            for it, d in deltas
        }

    delta_values = [d for _, d in deltas]
    mean_d = statistics.mean(delta_values)
    std_d = statistics.stdev(delta_values)

    result = {}
    for it, d in deltas:
        if std_d > 0 and abs(d - mean_d) > 2 * std_d:
            risk = "high"
        else:
            risk = "low"
        result[it] = {
            "delta": round(d, 4),
            "mean_delta": round(mean_d, 4),
            "std_delta": round(std_d, 4),
            "risk_level": risk,
        }
    return result


# --- 3.4: Regression check ---


def check_calibration_regression(
    calibrations: dict[str, dict[str, Any]],
    outcomes: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """変更後 confidence で既存 outcomes を再分類し回帰検出。

    Returns:
        {"has_regression": bool, "regressions": {issue_type: {old_fp_rate, new_fp_rate, increase}}}
    """
    if config is None:
        config = load_self_evolution_config()
    fp_threshold = config.get("regression_fp_increase_threshold", 0.1)

    AUTO_FIX_CONFIDENCE = 0.9

    # Current FP rates by type
    by_type: dict[str, list[dict[str, Any]]] = {}
    for rec in outcomes:
        it = rec.get("issue_type", "unknown")
        if it not in by_type:
            by_type[it] = []
        by_type[it].append(rec)

    regressions: dict[str, dict[str, Any]] = {}
    for it, recs in by_type.items():
        if not recs:
            continue

        # Current classification-based FP: rejected/skipped among auto_fixable
        current_auto = [r for r in recs if r.get("category") == "auto_fixable"]
        current_fp = sum(
            1 for r in current_auto
            if r.get("user_decision") in ("rejected", "skipped")
        )
        current_fp_rate = current_fp / len(current_auto) if current_auto else 0.0

        # Re-classify with calibrated confidence
        cal = calibrations.get(it)
        if cal is None:
            continue
        new_confidence = cal["calibrated"]

        # Simulate: if new_confidence >= AUTO_FIX, more items become auto_fixable
        # If new_confidence < AUTO_FIX, fewer items are auto_fixable → FP should decrease
        # Check if this change causes other types to have more FP
        # Simplified: check if lowering confidence changes auto_fixable classification
        new_auto = [
            r for r in recs
            if new_confidence >= AUTO_FIX_CONFIDENCE
            and r.get("impact_scope", "file") in ("file", "project")
        ]
        if not new_auto:
            continue
        new_fp = sum(
            1 for r in new_auto
            if r.get("user_decision") in ("rejected", "skipped")
        )
        new_fp_rate = new_fp / len(new_auto) if new_auto else 0.0

        increase = new_fp_rate - current_fp_rate
        if increase >= fp_threshold:
            regressions[it] = {
                "old_fp_rate": round(current_fp_rate, 4),
                "new_fp_rate": round(new_fp_rate, 4),
                "increase": round(increase, 4),
            }

    return {
        "has_regression": len(regressions) > 0,
        "regressions": regressions,
    }


# --- 4.1: Adjustment proposal generation ---


def generate_adjustment_proposals(
    calibrations: dict[str, dict[str, Any]],
    control_chart: dict[str, dict[str, Any]],
    regression_result: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """confidence delta proposal + risk_level 判定。"""
    if config is None:
        config = load_self_evolution_config()
    fp_threshold = config.get("false_positive_rate_threshold", 0.3)

    proposals = []
    for it, cal in calibrations.items():
        delta = cal["calibrated"] - cal["current"]
        if abs(delta) < 0.01:
            continue  # 変化なし

        cc = control_chart.get(it, {})
        risk_level = cc.get("risk_level", "low")

        # Regression override
        if it in regression_result.get("regressions", {}):
            risk_level = "regression"

        proposal = {
            "issue_type": it,
            "current_confidence": cal["current"],
            "proposed_confidence": cal["calibrated"],
            "delta": round(delta, 4),
            "alpha": cal["alpha"],
            "risk_level": risk_level,
            "evidence": (
                f"approval_rate={cal['approval_rate']:.2f}, "
                f"sample_size={cal['sample_size']}, "
                f"α={cal['alpha']:.2f}"
            ),
        }

        if risk_level == "high":
            proposal["warning"] = "統計的に外れ値の調整幅です。慎重にレビューしてください。"
        elif risk_level == "regression":
            reg = regression_result["regressions"][it]
            proposal["warning"] = (
                f"回帰検出: {it} の false positive rate が "
                f"{reg['old_fp_rate']:.0%} → {reg['new_fp_rate']:.0%} に増加する可能性があります。"
            )

        proposals.append(proposal)

    return proposals


# --- 4.2: Proposal persistence ---


def record_proposal(proposal: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any] | None:
    """pipeline-proposals.jsonl に提案を記録する。"""
    if dry_run:
        return None
    record = {
        **proposal,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROPOSALS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def update_proposal_status(issue_type: str, status: str) -> bool:
    """pipeline-proposals.jsonl 内の最新 pending 提案の status を更新する。"""
    if not PROPOSALS_FILE.exists():
        return False
    lines = PROPOSALS_FILE.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []
    for line in reversed(lines):
        if not updated:
            try:
                rec = json.loads(line)
                if rec.get("issue_type") == issue_type and rec.get("status") == "pending":
                    rec["status"] = status
                    line = json.dumps(rec, ensure_ascii=False)
                    updated = True
            except json.JSONDecodeError:
                pass
        new_lines.append(line)
    new_lines.reverse()
    PROPOSALS_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


# --- 5.2: Pipeline Health section for audit ---


def build_pipeline_health_section(
    config: dict[str, Any] | None = None,
) -> list[str] | None:
    """audit レポート用の Pipeline Health セクションを生成する。LLM 不使用。"""
    if config is None:
        config = load_self_evolution_config()

    outcomes = load_outcomes(lookback_days=config.get("analysis_lookback_days", 30))
    min_outcomes = config["min_outcomes_for_analysis"]
    total = len(outcomes)

    lines = ["", "## Pipeline Health", ""]

    if total < min_outcomes:
        lines.append(
            f"データ不足（{total}/{min_outcomes} 件）。"
            "evolve を繰り返し実行してデータを蓄積してください。"
        )
        lines.append("")
        return lines

    analysis = analyze_trajectory(outcomes, config)
    by_type = analysis.get("by_type", {})
    degraded_threshold = config.get("approval_rate_degraded_threshold", 0.7)

    # Table header
    lines.append("| issue_type | total | precision | approval_rate | FP count | status |")
    lines.append("|---|---|---|---|---|---|")

    for it, stats in sorted(by_type.items()):
        t = stats.get("total", 0)
        prec = stats.get("precision", 0)
        ar = stats.get("approval_rate", 0)
        fp = stats.get("rejected", 0) + stats.get("skipped", 0)
        status = "DEGRADED" if ar < degraded_threshold else "OK"
        lines.append(f"| {it} | {t} | {prec:.0%} | {ar:.0%} | {fp} | {status} |")

    lines.append("")

    # DEGRADED recommendation
    degraded_types = [it for it, s in by_type.items() if s.get("approval_rate", 0) < degraded_threshold]
    if degraded_types:
        lines.append(
            f"DEGRADED: {', '.join(degraded_types)}。"
            "`/rl-anything:evolve` での self-evolution を推奨します。"
        )
        lines.append("")

    return lines
