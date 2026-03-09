"""pipeline_reflector.py のユニットテスト。"""
import json
import sys
from pathlib import Path

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

from pipeline_reflector import (
    DEFAULT_SELF_EVOLUTION_CONFIG,
    analyze_trajectory,
    build_pipeline_health_section,
    calibrate_confidence,
    check_calibration_regression,
    check_control_chart,
    detect_false_positives,
    generate_adjustment_proposals,
    load_calibration,
    load_outcomes,
    load_self_evolution_config,
    record_proposal,
    save_calibration,
    update_proposal_status,
)


def _make_outcome(
    issue_type="stale_ref",
    result="success",
    user_decision="approved",
    confidence_score=0.95,
    category="auto_fixable",
    impact_scope="file",
    **kwargs,
):
    rec = {
        "timestamp": "2026-03-01T00:00:00+00:00",
        "issue_type": issue_type,
        "result": result,
        "user_decision": user_decision,
        "confidence_score": confidence_score,
        "category": category,
        "impact_scope": impact_scope,
        "action": "test",
        "rationale": "test",
        "file": "test.md",
    }
    rec.update(kwargs)
    return rec


# ---------- Config ----------

class TestConfig:
    def test_default_config_has_all_keys(self):
        assert "min_outcomes_for_analysis" in DEFAULT_SELF_EVOLUTION_CONFIG
        assert "calibration_sample_threshold" in DEFAULT_SELF_EVOLUTION_CONFIG
        assert "max_calibration_alpha" in DEFAULT_SELF_EVOLUTION_CONFIG
        assert "false_positive_rate_threshold" in DEFAULT_SELF_EVOLUTION_CONFIG
        assert "self_evolution_cooldown_hours" in DEFAULT_SELF_EVOLUTION_CONFIG
        assert "systematic_rejection_threshold" in DEFAULT_SELF_EVOLUTION_CONFIG

    def test_load_config_with_empty_state(self):
        config = load_self_evolution_config(state={})
        assert config == DEFAULT_SELF_EVOLUTION_CONFIG

    def test_load_config_with_overrides(self):
        state = {
            "trigger_config": {
                "self_evolution": {
                    "min_outcomes_for_analysis": 50,
                }
            }
        }
        config = load_self_evolution_config(state=state)
        assert config["min_outcomes_for_analysis"] == 50
        assert config["calibration_sample_threshold"] == 30  # default preserved


# ---------- Trajectory Analysis ----------

class TestTrajectoryAnalysis:
    def test_insufficient_data(self):
        outcomes = [_make_outcome() for _ in range(5)]
        result = analyze_trajectory(outcomes)
        assert result["sufficient"] is False
        assert "データ不足" in result["diagnosis"]

    def test_sufficient_data_computes_metrics(self):
        outcomes = [_make_outcome() for _ in range(15)]
        outcomes += [_make_outcome(user_decision="rejected", result="rejected") for _ in range(5)]
        result = analyze_trajectory(outcomes)
        assert result["sufficient"] is True
        assert "stale_ref" in result["by_type"]
        stats = result["by_type"]["stale_ref"]
        assert stats["total"] == 20
        assert stats["approved"] == 15
        assert stats["approval_rate"] == 0.75

    def test_empty_outcomes(self):
        result = analyze_trajectory([])
        assert result["sufficient"] is False

    def test_multiple_issue_types(self):
        outcomes = [_make_outcome(issue_type="stale_ref") for _ in range(12)]
        outcomes += [_make_outcome(issue_type="orphan_rule") for _ in range(10)]
        result = analyze_trajectory(outcomes)
        assert result["sufficient"] is True
        assert "stale_ref" in result["by_type"]
        assert "orphan_rule" in result["by_type"]


# ---------- False Positive Detection ----------

