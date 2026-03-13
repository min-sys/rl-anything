#!/usr/bin/env python3
"""Evolve オーケストレーター。

Observe データ確認 → Discover → Enrich → Optimize → Reorganize → Prune(+Merge) →
Fitness Evolution → Report の全フェーズを1つのコマンドで実行する。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "discover" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "prune" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "evolve-fitness" / "scripts"))
# enrich は discover に統合済み — import パス不要
sys.path.insert(0, str(_plugin_root / "skills" / "reorganize" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "evolve" / "scripts"))

DATA_DIR = Path.home() / ".claude" / "rl-anything"
EVOLVE_STATE_FILE = DATA_DIR / "evolve-state.json"


def load_evolve_state() -> Dict[str, Any]:
    """前回の evolve 実行状態を読み込む。"""
    if not EVOLVE_STATE_FILE.exists():
        return {}
    try:
        return json.loads(EVOLVE_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_evolve_state(state: Dict[str, Any]) -> None:
    """evolve 実行状態を保存する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVOLVE_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def count_new_sessions() -> int:
    """前回 evolve 実行以降のセッション数を数える。

    sessions.jsonl と usage.jsonl 両方からユニーク session_id を集計する。
    backfill データ（sessions.jsonl に書かれない）も含めてカウントできる。
    """
    state = load_evolve_state()
    last_run = state.get("last_run_timestamp", "")
    session_ids: set = set()

    # sessions.jsonl から集計
    sessions_file = DATA_DIR / "sessions.jsonl"
    if sessions_file.exists():
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

    # usage.jsonl からもユニーク session_id を集計（backfill 対応）
    usage_file = DATA_DIR / "usage.jsonl"
    if usage_file.exists():
        for line in usage_file.read_text(encoding="utf-8").splitlines():
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


def count_new_observations() -> int:
    """前回 evolve 実行以降の観測数を数える。"""
    state = load_evolve_state()
    last_run = state.get("last_run_timestamp", "")

    usage_file = DATA_DIR / "usage.jsonl"
    if not usage_file.exists():
        return 0

    count = 0
    for line in usage_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "")
            if ts > last_run:
                count += 1
        except json.JSONDecodeError:
            continue
    return count


def _build_trigger_summary() -> Dict[str, Any]:
    """直近のトリガー発火回数・最終発火日時をまとめる。"""
    state = load_evolve_state()
    history = state.get("trigger_history", [])
    if not history:
        return {"total_fires": 0, "last_fired": None}
    return {
        "total_fires": len(history),
        "last_fired": history[-1].get("timestamp"),
        "recent_reasons": [h.get("reason") for h in history[-5:]],
    }


