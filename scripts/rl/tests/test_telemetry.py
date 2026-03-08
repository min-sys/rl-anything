#!/usr/bin/env python3
"""telemetry.py のユニットテスト"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

_test_dir = Path(__file__).resolve().parent
_rl_dir = _test_dir.parent
_plugin_root = _rl_dir.parent.parent
sys.path.insert(0, str(_rl_dir))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))

import importlib.util

_telemetry_path = _rl_dir / "fitness" / "telemetry.py"
_spec = importlib.util.spec_from_file_location("telemetry", _telemetry_path)
telemetry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(telemetry)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _days_ago_iso(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _make_project(tmp_path, skill_names=None):
    """テスト用プロジェクト + JSONL データを作成する。"""
    if skill_names is None:
        skill_names = ["skill-a", "skill-b", "skill-c"]
    for name in skill_names:
        skill_dir = tmp_path / ".claude" / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}\n\n## Usage\nUse it.\n\n## Steps\nDo it.\n")
    return tmp_path


def _write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


class TestScoreUtilization:
    def test_all_skills_used_evenly(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        now = _now_iso()
        records = [
            {"skill_name": "skill-a", "project": tmp_path.name, "timestamp": now, "session_id": "s1"},
            {"skill_name": "skill-b", "project": tmp_path.name, "timestamp": now, "session_id": "s1"},
            {"skill_name": "skill-c", "project": tmp_path.name, "timestamp": now, "session_id": "s1"},
        ]
        usage_file = data_dir / "usage.jsonl"
        _write_jsonl(usage_file, records)

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_utilization(project, days=30)

        # 全 Skill 利用 + 均等分散 → 高スコア
        assert score >= 0.9

    def test_half_skills_unused(self, tmp_path):
        project = _make_project(tmp_path, skill_names=["skill-a", "skill-b", "skill-c", "skill-d"])
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        now = _now_iso()
        records = [
            {"skill_name": "skill-a", "project": tmp_path.name, "timestamp": now, "session_id": "s1"},
            {"skill_name": "skill-b", "project": tmp_path.name, "timestamp": now, "session_id": "s1"},
        ]
        _write_jsonl(data_dir / "usage.jsonl", records)

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_utilization(project, days=30)

        # utilization=0.5, entropy=1.0 → score=0.75
        assert 0.5 <= score <= 0.85

    def test_no_usage(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        _write_jsonl(data_dir / "usage.jsonl", [])

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_utilization(project, days=30)

        assert score == 0.0

    def test_no_skills(self, tmp_path):
        # No .claude/skills dir
        with mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_utilization(tmp_path, days=30)
        assert score == 0.0


class TestScoreEffectiveness:
    def test_errors_decreasing(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()

        mid = _days_ago_iso(30)
        old_ts = _days_ago_iso(45)
        recent_ts = _days_ago_iso(5)

        # 前期間: 10 errors、直近: 5 errors (50% 減)
        prev_errors = [{"tool_name": "Bash", "error": f"e{i}", "project": tmp_path.name, "timestamp": old_ts} for i in range(10)]
        recent_errors = [{"tool_name": "Bash", "error": f"e{i}", "project": tmp_path.name, "timestamp": recent_ts} for i in range(5)]
        _write_jsonl(data_dir / "errors.jsonl", prev_errors + recent_errors)
        _write_jsonl(data_dir / "corrections.jsonl", [])
        _write_jsonl(data_dir / "workflows.jsonl", [])

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_effectiveness(project, days=30)

        # エラー減少 → スコア > 0.5
        assert score > 0.5

    def test_no_data(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        _write_jsonl(data_dir / "errors.jsonl", [])
        _write_jsonl(data_dir / "corrections.jsonl", [])
        _write_jsonl(data_dir / "workflows.jsonl", [])

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_effectiveness(project, days=30)

        # 中立スコア
        assert 0.4 <= score <= 0.6

    def test_workflows_completing(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        recent_ts = _days_ago_iso(5)

        workflows = [
            {"workflow_id": f"wf-{i}", "step_count": 3, "started_at": recent_ts} for i in range(8)
        ] + [
            {"workflow_id": f"wf-x{i}", "step_count": 1, "started_at": recent_ts} for i in range(2)
        ]
        _write_jsonl(data_dir / "errors.jsonl", [])
        _write_jsonl(data_dir / "corrections.jsonl", [])
        _write_jsonl(data_dir / "workflows.jsonl", workflows)

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_effectiveness(project, days=30)

        # 80% 完走 → 高めスコア
        assert score > 0.5


class TestScoreImplicitReward:
    def test_high_success_rate(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        now_ts = _days_ago_iso(1)

        # 10 invocations, no corrections → 100% success
        records = [
            {"skill_name": "skill-a", "project": tmp_path.name, "timestamp": now_ts, "session_id": "s1"}
            for _ in range(10)
        ]
        _write_jsonl(data_dir / "usage.jsonl", records)
        _write_jsonl(data_dir / "corrections.jsonl", [])

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_implicit_reward(project, days=30)

        # 100% success + repeat usage → high score
        assert score >= 0.8

    def test_no_corrections_data(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        now_ts = _days_ago_iso(1)

        records = [
            {"skill_name": "skill-a", "project": tmp_path.name, "timestamp": now_ts, "session_id": "s1"},
        ]
        _write_jsonl(data_dir / "usage.jsonl", records)
        _write_jsonl(data_dir / "corrections.jsonl", [])

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_implicit_reward(project, days=30)

        # corrections 空 → 全 success (1.0) → score = 0.6*1.0 + 0.4*0.0 = 0.6
        assert score == pytest.approx(0.6, abs=0.01)

    def test_with_corrections_in_window(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        base_ts = _days_ago_iso(1)

        from datetime import datetime, timedelta, timezone
        base_dt = datetime.fromisoformat(base_ts.replace("Z", "+00:00"))
        corr_ts = (base_dt + timedelta(seconds=30)).isoformat()

        records = [
            {"skill_name": "skill-a", "project": tmp_path.name, "timestamp": base_ts, "session_id": "s1"},
        ]
        corrections = [
            {"correction_type": "stop", "timestamp": corr_ts, "session_id": "s1",
             "project_path": f"/path/{tmp_path.name}"},
        ]
        _write_jsonl(data_dir / "usage.jsonl", records)
        _write_jsonl(data_dir / "corrections.jsonl", corrections)

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            score = telemetry.score_implicit_reward(project, days=30)

        # 1 invoke with correction within 60s → 0% success → score = 0.6*0.0 + 0.4*0.0 = 0.0
        assert score == pytest.approx(0.0, abs=0.01)


class TestComputeTelemetryScore:
    def test_return_keys(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        _write_jsonl(data_dir / "usage.jsonl", [])
        _write_jsonl(data_dir / "errors.jsonl", [])
        _write_jsonl(data_dir / "corrections.jsonl", [])
        _write_jsonl(data_dir / "workflows.jsonl", [])
        _write_jsonl(data_dir / "sessions.jsonl", [])

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            result = telemetry.compute_telemetry_score(project, days=30)

        assert "overall" in result
        assert "utilization" in result
        assert "effectiveness" in result
        assert "implicit_reward" in result
        assert "data_sufficiency" in result

    def test_data_sufficiency_true(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        _write_jsonl(data_dir / "usage.jsonl", [])
        _write_jsonl(data_dir / "errors.jsonl", [])
        _write_jsonl(data_dir / "corrections.jsonl", [])
        _write_jsonl(data_dir / "workflows.jsonl", [])

        # 35 sessions spanning 10 days
        sessions = []
        for i in range(35):
            ts = _days_ago_iso(i % 10)
            sessions.append({"session_id": f"s{i}", "skill_count": 1, "error_count": 0,
                           "timestamp": ts, "project": tmp_path.name})
        _write_jsonl(data_dir / "sessions.jsonl", sessions)

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            result = telemetry.compute_telemetry_score(project, days=30)

        assert result["data_sufficiency"] is True

    def test_data_sufficiency_false(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        _write_jsonl(data_dir / "usage.jsonl", [])
        _write_jsonl(data_dir / "errors.jsonl", [])
        _write_jsonl(data_dir / "corrections.jsonl", [])
        _write_jsonl(data_dir / "workflows.jsonl", [])

        # Only 5 sessions
        sessions = [
            {"session_id": f"s{i}", "skill_count": 1, "error_count": 0,
             "timestamp": _now_iso(), "project": tmp_path.name}
            for i in range(5)
        ]
        _write_jsonl(data_dir / "sessions.jsonl", sessions)

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            result = telemetry.compute_telemetry_score(project, days=30)

        assert result["data_sufficiency"] is False
