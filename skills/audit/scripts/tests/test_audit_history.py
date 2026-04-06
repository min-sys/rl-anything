"""audit-history 記録・劣化検出・pruning テスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

_audit_dir = Path(__file__).resolve().parent.parent
_plugin_root = _audit_dir.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_audit_dir))

from audit import (
    _append_audit_history,
    _check_degradation,
    _extract_score_from_report,
    _MAX_AUDIT_HISTORY,
)


@pytest.fixture
def data_dir(tmp_path):
    with mock.patch("audit.DATA_DIR", tmp_path), mock.patch(
        "audit._AUDIT_HISTORY_FILE", tmp_path / "audit-history.jsonl"
    ):
        yield tmp_path


class TestAppendAuditHistory:
    def test_append_creates_file(self, data_dir):
        _append_audit_history({"timestamp": "2026-01-01", "coherence_score": 0.85})
        history = (data_dir / "audit-history.jsonl").read_text(encoding="utf-8")
        assert "0.85" in history

    def test_append_multiple(self, data_dir):
        _append_audit_history({"timestamp": "2026-01-01", "coherence_score": 0.85})
        _append_audit_history({"timestamp": "2026-01-02", "coherence_score": 0.90})
        lines = (
            (data_dir / "audit-history.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert len(lines) == 2

    def test_pruning(self, data_dir):
        # Write 105 records
        existing = [
            json.dumps({"timestamp": f"2026-01-{i:02d}", "coherence_score": 0.80})
            for i in range(1, 106)
        ]
        (data_dir / "audit-history.jsonl").write_text(
            "\n".join(existing), encoding="utf-8"
        )
        _append_audit_history({"timestamp": "2026-02-01", "coherence_score": 0.75})
        lines = (
            (data_dir / "audit-history.jsonl")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert len(lines) <= _MAX_AUDIT_HISTORY


class TestCheckDegradation:
    def test_degradation_warning(self, data_dir, capsys):
        # Write previous record with high score, current with low
        records = [
            json.dumps({"timestamp": "2026-01-01", "coherence_score": 1.0}),
            json.dumps({"timestamp": "2026-01-02", "coherence_score": 0.80}),
        ]
        (data_dir / "audit-history.jsonl").write_text(
            "\n".join(records) + "\n", encoding="utf-8"
        )
        _check_degradation({"coherence_score": 0.80})
        captured = capsys.readouterr()
        assert "低下" in captured.err

    def test_no_degradation(self, data_dir, capsys):
        records = [
            json.dumps({"timestamp": "2026-01-01", "coherence_score": 0.80}),
            json.dumps({"timestamp": "2026-01-02", "coherence_score": 0.85}),
        ]
        (data_dir / "audit-history.jsonl").write_text(
            "\n".join(records) + "\n", encoding="utf-8"
        )
        _check_degradation({"coherence_score": 0.85})
        captured = capsys.readouterr()
        assert "低下" not in captured.err

    def test_no_previous_record(self, data_dir, capsys):
        _check_degradation({"coherence_score": 0.85})
        captured = capsys.readouterr()
        assert captured.err == ""


class TestExtractScoreFromReport:
    def test_extract_score(self):
        lines = ["Coherence Score: 0.85", "Details..."]
        assert _extract_score_from_report(lines) == 0.85

    def test_extract_overall(self):
        lines = ["  Overall: 0.72  "]
        assert _extract_score_from_report(lines) == 0.72

    def test_no_score(self):
        lines = ["No scores here"]
        assert _extract_score_from_report(lines) is None
