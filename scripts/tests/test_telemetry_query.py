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


class TestTimeRangeFallback:
    """since/until 時間範囲フィルタのテスト（Python フォールバック）。"""

    def test_query_usage_with_since(self, usage_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage(
                usage_file=usage_file, since="2026-03-01T02:00:00Z"
            )
        # timestamp >= 02:00 → 02:00, 03:00, 04:00 の3件
        assert len(result) == 3

    def test_query_usage_with_until(self, usage_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage(
                usage_file=usage_file, until="2026-03-01T02:00:00Z"
            )
        # timestamp < 02:00 → 00:00, 01:00 の2件
        assert len(result) == 2

    def test_query_usage_with_range(self, usage_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage(
                usage_file=usage_file,
                since="2026-03-01T01:00:00Z",
                until="2026-03-01T03:00:00Z",
            )
        # 01:00 <= ts < 03:00 → 01:00, 02:00 の2件
        assert len(result) == 2

    def test_query_errors_with_time_range(self, tmp_path):
        filepath = tmp_path / "errors.jsonl"
        records = [
            {"error": "e1", "project": "a", "timestamp": "2026-02-01T00:00:00Z"},
            {"error": "e2", "project": "a", "timestamp": "2026-03-01T00:00:00Z"},
            {"error": "e3", "project": "a", "timestamp": "2026-04-01T00:00:00Z"},
        ]
        filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_errors(
                errors_file=filepath,
                since="2026-02-15T00:00:00Z",
                until="2026-03-15T00:00:00Z",
            )
        assert len(result) == 1
        assert result[0]["error"] == "e2"

    def test_query_sessions_with_since(self, tmp_path):
        filepath = tmp_path / "sessions.jsonl"
        records = [
            {"session_id": "s1", "timestamp": "2026-02-01T00:00:00Z", "project": "a"},
            {"session_id": "s2", "timestamp": "2026-03-01T00:00:00Z", "project": "a"},
        ]
        filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_sessions(
                sessions_file=filepath, since="2026-02-15T00:00:00Z"
            )
        assert len(result) == 1
        assert result[0]["session_id"] == "s2"

    def test_backward_compatible_no_time_params(self, usage_file):
        """since/until 未指定時は全レコード返却（後方互換）。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage(usage_file=usage_file)
        assert len(result) == 5


class TestCorrectionsQuery:
    """query_corrections() のテスト。"""

    @pytest.fixture
    def corrections_file(self, tmp_path):
        filepath = tmp_path / "corrections.jsonl"
        records = [
            {"correction_type": "stop", "timestamp": "2026-03-01T00:00:00Z",
             "session_id": "s1", "project_path": "/Users/foo/projects/atlas"},
            {"correction_type": "stop", "timestamp": "2026-03-02T00:00:00Z",
             "session_id": "s2", "project_path": "/Users/foo/projects/beta"},
            {"correction_type": "stop", "timestamp": "2026-03-03T00:00:00Z",
             "session_id": "s3", "project_path": ""},
        ]
        filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return filepath

    def test_query_all(self, corrections_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_corrections(corrections_file=corrections_file)
        assert len(result) == 3

    def test_query_by_project(self, corrections_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_corrections(
                project="atlas", corrections_file=corrections_file
            )
        assert len(result) == 1
        assert result[0]["session_id"] == "s1"

    def test_query_with_time_range(self, corrections_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_corrections(
                corrections_file=corrections_file,
                since="2026-03-01T12:00:00Z",
                until="2026-03-02T12:00:00Z",
            )
        assert len(result) == 1
        assert result[0]["session_id"] == "s2"


class TestWorkflowsQuery:
    """query_workflows() のテスト。"""

    @pytest.fixture
    def workflows_file(self, tmp_path):
        filepath = tmp_path / "workflows.jsonl"
        records = [
            {"workflow_id": "wf-1", "step_count": 3, "started_at": "2026-03-01T00:00:00Z"},
            {"workflow_id": "wf-2", "step_count": 1, "started_at": "2026-03-02T00:00:00Z"},
            {"workflow_id": "wf-3", "step_count": 5, "started_at": "2026-03-03T00:00:00Z"},
        ]
        filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return filepath

    def test_query_all(self, workflows_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_workflows(workflows_file=workflows_file)
        assert len(result) == 3

    def test_query_with_since(self, workflows_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_workflows(
                workflows_file=workflows_file, since="2026-03-02T00:00:00Z"
            )
        assert len(result) == 2

    def test_query_with_range(self, workflows_file):
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_workflows(
                workflows_file=workflows_file,
                since="2026-03-01T12:00:00Z",
                until="2026-03-02T12:00:00Z",
            )
        assert len(result) == 1
        assert result[0]["workflow_id"] == "wf-2"


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