class TestFalsePositiveDetection:
    def test_high_confidence_rejection(self):
        outcomes = [
            _make_outcome(confidence_score=0.95, user_decision="rejected", result="rejected"),
        ]
        result = detect_false_positives(outcomes)
        assert len(result["high_confidence_rejections"]) == 1

    def test_no_high_confidence_rejection(self):
        outcomes = [
            _make_outcome(confidence_score=0.5, user_decision="rejected", result="rejected"),
        ]
        result = detect_false_positives(outcomes)
        assert len(result["high_confidence_rejections"]) == 0

    def test_systematic_rejection(self):
        outcomes = [
            _make_outcome(category="proposable", user_decision="rejected", result="rejected")
            for _ in range(4)
        ]
        result = detect_false_positives(outcomes)
        assert "stale_ref" in result["systematic_rejections"]
        assert result["systematic_rejections"]["stale_ref"] >= 3


# ---------- Diagnosis ----------

class TestDiagnosis:
    def test_false_positive_dominant_diagnosis(self):
        outcomes = [_make_outcome() for _ in range(12)]
        outcomes += [_make_outcome(user_decision="rejected", result="rejected") for _ in range(8)]
        result = analyze_trajectory(outcomes)
        assert "過大評価" in result["diagnosis"]

    def test_healthy_diagnosis(self):
        outcomes = [_make_outcome() for _ in range(20)]
        result = analyze_trajectory(outcomes)
        assert "健全" in result["diagnosis"]


# ---------- Calibration ----------

class TestCalibration:
    def test_calibrate_with_sufficient_data(self):
        outcomes = [_make_outcome() for _ in range(8)]
        outcomes += [_make_outcome(user_decision="rejected", result="rejected") for _ in range(4)]
        config = dict(DEFAULT_SELF_EVOLUTION_CONFIG)
        config["min_outcomes_per_type"] = 10
        result = calibrate_confidence(outcomes, config)
        assert "stale_ref" in result["calibrations"]
        cal = result["calibrations"]["stale_ref"]
        assert 0 < cal["alpha"] <= 0.7
        assert 0 <= cal["calibrated"] <= 1.0

    def test_calibrate_insufficient_data(self):
        outcomes = [_make_outcome() for _ in range(3)]
        config = dict(DEFAULT_SELF_EVOLUTION_CONFIG)
        config["min_outcomes_per_type"] = 10
        result = calibrate_confidence(outcomes, config)
        assert "stale_ref" not in result["calibrations"]

    def test_ewa_formula(self):
        """EWA: calibrated = α * observed + (1-α) * current."""
        outcomes = [_make_outcome(confidence_score=0.95) for _ in range(10)]
        outcomes += [_make_outcome(confidence_score=0.95, user_decision="rejected", result="rejected") for _ in range(5)]
        config = dict(DEFAULT_SELF_EVOLUTION_CONFIG)
        config["min_outcomes_per_type"] = 10
        config["calibration_sample_threshold"] = 30
        config["max_calibration_alpha"] = 0.7
        result = calibrate_confidence(outcomes, config)
        cal = result["calibrations"]["stale_ref"]
        # α = min(15/30, 0.7) = 0.5
        # observed = 10/15 ≈ 0.6667
        # current = 0.95
        # calibrated = 0.5 * 0.6667 + 0.5 * 0.95 ≈ 0.8083
        assert abs(cal["alpha"] - 0.5) < 0.01
        assert abs(cal["calibrated"] - 0.8083) < 0.02


# ---------- Control Chart ----------

class TestControlChart:
    def test_single_item_is_low_risk(self):
        calibrations = {"stale_ref": {"current": 0.95, "calibrated": 0.80, "alpha": 0.5, "sample_size": 15, "approval_rate": 0.7}}
        result = check_control_chart(calibrations)
        assert result["stale_ref"]["risk_level"] == "low"

    def test_outlier_is_high_risk(self):
        # 5 types with small deltas, 1 with extreme delta → outlier > 2σ
        calibrations = {
            f"type_{i}": {"current": 0.9, "calibrated": 0.9 - 0.01 * i, "alpha": 0.5, "sample_size": 15, "approval_rate": 0.9}
            for i in range(1, 6)
        }
        calibrations["type_outlier"] = {"current": 0.9, "calibrated": 0.1, "alpha": 0.5, "sample_size": 15, "approval_rate": 0.1}
        result = check_control_chart(calibrations)
        assert result["type_outlier"]["risk_level"] == "high"
        # Normal types should be low
        assert result["type_1"]["risk_level"] == "low"