def compute_trend(
    current: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """前回 snapshot との差分を算出しトレンド情報を返す。

    Args:
        current: 今回の tool_usage_snapshot (builtin_replaceable, sleep_patterns, bash_ratio)
        previous: 前回の tool_usage_snapshot (None = 初回)

    Returns:
        各指標のトレンド情報を含む辞書
    """
    if previous is None:
        return {"has_previous": False}

    trends: Dict[str, Any] = {"has_previous": True}

    # 件数ベースの指標
    for key in ("builtin_replaceable", "sleep_patterns"):
        cur = current.get(key, 0)
        prev = previous.get(key, 0)
        diff = cur - prev
        if prev > 0:
            pct = diff / prev * 100
        else:
            pct = 0.0 if diff == 0 else 100.0

        if diff < 0:
            label = f"↓ {abs(diff)}件減少 ({pct:+.0f}%)"
        elif diff > 0:
            label = f"↑ {diff}件増加 ({pct:+.0f}%)"
        else:
            label = "→ 変化なし"

        trends[key] = {"current": cur, "previous": prev, "diff": diff, "pct": pct, "label": label}

    # ratio ベースの指標 (bash_ratio)
    cur_ratio = current.get("bash_ratio", 0.0)
    prev_ratio = previous.get("bash_ratio", 0.0)
    pp_diff = (cur_ratio - prev_ratio) * 100  # パーセントポイント差

    if abs(pp_diff) < 0.05:
        ratio_label = f"{cur_ratio * 100:.1f}% → 変化なし"
    elif pp_diff < 0:
        ratio_label = f"{prev_ratio * 100:.1f}% → {cur_ratio * 100:.1f}% (↓{abs(pp_diff):.1f}pp)"
    else:
        ratio_label = f"{prev_ratio * 100:.1f}% → {cur_ratio * 100:.1f}% (↑{pp_diff:.1f}pp)"

    trends["bash_ratio"] = {
        "current": cur_ratio,
        "previous": prev_ratio,
        "pp_diff": pp_diff,
        "label": ratio_label,
    }

    return trends


def check_data_sufficiency() -> Dict[str, Any]:
    """観測データの十分性をチェックする。

    判定基準: セッション3+かつ観測10+、
    または全観測が20+（backfill で大量データがある場合を考慮）。
    """
    sessions = count_new_sessions()
    observations = count_new_observations()

    # 全データ（last_run 以前も含む）の観測数もフォールバックで確認
    total_observations = _count_total_observations()

    sufficient = (
        (sessions >= 3 and observations >= 10)
        or total_observations >= 20
    )

    if sufficient:
        msg = f"{sessions} セッション, {observations} 新規観測 (全{total_observations}) — データ十分"
    else:
        msg = f"前回 evolve 以降: {sessions} セッション, {observations} 観測 (全{total_observations})"

    return {
        "sessions": sessions,
        "observations": observations,
        "total_observations": total_observations,
        "sufficient": sufficient,
        "message": msg,
    }


def _count_total_observations() -> int:
    """usage.jsonl の全レコード数を返す。"""
    usage_file = DATA_DIR / "usage.jsonl"
    if not usage_file.exists():
        return 0
    return sum(
        1 for line in usage_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def check_fitness_function(project_dir: Optional[str] = None) -> Dict[str, Any]:
    """プロジェクト固有の fitness 関数の有無をチェックする。"""
    proj = Path(project_dir) if project_dir else Path.cwd()
    fitness_dir = proj / "scripts" / "rl" / "fitness"
    criteria_file = proj / ".claude" / "fitness-criteria.md"

    fitness_files = []
    if fitness_dir.exists():
        fitness_files = [f.stem for f in fitness_dir.glob("*.py") if f.name != "__init__.py"]

    return {
        "has_fitness": len(fitness_files) > 0,
        "has_criteria": criteria_file.exists(),
        "fitness_functions": fitness_files,
        "fitness_dir": str(fitness_dir),
    }


def run_evolve(
    project_dir: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """全フェーズを実行する。

    Args:
        project_dir: プロジェクトディレクトリ
        dry_run: True の場合、レポートのみ出力し変更は行わない

    Returns:
        各フェーズの結果を含む辞書
    """
    result: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "phases": {},
    }

    # Phase 1: Observe データ確認
    sufficiency = check_data_sufficiency()
    result["phases"]["observe"] = sufficiency

    if not sufficiency["sufficient"]:
        result["phases"]["observe"]["action"] = "skip_recommended"
        # スキップ推奨だがユーザー選択に委ねる
        print(f"データ不足: {sufficiency['message']}")
        print("スキップ推奨。--force で強制実行可能。")

    # Phase 1.5: Fitness 関数チェック
    fitness_check = check_fitness_function(project_dir)
    result["phases"]["fitness"] = fitness_check

    # Phase 2: Discover
    try:
        from discover import run_discover
        project_root = Path(project_dir) if project_dir else None
        discover_result = run_discover(project_root=project_root, tool_usage=True)
        result["phases"]["discover"] = discover_result
    except Exception as e:
        result["phases"]["discover"] = {"error": str(e)}

    # Phase 2.5: Enrich（discover に統合済み — discover 出力から取得）
    discover_data = result["phases"].get("discover", {})
    result["phases"]["enrich"] = {
        "enrichments": discover_data.get("matched_skills", []),
        "unmatched_patterns": discover_data.get("unmatched_patterns", []),
        "total_enrichments": len(discover_data.get("matched_skills", [])),
        "total_unmatched": len(discover_data.get("unmatched_patterns", [])),
        "skipped_reason": "no_patterns_available" if not discover_data.get("matched_skills") and not discover_data.get("unmatched_patterns") else None,
    }

    # Phase 2.7: Layer Diagnose（全レイヤー診断）
    try:
        sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
        from layer_diagnose import diagnose_all_layers
        proj = Path(project_dir) if project_dir else Path.cwd()
        layer_result = diagnose_all_layers(proj)
        result["phases"]["layer_diagnose"] = layer_result
    except Exception as e:
        result["phases"]["layer_diagnose"] = {"error": str(e)}

    # Phase 3: Audit
    try:
        from audit import run_audit
        audit_report = run_audit(project_dir)
        result["phases"]["audit"] = {"report": audit_report}
    except Exception as e:
        result["phases"]["audit"] = {"error": str(e)}

    # Phase 3.5: Remediation（audit の後）
    try:
        from audit import collect_issues
        from remediation import classify_issues as classify_remediation_issues
        proj = Path(project_dir) if project_dir else Path.cwd()
        issues = collect_issues(proj)
        classified = classify_remediation_issues(issues)
        remediation_data = {
            "total_issues": len(issues),
            "auto_fixable": len(classified["auto_fixable"]),
            "proposable": len(classified["proposable"]),
            "manual_required": len(classified["manual_required"]),
            "classified": classified,
        }
        result["phases"]["remediation"] = remediation_data
    except Exception as e:
        result["phases"]["remediation"] = {"error": str(e)}

    # Phase 3.7: Reorganize（Prune の前）
    try:
        from reorganize import run_reorganize
        reorganize_result = run_reorganize(project_dir)
        result["phases"]["reorganize"] = reorganize_result
    except Exception as e:
        result["phases"]["reorganize"] = {"error": str(e)}

    # Phase 4: Prune（dry-run 時は候補のみ）
    try:
        from prune import run_prune
        # Reorganize の merge_groups を Prune に渡す
        reorganize_data = result["phases"].get("reorganize", {})
        merge_groups = reorganize_data.get("merge_groups", []) if not reorganize_data.get("skipped") else []
        prune_result = run_prune(project_dir, reorganize_merge_groups=merge_groups)
        result["phases"]["prune"] = prune_result
    except Exception as e:
        result["phases"]["prune"] = {"error": str(e)}

    # Phase 5: Fitness Evolution（評価関数の改善チェック）
    try:
        from fitness_evolution import run_fitness_evolution
        fitness_evo_result = run_fitness_evolution()
        result["phases"]["fitness_evolution"] = fitness_evo_result
    except Exception as e:
        result["phases"]["fitness_evolution"] = {"error": str(e)}

    # Phase 6: Self-Evolution（パイプライン自己改善）
    try:
        sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
        from pipeline_reflector import (
            analyze_trajectory,
            calibrate_confidence,
            check_calibration_regression,
            check_control_chart,
            detect_false_positives,
            generate_adjustment_proposals,
            load_self_evolution_config,
            record_proposal,
        )
        se_config = load_self_evolution_config()
        analysis = analyze_trajectory(config=se_config)

        if not analysis["sufficient"]:
            result["phases"]["self_evolution"] = {
                "skipped": True,
                "reason": analysis["diagnosis"],
                "total": analysis["total"],
                "min_required": analysis["min_required"],
            }
        else:
            # Trajectory analysis
            fp_result = detect_false_positives(
                analysis.get("_outcomes", []),  # fallback: empty
                se_config,
            )

            # Calibration
            cal_result = calibrate_confidence(config=se_config)
            calibrations = cal_result.get("calibrations", {})

            # Control chart + regression check
            cc_result = check_control_chart(calibrations) if calibrations else {}
            from pipeline_reflector import load_outcomes
            outcomes = load_outcomes(lookback_days=se_config.get("analysis_lookback_days", 30))
            reg_result = check_calibration_regression(calibrations, outcomes, se_config) if calibrations else {"has_regression": False, "regressions": {}}

            # Generate proposals
            proposals = generate_adjustment_proposals(calibrations, cc_result, reg_result, se_config) if calibrations else []

            # Record proposals (unless dry-run)
            recorded_proposals = []
            for p in proposals:
                rec = record_proposal(p, dry_run=dry_run)
                if rec:
                    recorded_proposals.append(rec)

            result["phases"]["self_evolution"] = {
                "skipped": False,
                "analysis": {
                    "total": analysis["total"],
                    "by_type": analysis["by_type"],
                    "diagnosis": analysis["diagnosis"],
                },
                "false_positives": {
                    "high_confidence_count": len(fp_result.get("high_confidence_rejections", [])),
                    "systematic_flags": fp_result.get("systematic_rejections", {}),
                },
                "calibrations": calibrations,
                "control_chart": cc_result,
                "regression": reg_result,
                "proposals": proposals,
                "proposals_recorded": len(recorded_proposals),
            }
    except Exception as e:
        result["phases"]["self_evolution"] = {"error": str(e)}

    # Trigger history summary for report
    result["trigger_summary"] = _build_trigger_summary()

    # State 更新（dry-run でない場合）
    if not dry_run:
        state = load_evolve_state()
        state.update({
            "last_run_timestamp": datetime.now(timezone.utc).isoformat(),
            "sessions_processed": sufficiency["sessions"],
            "observations_processed": sufficiency["observations"],
        })
        # Self-evolution state
        se_phase = result["phases"].get("self_evolution", {})
        if not se_phase.get("skipped") and not se_phase.get("error"):
            state["last_calibration_timestamp"] = datetime.now(timezone.utc).isoformat()
            history = state.get("calibration_history", [])
            history.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "calibrations": se_phase.get("calibrations", {}),
                "proposals_count": len(se_phase.get("proposals", [])),
            })
            state["calibration_history"] = history
        # Tool usage snapshot for trend tracking
        discover_data = result["phases"].get("discover", {})
        tool_usage = discover_data.get("tool_usage_patterns", {})
        if tool_usage:
            state["tool_usage_snapshot"] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "builtin_replaceable": sum(
                    item.get("count", 0)
                    for item in tool_usage.get("builtin_replaceable", [])
                ),
                "sleep_patterns": sum(
                    p.get("count", 0)
                    for p in tool_usage.get("repeating_patterns", [])
                    if "sleep" in p.get("pattern", "").lower()
                ),
                "bash_ratio": (
                    tool_usage.get("bash_calls", 0) / tool_usage.get("total_tool_calls", 1)
                    if tool_usage.get("total_tool_calls", 0) > 0
                    else 0.0
                ),
            }
        save_evolve_state(state)

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evolve オーケストレーター")
    parser.add_argument("--project-dir", default=None, help="プロジェクトディレクトリ")
    parser.add_argument("--dry-run", action="store_true", help="レポートのみ、変更なし")

    args = parser.parse_args()

    result = run_evolve(
        project_dir=args.project_dir,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
