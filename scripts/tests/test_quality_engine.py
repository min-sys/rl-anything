"""quality_engine.py + telemetry_query.query_usage_by_skill_session のユニットテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import telemetry_query
import quality_engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_usage_records():
    """テスト用 usage.jsonl レコードを生成。

    セッション s1, s2, s3, s4, s5, s6 に対して:
    - s1〜s5: my-skill が発火 → 後続ツール呼び出しあり
    - s6: other-skill のみ
    """
    base_ts = "2026-03-01T00:0{}:00Z"
    records = []

    for i, sid in enumerate(["s1", "s2", "s3", "s4", "s5"]):
        minute = i * 6  # 0, 6, 12, 18, 24
        # Skill 発火
        records.append({
            "tool_name": "Skill",
            "skill_name": "my-skill",
            "session_id": sid,
            "timestamp": f"2026-03-01T00:{minute:02d}:00Z",
            "project": "atlas",
        })
        # 後続ツール呼び出し (Read, Edit, Bash)
        for j, tool in enumerate(["Read", "Edit", "Read", "Edit", "Read", "Edit", "Bash"]):
            sec = j + 1
            records.append({
                "tool_name": tool,
                "session_id": sid,
                "timestamp": f"2026-03-01T00:{minute:02d}:{sec:02d}Z",
                "project": "atlas",
            })
        # s1 にエラーを追加
        if sid == "s1":
            records.append({
                "tool_name": "Bash",
                "session_id": sid,
                "timestamp": f"2026-03-01T00:{minute:02d}:08Z",
                "project": "atlas",
                "error": "command failed",
            })

    # other-skill (s6)
    records.append({
        "tool_name": "Skill",
        "skill_name": "other-skill",
        "session_id": "s6",
        "timestamp": "2026-03-01T01:00:00Z",
        "project": "atlas",
    })
    records.append({
        "tool_name": "Read",
        "session_id": "s6",
        "timestamp": "2026-03-01T01:00:01Z",
        "project": "atlas",
    })

    return records


@pytest.fixture
def usage_file(tmp_path):
    """テスト用 usage.jsonl を作成する。"""
    filepath = tmp_path / "usage.jsonl"
    records = _make_usage_records()
    filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return filepath


@pytest.fixture
def few_sessions_usage_file(tmp_path):
    """MIN_SESSION_SAMPLES 未満のセッション数を持つ usage.jsonl。"""
    filepath = tmp_path / "usage.jsonl"
    records = []
    for sid in ["s1", "s2"]:
        records.append({
            "tool_name": "Skill",
            "skill_name": "rare-skill",
            "session_id": sid,
            "timestamp": "2026-03-01T00:00:00Z",
            "project": "atlas",
        })
        records.append({
            "tool_name": "Read",
            "session_id": sid,
            "timestamp": "2026-03-01T00:00:01Z",
            "project": "atlas",
        })
    filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return filepath


# ---------------------------------------------------------------------------
# Tests: query_usage_by_skill_session (telemetry_query.py)
# ---------------------------------------------------------------------------

class TestQueryUsageBySkillSession:
    """telemetry_query.query_usage_by_skill_session のテスト。"""

    def test_returns_grouped_sessions(self, usage_file):
        """my-skill の5セッションが正しくグループ化される。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", usage_file=usage_file
            )
        assert len(result) == 5
        session_ids = {r["session_id"] for r in result}
        assert session_ids == {"s1", "s2", "s3", "s4", "s5"}

    def test_tool_calls_count(self, usage_file):
        """各セッションのツール呼び出し数が正しい。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", usage_file=usage_file
            )
        # s1 には7ツール + 1エラーBash = 8, s2-s5 は7ツール
        by_session = {r["session_id"]: r for r in result}
        assert by_session["s1"]["tool_calls"] == 8
        assert by_session["s2"]["tool_calls"] == 7

    def test_read_edit_cycles(self, usage_file):
        """Read→Edit の反復回数が正しく計算される。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", usage_file=usage_file
            )
        by_session = {r["session_id"]: r for r in result}
        # パターン: Read, Edit, Read, Edit, Read, Edit, Bash → 3サイクル
        assert by_session["s2"]["read_edit_cycles"] == 3

    def test_errors_count(self, usage_file):
        """エラーありセッションのエラー数が正しい。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", usage_file=usage_file
            )
        by_session = {r["session_id"]: r for r in result}
        assert by_session["s1"]["errors"] == 1
        assert by_session["s2"]["errors"] == 0

    def test_duration_seconds(self, usage_file):
        """duration_seconds が正しく計算される。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", usage_file=usage_file
            )
        by_session = {r["session_id"]: r for r in result}
        # s1: 00:00:00 → 00:00:08 = 8秒
        assert by_session["s1"]["duration_seconds"] == 8.0
        # s2: 00:06:00 → 00:06:07 = 7秒
        assert by_session["s2"]["duration_seconds"] == 7.0

    def test_excludes_other_skills(self, usage_file):
        """other-skill のセッションは含まれない。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", usage_file=usage_file
            )
        session_ids = {r["session_id"] for r in result}
        assert "s6" not in session_ids

    def test_nonexistent_skill(self, usage_file):
        """存在しないスキルは空リストを返す。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "nonexistent-skill", usage_file=usage_file
            )
        assert result == []

    def test_empty_file(self, tmp_path):
        """空ファイルは空リストを返す。"""
        filepath = tmp_path / "usage.jsonl"
        filepath.write_text("")
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", usage_file=filepath
            )
        assert result == []

    def test_nonexistent_file(self, tmp_path):
        """ファイルが存在しない場合は空リストを返す。"""
        filepath = tmp_path / "nonexistent.jsonl"
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", usage_file=filepath
            )
        assert result == []

    def test_project_filter(self, tmp_path):
        """project フィルタが適用される。"""
        filepath = tmp_path / "usage.jsonl"
        records = [
            {"tool_name": "Skill", "skill_name": "my-skill", "session_id": "s1",
             "timestamp": "2026-03-01T00:00:00Z", "project": "atlas"},
            {"tool_name": "Read", "session_id": "s1",
             "timestamp": "2026-03-01T00:00:01Z", "project": "atlas"},
            {"tool_name": "Skill", "skill_name": "my-skill", "session_id": "s2",
             "timestamp": "2026-03-01T00:00:00Z", "project": "beta"},
            {"tool_name": "Read", "session_id": "s2",
             "timestamp": "2026-03-01T00:00:01Z", "project": "beta"},
        ]
        filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", project="atlas", usage_file=filepath
            )
        assert len(result) == 1
        assert result[0]["session_id"] == "s1"

    def test_trace_window_limits(self, tmp_path):
        """TRACE_WINDOW_MINUTES を超えるツール呼び出しは除外される。"""
        filepath = tmp_path / "usage.jsonl"
        records = [
            {"tool_name": "Skill", "skill_name": "my-skill", "session_id": "s1",
             "timestamp": "2026-03-01T00:00:00Z", "project": "atlas"},
            {"tool_name": "Read", "session_id": "s1",
             "timestamp": "2026-03-01T00:01:00Z", "project": "atlas"},
            # 6分後 → TRACE_WINDOW_MINUTES(5)を超える
            {"tool_name": "Edit", "session_id": "s1",
             "timestamp": "2026-03-01T00:06:00Z", "project": "atlas"},
        ]
        filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = telemetry_query.query_usage_by_skill_session(
                "my-skill", usage_file=filepath
            )
        assert len(result) == 1
        assert result[0]["tool_calls"] == 1  # Read のみ、Edit は除外