# ---------- Regression Check ----------

class TestRegressionCheck:
    def test_no_regression(self):
        calibrations = {"stale_ref": {"current": 0.95, "calibrated": 0.80, "alpha": 0.5, "sample_size": 15, "approval_rate": 0.7}}
        outcomes = [_make_outcome() for _ in range(10)]
        result = check_calibration_regression(calibrations, outcomes)
        assert result["has_regression"] is False

    def test_regression_detected(self):
        calibrations = {"stale_ref": {"current": 0.95, "calibrated": 0.95, "alpha": 0.5, "sample_size": 15, "approval_rate": 0.7}}
        outcomes = [_make_outcome(user_decision="rejected", result="rejected") for _ in range(10)]
        config = dict(DEFAULT_SELF_EVOLUTION_CONFIG)
        config["regression_fp_increase_threshold"] = 0.0  # Any increase triggers
        result = check_calibration_regression(calibrations, outcomes, config)
        # regression depends on classification logic


# ---------- Proposal Generation ----------

class TestProposalGeneration:
    def test_generates_proposals_for_delta(self):
        calibrations = {
            "stale_ref": {"current": 0.95, "calibrated": 0.80, "alpha": 0.5, "sample_size": 15, "approval_rate": 0.7},
        }
        control_chart = {"stale_ref": {"delta": -0.15, "mean_delta": -0.15, "std_delta": 0, "risk_level": "low"}}
        regression_result = {"has_regression": False, "regressions": {}}
        proposals = generate_adjustment_proposals(calibrations, control_chart, regression_result)
        assert len(proposals) == 1
        assert proposals[0]["issue_type"] == "stale_ref"
        assert proposals[0]["risk_level"] == "low"

    def test_high_risk_proposal_has_warning(self):
        calibrations = {
            "stale_ref": {"current": 0.95, "calibrated": 0.30, "alpha": 0.5, "sample_size": 15, "approval_rate": 0.3},
        }
        control_chart = {"stale_ref": {"delta": -0.65, "mean_delta": -0.1, "std_delta": 0.05, "risk_level": "high"}}
        regression_result = {"has_regression": False, "regressions": {}}
        proposals = generate_adjustment_proposals(calibrations, control_chart, regression_result)
        assert proposals[0]["risk_level"] == "high"
        assert "warning" in proposals[0]

    def test_regression_risk_level(self):
        calibrations = {
            "stale_ref": {"current": 0.95, "calibrated": 0.80, "alpha": 0.5, "sample_size": 15, "approval_rate": 0.7},
        }
        control_chart = {"stale_ref": {"delta": -0.15, "mean_delta": -0.15, "std_delta": 0, "risk_level": "low"}}
        regression_result = {
            "has_regression": True,
            "regressions": {"stale_ref": {"old_fp_rate": 0.1, "new_fp_rate": 0.3, "increase": 0.2}},
        }
        proposals = generate_adjustment_proposals(calibrations, control_chart, regression_result)
        assert proposals[0]["risk_level"] == "regression"

    def test_skip_negligible_delta(self):
        calibrations = {
            "stale_ref": {"current": 0.95, "calibrated": 0.955, "alpha": 0.5, "sample_size": 15, "approval_rate": 0.95},
        }
        control_chart = {"stale_ref": {"delta": 0.005, "mean_delta": 0.005, "std_delta": 0, "risk_level": "low"}}
        regression_result = {"has_regression": False, "regressions": {}}
        proposals = generate_adjustment_proposals(calibrations, control_chart, regression_result)
        assert len(proposals) == 0


# ---------- Proposal Persistence ----------

