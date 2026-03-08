#!/usr/bin/env python3
"""environment.py の統合テスト"""

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

_env_path = _rl_dir / "fitness" / "environment.py"
_spec = importlib.util.spec_from_file_location("environment", _env_path)
environment = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(environment)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _days_ago_iso(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def _make_project(tmp_path):
    """テスト用プロジェクトを作成する。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "CLAUDE.md").write_text("# Project\n\n## Skills\n\n- sample-skill: A sample\n")

    rules_dir = claude_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "sample.md").write_text("# Rule\nDo this.\n")

    skill_dir = claude_dir / "skills" / "sample-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = "# Sample Skill\n\n## Usage\n\nUse it.\n\n## Steps\n\n" + "\n".join([f"Step {i}" for i in range(50)])
    (skill_dir / "SKILL.md").write_text(content)

    mem_dir = claude_dir / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "MEMORY.md").write_text("# Memory\n\n## Notes\n\nSome notes.\n")

    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": ["echo test"]}]}}
    (claude_dir / "settings.json").write_text(json.dumps(settings))

    return tmp_path


class TestComputeEnvironmentFitness:
    def test_both_sources_available(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        _write_jsonl(data_dir / "usage.jsonl", [])
        _write_jsonl(data_dir / "errors.jsonl", [])
        _write_jsonl(data_dir / "corrections.jsonl", [])
        _write_jsonl(data_dir / "workflows.jsonl", [])

        # 十分なセッション数
        sessions = []
        for i in range(35):
            ts = _days_ago_iso(i % 10)
            sessions.append({"session_id": f"s{i}", "skill_count": 1, "error_count": 0,
                           "timestamp": ts, "project": tmp_path.name})
        _write_jsonl(data_dir / "sessions.jsonl", sessions)

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            result = environment.compute_environment_fitness(project, days=30)

        assert "overall" in result
        assert "sources" in result
        assert "coherence" in result["sources"]
        assert "telemetry" in result["sources"]
        # ブレンド計算: coherence * 0.4 + telemetry * 0.6
        coh = result["coherence"]["overall"]
        tel = result["telemetry"]["overall"]
        expected = round(coh * 0.4 + tel * 0.6, 4)
        assert abs(result["overall"] - expected) < 0.01

    def test_telemetry_insufficient(self, tmp_path):
        project = _make_project(tmp_path)
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        _write_jsonl(data_dir / "usage.jsonl", [])
        _write_jsonl(data_dir / "errors.jsonl", [])
        _write_jsonl(data_dir / "corrections.jsonl", [])
        _write_jsonl(data_dir / "workflows.jsonl", [])

        # 不十分なセッション
        sessions = [
            {"session_id": f"s{i}", "skill_count": 1, "error_count": 0,
             "timestamp": _now_iso(), "project": tmp_path.name}
            for i in range(5)
        ]
        _write_jsonl(data_dir / "sessions.jsonl", sessions)

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            result = environment.compute_environment_fitness(project, days=30)

        assert result["sources"] == ["coherence"]
        # coherence のみで算出
        assert result["overall"] == result["coherence"]["overall"]

    def test_empty_project(self, tmp_path):
        data_dir = tmp_path / "_data"
        data_dir.mkdir()
        _write_jsonl(data_dir / "sessions.jsonl", [])
        _write_jsonl(data_dir / "usage.jsonl", [])
        _write_jsonl(data_dir / "errors.jsonl", [])
        _write_jsonl(data_dir / "corrections.jsonl", [])
        _write_jsonl(data_dir / "workflows.jsonl", [])

        with mock.patch("telemetry_query.DATA_DIR", data_dir), \
             mock.patch("telemetry_query.HAS_DUCKDB", False):
            result = environment.compute_environment_fitness(tmp_path, days=30)

        # coherence は算出可能（低スコア）、telemetry は不足
        assert "overall" in result