# ---------------------------------------------------------------------------
# Tests: analyze_traces (quality_engine.py)
# ---------------------------------------------------------------------------

class TestAnalyzeTraces:
    """quality_engine.analyze_traces のテスト。"""

    def test_returns_none_below_min_samples(self, few_sessions_usage_file):
        """MIN_SESSION_SAMPLES 未満なら None を返す。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = quality_engine.analyze_traces(
                "rare-skill", usage_file=few_sessions_usage_file
            )
        assert result is None

    def test_returns_confusion_score(self, usage_file):
        """十分なセッション数があれば confusion_score を含む dict を返す。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = quality_engine.analyze_traces(
                "my-skill", usage_file=usage_file
            )
        assert result is not None
        assert "confusion_score" in result
        assert 0.0 <= result["confusion_score"] <= 1.0

    def test_confusion_score_components(self, usage_file):
        """confusion_score の各コンポーネントが返される。"""
        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = quality_engine.analyze_traces(
                "my-skill", usage_file=usage_file
            )
        assert "tool_ratio_score" in result
        assert "read_edit_score" in result
        assert "error_score" in result
        assert "sample_count" in result

    def test_high_read_edit_cycles(self, tmp_path):
        """Read→Edit 反復が多いセッションは read_edit_score が高い。"""
        filepath = tmp_path / "usage.jsonl"
        records = []
        for sid in [f"s{i}" for i in range(6)]:
            records.append({
                "tool_name": "Skill", "skill_name": "confused-skill",
                "session_id": sid, "timestamp": "2026-03-01T00:00:00Z",
            })
            # 4回の Read→Edit サイクル（>= CONFUSION_READ_EDIT_CYCLE_MIN=3）
            for j in range(4):
                records.append({
                    "tool_name": "Read", "session_id": sid,
                    "timestamp": f"2026-03-01T00:00:{j*2+1:02d}Z",
                })
                records.append({
                    "tool_name": "Edit", "session_id": sid,
                    "timestamp": f"2026-03-01T00:00:{j*2+2:02d}Z",
                })
        filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        with mock.patch.object(telemetry_query, "HAS_DUCKDB", False):
            result = quality_engine.analyze_traces(
                "confused-skill", usage_file=filepath
            )
        assert result is not None
        # 全セッションが閾値以上 → read_edit_score = 1.0
        assert result["read_edit_score"] == 1.0