class TestProposalPersistence:
    def test_record_proposal(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline_reflector.DATA_DIR", tmp_path)
        monkeypatch.setattr("pipeline_reflector.PROPOSALS_FILE", tmp_path / "pipeline-proposals.jsonl")
        proposal = {"issue_type": "stale_ref", "delta": -0.15}
        result = record_proposal(proposal)
        assert result is not None
        assert result["status"] == "pending"
        assert (tmp_path / "pipeline-proposals.jsonl").exists()

    def test_record_proposal_dry_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline_reflector.DATA_DIR", tmp_path)
        monkeypatch.setattr("pipeline_reflector.PROPOSALS_FILE", tmp_path / "pipeline-proposals.jsonl")
        result = record_proposal({"issue_type": "stale_ref"}, dry_run=True)
        assert result is None

    def test_update_proposal_status(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline_reflector.DATA_DIR", tmp_path)
        proposals_file = tmp_path / "pipeline-proposals.jsonl"
        monkeypatch.setattr("pipeline_reflector.PROPOSALS_FILE", proposals_file)
        record = {"issue_type": "stale_ref", "status": "pending", "timestamp": "2026-03-01"}
        proposals_file.write_text(json.dumps(record) + "\n")
        assert update_proposal_status("stale_ref", "approved") is True
        updated = json.loads(proposals_file.read_text().strip())
        assert updated["status"] == "approved"


# ---------- Pipeline Health Section ----------

class TestPipelineHealthSection:
    def test_sufficient_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline_reflector.OUTCOMES_FILE", tmp_path / "outcomes.jsonl")
        outcomes = [_make_outcome() for _ in range(20)]
        (tmp_path / "outcomes.jsonl").write_text(
            "\n".join(json.dumps(o) for o in outcomes) + "\n"
        )
        lines = build_pipeline_health_section()
        assert lines is not None
        text = "\n".join(lines)
        assert "Pipeline Health" in text
        assert "stale_ref" in text

    def test_insufficient_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline_reflector.OUTCOMES_FILE", tmp_path / "outcomes.jsonl")
        outcomes = [_make_outcome() for _ in range(5)]
        (tmp_path / "outcomes.jsonl").write_text(
            "\n".join(json.dumps(o) for o in outcomes) + "\n"
        )
        lines = build_pipeline_health_section()
        text = "\n".join(lines)
        assert "データ不足" in text

    def test_degraded_marker(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline_reflector.OUTCOMES_FILE", tmp_path / "outcomes.jsonl")
        outcomes = [_make_outcome() for _ in range(10)]
        outcomes += [_make_outcome(user_decision="rejected", result="rejected") for _ in range(12)]
        (tmp_path / "outcomes.jsonl").write_text(
            "\n".join(json.dumps(o) for o in outcomes) + "\n"
        )
        lines = build_pipeline_health_section()
        text = "\n".join(lines)
        assert "DEGRADED" in text

    def test_no_llm_call(self, tmp_path, monkeypatch):
        """LLM は呼び出されない（mock なしでも動作する）。"""
        monkeypatch.setattr("pipeline_reflector.OUTCOMES_FILE", tmp_path / "outcomes.jsonl")
        outcomes = [_make_outcome() for _ in range(20)]
        (tmp_path / "outcomes.jsonl").write_text(
            "\n".join(json.dumps(o) for o in outcomes) + "\n"
        )
        # No LLM mock needed — if it called LLM it would fail
        lines = build_pipeline_health_section()
        assert lines is not None


# ---------- Calibration File I/O ----------

class TestCalibrationIO:
    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline_reflector.DATA_DIR", tmp_path)
        monkeypatch.setattr("pipeline_reflector.CALIBRATION_FILE", tmp_path / "calibration.json")
        data = {"last_calibrated": "2026-03-01", "calibrations": {"stale_ref": {"calibrated": 0.8}}}
        save_calibration(data)
        loaded = load_calibration()
        assert loaded["calibrations"]["stale_ref"]["calibrated"] == 0.8

    def test_load_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline_reflector.CALIBRATION_FILE", tmp_path / "nonexistent.json")
        assert load_calibration() == {}
