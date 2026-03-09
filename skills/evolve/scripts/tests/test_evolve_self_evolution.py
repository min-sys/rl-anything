"""evolve.py Phase 6 (Self-Evolution) の統合テスト。

他のフェーズ（discover, audit 等）は try/except で囲まれており
ImportError 時は error として記録されるため、
self_evolution Phase のみを検証する。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "evolve" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "scripts"))

from evolve import run_evolve


def _make_outcome(
    issue_type="stale_ref",
    result="success",
    user_decision="approved",
    confidence_score=0.95,
    category="auto_fixable",
):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "issue_type": issue_type,
        "result": result,
        "user_decision": user_decision,
        "confidence_score": confidence_score,
        "category": category,
        "impact_scope": "file",
        "action": "test",
        "rationale": "test",
        "file": "test.md",
    }


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """テスト用 DATA_DIR を設定。"""
    monkeypatch.setattr("evolve.DATA_DIR", tmp_path)
    monkeypatch.setattr("evolve.EVOLVE_STATE_FILE", tmp_path / "evolve-state.json")
    monkeypatch.setattr("pipeline_reflector.DATA_DIR", tmp_path)
    monkeypatch.setattr("pipeline_reflector.OUTCOMES_FILE", tmp_path / "remediation-outcomes.jsonl")
    monkeypatch.setattr("pipeline_reflector.CALIBRATION_FILE", tmp_path / "confidence-calibration.json")
    monkeypatch.setattr("pipeline_reflector.PROPOSALS_FILE", tmp_path / "pipeline-proposals.jsonl")
    return tmp_path


class TestSelfEvolutionPhase:
    def test_skipped_when_insufficient_data(self, data_dir):
        """outcome が不足している場合は Phase 6 がスキップされる。"""
        outcomes = [_make_outcome() for _ in range(5)]
        (data_dir / "remediation-outcomes.jsonl").write_text(
            "\n".join(json.dumps(o) for o in outcomes) + "\n"
        )

        result = run_evolve(dry_run=True)

        se = result["phases"].get("self_evolution", {})
        assert se.get("skipped") is True
        assert "データ不足" in se.get("reason", "")

    def test_executes_with_sufficient_data(self, data_dir):
        """outcome が十分な場合は Phase 6 が実行される。"""
        outcomes = [_make_outcome() for _ in range(15)]
        outcomes += [_make_outcome(user_decision="rejected", result="rejected") for _ in range(7)]
        (data_dir / "remediation-outcomes.jsonl").write_text(
            "\n".join(json.dumps(o) for o in outcomes) + "\n"
        )

        result = run_evolve(dry_run=True)

        se = result["phases"].get("self_evolution", {})
        assert se.get("skipped") is False
        assert "analysis" in se
        assert "calibrations" in se
        assert se["analysis"]["total"] == 22

    def test_dry_run_does_not_write_state(self, data_dir):
        """dry-run 時は evolve-state.json に calibration 状態が書き込まれない。"""
        outcomes = [_make_outcome() for _ in range(20)]
        (data_dir / "remediation-outcomes.jsonl").write_text(
            "\n".join(json.dumps(o) for o in outcomes) + "\n"
        )

        run_evolve(dry_run=True)

        state_file = data_dir / "evolve-state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text())
            assert "last_calibration_timestamp" not in state

    def test_non_dry_run_writes_calibration_state(self, data_dir):
        """非 dry-run 時は calibration 状態が記録される。"""
        outcomes = [_make_outcome() for _ in range(20)]
        (data_dir / "remediation-outcomes.jsonl").write_text(
            "\n".join(json.dumps(o) for o in outcomes) + "\n"
        )

        run_evolve(dry_run=False)

        state_file = data_dir / "evolve-state.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert "last_calibration_timestamp" in state
        assert "calibration_history" in state
        assert len(state["calibration_history"]) >= 1