# ---------------------------------------------------------------------------
# Tests: recommend_patterns (quality_engine.py)
# ---------------------------------------------------------------------------

class TestRecommendPatterns:
    """quality_engine.recommend_patterns のテスト。"""

    def test_deploy_domain(self):
        """deploy キーワードで deploy ドメインを検出。"""
        content = "# Deploy Skill\nThis skill handles deployment to production."
        result = quality_engine.recommend_patterns({}, content)
        assert result["domain"] == "deploy"
        assert "plan_validate_execute" in result["required_missing"]
        assert "checklist" in result["required_missing"]

    def test_investigation_domain(self):
        """debug/investigate キーワードで investigation ドメインを検出。"""
        content = "# Debug Skill\nThis skill helps investigate and diagnose issues."
        result = quality_engine.recommend_patterns({}, content)
        assert result["domain"] == "investigation"
        assert "validation_loop" in result["required_missing"]

    def test_generation_domain(self):
        """generate/create キーワードで generation ドメインを検出。"""
        content = "# Generator\nThis skill will generate scaffolding and create new files."
        result = quality_engine.recommend_patterns({}, content)
        assert result["domain"] == "generation"
        assert "output_template" in result["required_missing"]

    def test_workflow_domain(self):
        """workflow/pipeline キーワードで workflow ドメインを検出。"""
        content = "# Workflow Skill\nManages the CI/CD pipeline flow with multiple steps."
        result = quality_engine.recommend_patterns({}, content)
        assert result["domain"] == "workflow"
        assert "checklist" in result["required_missing"]

    def test_reference_domain(self):
        """reference/guide キーワードで reference ドメインを検出。"""
        content = "# Reference Guide\nA lookup doc for API documentation."
        result = quality_engine.recommend_patterns({}, content)
        assert result["domain"] == "reference"
        assert "progressive_disclosure" in result["required_missing"]

    def test_default_fallback(self):
        """マッチしないコンテンツは default にフォールバック。"""
        content = "# My Skill\nDoes something useful."
        result = quality_engine.recommend_patterns({}, content)
        assert result["domain"] == "default"
        assert result["required_missing"] == []
        assert "gotchas" in result["recommended_missing"]

    def test_detected_patterns_excluded(self):
        """detected_patterns に含まれるパターンは missing から除外。"""
        content = "# Deploy Skill\nHandles deployment."
        detected = {"used_patterns": ["plan_validate_execute", "checklist"]}
        result = quality_engine.recommend_patterns(detected, content)
        assert result["domain"] == "deploy"
        assert "plan_validate_execute" not in result["required_missing"]
        assert "checklist" not in result["required_missing"]


