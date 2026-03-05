"""telemetry_query.py のユニットテスト。DuckDB あり/なし両方をテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import telemetry_query


@pytest.fixture
def usage_file(tmp_path):
    """テスト用 usage.jsonl を作成する。"""
    filepath = tmp_path / "usage.jsonl"
    records = [
        {"skill_name": "my-skill", "project": "atlas", "timestamp": "2026-03-01T00:00:00Z"},
        {"skill_name": "my-skill", "project": "atlas", "timestamp": "2026-03-01T01:00:00Z"},
        {"skill_name": "other-skill", "project": "beta", "timestamp": "2026-03-01T02:00:00Z"},
        {"skill_name": "my-skill", "project": None, "timestamp": "2026-03-01T03:00:00Z"},
        {"skill_name": "legacy-skill", "timestamp": "2026-03-01T04:00:00Z"},  # project フィールドなし
    ]
    filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return filepath


@pytest.fixture
def errors_file(tmp_path):
    """テスト用 errors.jsonl を作成する。"""
    filepath = tmp_path / "errors.jsonl"
    records = [
        {"tool_name": "Bash", "error": "fail1", "project": "atlas"},
        {"tool_name": "Bash", "error": "fail2", "project": "beta"},
        {"tool_name": "Bash", "error": "fail3", "project": None},
    ]
    filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return filepath


class TestFallback:
    """DuckDB なし（Python フォールバック）のテスト。"""

    def test_query_usage_all(self, usage_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage(usage_file=usage_file)
        assert len(result) == 5

    def test_query_usage_by_project(self, usage_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage(project="atlas", usage_file=usage_file)
        assert len(result) == 2
        assert all(r["project"] == "atlas" for r in result)

    def test_query_usage_include_unknown(self, usage_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage(
                project="atlas", include_unknown=True, usage_file=usage_file
            )
        # atlas: 2 + project=None: 1 + project未定義(legacy): 1 = 4
        # project フィールドなしのレコードは rec.get("project") が None
        assert len(result) == 4

    def test_query_usage_excludes_unknown_by_default(self, usage_file):
        """project フィルタ指定時、null レコードはデフォルトで除外。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage(project="atlas", usage_file=usage_file)
        projects = [r.get("project") for r in result]
        assert None not in projects

    def test_query_errors_by_project(self, errors_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_errors(project="atlas", errors_file=errors_file)
        assert len(result) == 1
        assert result[0]["error"] == "fail1"

    def test_query_skill_counts(self, usage_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_skill_counts(project="atlas", usage_file=usage_file)
        assert len(result) == 1
        assert result[0]["skill_name"] == "my-skill"
        assert result[0]["count"] == 2

    def test_query_skill_counts_min_count(self, usage_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_skill_counts(
                min_count=3, usage_file=usage_file
            )
        # my-skill: 3回 (atlas*2 + null*1), other-skill: 1, legacy-skill: 1
        assert len(result) == 1
        assert result[0]["skill_name"] == "my-skill"

    def test_query_nonexistent_file(self, tmp_path):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage(usage_file=tmp_path / "nope.jsonl")
        assert result == []


class TestDuckDB:
    """DuckDB ありのテスト。DuckDB 未インストールの場合はスキップ。"""

    @pytest.fixture(autouse=True)
    def _skip_if_no_duckdb(self):
        if not telemetry_query.HAS_DUCKDB:
            pytest.skip("duckdb not installed")

    def test_query_usage_all(self, usage_file):
        result = telemetry_query.query_usage(usage_file=usage_file)
        assert len(result) == 5

    def test_query_usage_by_project(self, usage_file):
        result = telemetry_query.query_usage(project="atlas", usage_file=usage_file)
        assert len(result) == 2

    def test_query_usage_include_unknown(self, usage_file):
        result = telemetry_query.query_usage(
            project="atlas", include_unknown=True, usage_file=usage_file
        )
        # atlas: 2 + null/missing: 2 = 4
        assert len(result) == 4

    def test_query_errors_by_project(self, errors_file):
        result = telemetry_query.query_errors(project="atlas", errors_file=errors_file)
        assert len(result) == 1

    def test_query_skill_counts(self, usage_file):
        result = telemetry_query.query_skill_counts(project="atlas", usage_file=usage_file)
        assert len(result) == 1
        assert result[0]["skill_name"] == "my-skill"
        assert result[0]["count"] == 2

    def test_query_skill_counts_min_count(self, usage_file):
        result = telemetry_query.query_skill_counts(min_count=5, usage_file=usage_file)
        assert result == []

    def test_corrupt_jsonl_ignored(self, tmp_path):
        """不正な JSON 行は ignore_errors=true でスキップされる。"""
        filepath = tmp_path / "corrupt.jsonl"
        filepath.write_text(
            '{"skill_name": "ok", "project": "atlas"}\n'
            'NOT JSON\n'
            '{"skill_name": "ok2", "project": "atlas"}\n'
        )
        result = telemetry_query.query_usage(project="atlas", usage_file=filepath)
        assert len(result) == 2