# ---------------------------------------------------------------------------
# Tests: compute_overall_score (quality_engine.py)
# ---------------------------------------------------------------------------

class TestComputeOverallScore:
    """quality_engine.compute_overall_score のテスト。"""

    def test_all_axes(self):
        """全軸ありの場合の重み付き平均。"""
        score = quality_engine.compute_overall_score(
            pattern_score=0.8,
            confusion_score=0.2,
            context_efficiency=0.9,
            defaults_first_score=0.7,
        )
        # pattern: 0.35*0.8 = 0.28
        # inverse_confusion: 0.25*(1-0.2) = 0.20
        # context: 0.20*0.9 = 0.18
        # defaults: 0.20*0.7 = 0.14
        # total = 0.80
        assert abs(score - 0.80) < 0.001

    def test_confusion_none(self):
        """confusion_score=None の場合、残り軸で再正規化。"""
        score = quality_engine.compute_overall_score(
            pattern_score=1.0,
            confusion_score=None,
            context_efficiency=1.0,
            defaults_first_score=1.0,
        )
        # inverse_confusion 除外、残り weight = 0.35+0.20+0.20 = 0.75
        # 再正規化: 各 weight / 0.75
        # all 1.0 なので score = 1.0
        assert abs(score - 1.0) < 0.001

    def test_confusion_none_mixed(self):
        """confusion_score=None で値がバラバラの場合。"""
        score = quality_engine.compute_overall_score(
            pattern_score=0.6,
            confusion_score=None,
            context_efficiency=0.9,
            defaults_first_score=0.3,
        )
        # 残り weight = 0.75
        # pattern: (0.35/0.75)*0.6 = 0.28
        # context: (0.20/0.75)*0.9 = 0.24
        # defaults: (0.20/0.75)*0.3 = 0.08
        # total = 0.60
        assert abs(score - 0.60) < 0.01

    def test_boundary_zero(self):
        """全軸 0.0 の場合。"""
        score = quality_engine.compute_overall_score(0.0, 1.0, 0.0, 0.0)
        # inverse_confusion = 1 - 1.0 = 0.0
        assert score == 0.0

    def test_boundary_one(self):
        """全軸最大の場合。"""
        score = quality_engine.compute_overall_score(1.0, 0.0, 1.0, 1.0)
        # inverse_confusion = 1 - 0.0 = 1.0
        assert abs(score - 1.0) < 0.001

    def test_clamped(self):
        """結果が 0.0-1.0 にクランプされる。"""
        # 通常ありえないが、念のため
        score = quality_engine.compute_overall_score(1.5, -0.5, 1.5, 1.5)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Tests: record_quality_score (quality_engine.py)
# ---------------------------------------------------------------------------

class TestRecordQualityScore:
    """quality_engine.record_quality_score のテスト。"""

    def test_writes_jsonl(self, tmp_path):
        """quality-scores.jsonl に正しく書き込む。"""
        scores = {
            "pattern_score": 0.75,
            "confusion_score": 0.2,
            "context_efficiency": 0.85,
            "defaults_first_score": 0.85,
            "overall": 0.78,
        }
        quality_engine.record_quality_score("my-skill", scores, data_dir=tmp_path)

        filepath = tmp_path / "quality-scores.jsonl"
        assert filepath.exists()
        record = json.loads(filepath.read_text().strip())
        assert record["skill"] == "my-skill"
        assert record["pattern_score"] == 0.75
        assert record["overall"] == 0.78
        assert "timestamp" in record

    def test_appends_multiple(self, tmp_path):
        """複数回呼び出しで追記される。"""
        scores1 = {"pattern_score": 0.5, "overall": 0.5}
        scores2 = {"pattern_score": 0.8, "overall": 0.8}
        quality_engine.record_quality_score("skill-a", scores1, data_dir=tmp_path)
        quality_engine.record_quality_score("skill-b", scores2, data_dir=tmp_path)

        filepath = tmp_path / "quality-scores.jsonl"
        lines = [l for l in filepath.read_text().strip().split("\n") if l]
        assert len(lines) == 2
        assert json.loads(lines[0])["skill"] == "skill-a"
        assert json.loads(lines[1])["skill"] == "skill-b"
