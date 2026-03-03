"""analyze.py のテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# analyze.py をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# hooks/ もインポートパスに追加（common.py 用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "hooks"))

import common
import analyze


@pytest.fixture
def tmp_data_dir(tmp_path):
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def patch_data_dir(tmp_data_dir):
    with mock.patch.object(common, "DATA_DIR", tmp_data_dir):
        yield tmp_data_dir


class TestAnalyzeConsistency:
    """analyze_consistency() のテスト。"""

    def test_single_pattern_high_consistency(self):
        """全ワークフローが同じパターン → consistency_score = 1.0。"""
        workflows = [
            {"skill_name": "opsx:refine", "steps": [
                {"tool": "Agent:Explore", "intent_category": "code-exploration"},
                {"tool": "Agent:general-purpose", "intent_category": "implementation"},
            ]},
            {"skill_name": "opsx:refine", "steps": [
                {"tool": "Agent:Explore", "intent_category": "code-exploration"},
                {"tool": "Agent:general-purpose", "intent_category": "implementation"},
            ]},
        ]
        result = analyze.analyze_consistency(workflows)
        assert result["opsx:refine"]["consistency_score"] == 1.0
        assert result["opsx:refine"]["unique_patterns"] == 1

    def test_varied_patterns_low_consistency(self):
        """全ワークフローが異なるパターン → consistency_score が低い。"""
        workflows = [
            {"skill_name": "opsx:refine", "steps": [
                {"tool": "Agent:Explore"},
            ]},
            {"skill_name": "opsx:refine", "steps": [
                {"tool": "Agent:general-purpose"},
            ]},
            {"skill_name": "opsx:refine", "steps": [
                {"tool": "Agent:Plan"},
            ]},
        ]
        result = analyze.analyze_consistency(workflows)
        assert result["opsx:refine"]["consistency_score"] == pytest.approx(1 / 3, abs=0.01)
        assert result["opsx:refine"]["unique_patterns"] == 3

    def test_empty_workflows(self):
        """空のワークフローリスト。"""
        result = analyze.analyze_consistency([])
        assert result == {}

    def test_multiple_skills(self):
        """複数スキルが別々に集計される。"""
        workflows = [
            {"skill_name": "opsx:refine", "steps": [{"tool": "Agent:Explore"}]},
            {"skill_name": "opsx:apply", "steps": [{"tool": "Agent:general-purpose"}]},
        ]
        result = analyze.analyze_consistency(workflows)
        assert "opsx:refine" in result
        assert "opsx:apply" in result


class TestAnalyzeVariations:
    """analyze_variations() のテスト。"""

    def test_step_count_stats(self):
        """ステップ数の統計が正しい。"""
        workflows = [
            {"skill_name": "opsx:refine", "step_count": 2, "steps": [
                {"tool": "Agent:Explore", "intent_category": "code-exploration"},
                {"tool": "Agent:general-purpose", "intent_category": "implementation"},
            ]},
            {"skill_name": "opsx:refine", "step_count": 4, "steps": [
                {"tool": "Agent:Explore", "intent_category": "code-exploration"},
                {"tool": "Agent:Explore", "intent_category": "research"},
                {"tool": "Agent:Plan", "intent_category": "spec-review"},
                {"tool": "Agent:general-purpose", "intent_category": "implementation"},
            ]},
        ]
        result = analyze.analyze_variations(workflows)
        data = result["opsx:refine"]
        assert data["workflow_count"] == 2
        assert data["avg_steps"] == 3.0
        assert data["min_steps"] == 2
        assert data["max_steps"] == 4

    def test_tool_distribution(self):
        """ツール分布が正しい。"""
        workflows = [
            {"skill_name": "opsx:refine", "step_count": 2, "steps": [
                {"tool": "Agent:Explore", "intent_category": "code-exploration"},
                {"tool": "Agent:Explore", "intent_category": "research"},
            ]},
        ]
        result = analyze.analyze_variations(workflows)
        assert result["opsx:refine"]["tool_distribution"]["Agent:Explore"] == 2


class TestAnalyzeIntervention:
    """analyze_intervention() のテスト。"""

    def test_mixed_session(self):
        """contextualized と ad-hoc が混在するセッション。"""
        usage = [
            {"skill_name": "Agent:Explore", "session_id": "s1", "workflow_id": "wf-1"},
            {"skill_name": "Agent:Explore", "session_id": "s1", "workflow_id": None},
            {"skill_name": "opsx:refine", "session_id": "s1"},  # Skill は Agent ではない
        ]
        result = analyze.analyze_intervention(usage)
        assert result["total_agent_calls"] == 2
        assert result["contextualized"] == 1
        assert result["ad_hoc"] == 1
        assert result["sessions_with_mixed_patterns"] == 1

    def test_no_agents(self):
        """Agent 呼び出しがない場合。"""
        usage = [
            {"skill_name": "opsx:refine", "session_id": "s1"},
        ]
        result = analyze.analyze_intervention(usage)
        assert result["total_agent_calls"] == 0
        assert result["contextualized_ratio"] == 0.0


class TestAnalyzeDiscoverPrune:
    """analyze_discover_prune() のテスト。"""

    def test_source_breakdown(self):
        """source ごとのレコード数。"""
        usage = [
            {"skill_name": "Agent:Explore", "source": "backfill"},
            {"skill_name": "Agent:Explore", "source": "backfill"},
            {"skill_name": "Agent:Explore", "source": "trace", "parent_skill": "opsx:refine"},
            {"skill_name": "Agent:Explore", "source": "hook"},
        ]
        result = analyze.analyze_discover_prune(usage)
        assert result["backfill_records"] == 2
        assert result["trace_records"] == 1
        assert result["hook_records"] == 1

    def test_parent_skill_tracking(self):
        """parent_skill として参照されているスキルが検出される。"""
        usage = [
            {"skill_name": "Agent:Explore", "source": "trace", "parent_skill": "opsx:refine"},
            {"skill_name": "Agent:Explore", "source": "trace", "parent_skill": "opsx:apply"},
        ]
        result = analyze.analyze_discover_prune(usage)
        assert "opsx:refine" in result["skills_referenced_as_parent"]
        assert "opsx:apply" in result["skills_referenced_as_parent"]


class TestFormatReport:
    """format_report() のテスト。"""

    def test_report_contains_sections(self):
        """レポートに全セクションが含まれる。"""
        report = analyze.format_report(
            consistency={"opsx:refine": {
                "total_workflows": 5,
                "unique_patterns": 2,
                "consistency_score": 0.6,
                "most_common_pattern": "Agent:Explore → Agent:general-purpose",
                "most_common_count": 3,
                "all_patterns": {},
            }},
            variations={"opsx:refine": {
                "workflow_count": 5,
                "avg_steps": 2.5,
                "min_steps": 1,
                "max_steps": 4,
                "tool_distribution": {"Agent:Explore": 5},
                "intent_distribution": {"code-exploration": 3},
            }},
            intervention={
                "total_agent_calls": 10,
                "contextualized": 7,
                "ad_hoc": 3,
                "contextualized_ratio": 0.7,
                "sessions_with_mixed_patterns": 2,
                "total_sessions_with_agents": 5,
            },
            discover_prune={
                "total_records": 50,
                "backfill_records": 30,
                "trace_records": 10,
                "hook_records": 10,
                "skills_referenced_as_parent": ["opsx:refine"],
                "ad_hoc_agent_types": ["Agent:Explore"],
            },
            session_analysis={
                "total_sessions": 3,
                "avg_tool_calls": 15.0,
                "avg_duration_minutes": 12.5,
                "avg_errors": 0.5,
                "avg_human_messages": 4.0,
                "tool_distribution": {"Read": 10, "Edit": 5},
                "intent_distribution": {"implementation": 5, "code-exploration": 3},
                "sessions_by_duration": {"short": 1, "medium": 1, "long": 1},
                "sessions_by_project": {"rl-anything": 2, "ooishi-kun": 1},
            },
            workflow_count=5,
            usage_count=50,
            session_count=3,
        )
        assert "# Workflow Analysis Report" in report
        assert "## 1. ワークフロー構造の一貫性分析" in report
        assert "## 2. ステップバリエーション分析" in report
        assert "## 3. 介入分析" in report
        assert "## 4. Discover/Prune 比較データ" in report
        assert "## 5. セッション分析" in report
        assert "opsx:refine" in report
        assert "sessions.jsonl レコード数**: 3" in report


class TestAnalyzeSessions:
    """analyze_sessions() のテスト。"""

    def test_basic_stats(self):
        """基本統計が正しく計算される。"""
        sessions = [
            {
                "total_tool_calls": 10,
                "session_duration_seconds": 600,
                "error_count": 1,
                "human_message_count": 3,
                "tool_counts": {"Read": 5, "Edit": 3, "Bash": 2},
                "user_intents": ["code-exploration", "implementation"],
            },
            {
                "total_tool_calls": 20,
                "session_duration_seconds": 1200,
                "error_count": 3,
                "human_message_count": 5,
                "tool_counts": {"Read": 8, "Write": 7, "Grep": 5},
                "user_intents": ["implementation", "research", "implementation"],
            },
        ]
        result = analyze.analyze_sessions(sessions)
        assert result["total_sessions"] == 2
        assert result["avg_tool_calls"] == 15.0
        assert result["avg_duration_minutes"] == 15.0  # (600+1200)/2/60
        assert result["avg_errors"] == 2.0
        assert result["avg_human_messages"] == 4.0
        assert result["tool_distribution"]["Read"] == 13  # 5+8
        assert result["intent_distribution"]["implementation"] == 3  # 1+2

    def test_project_distribution(self):
        """プロジェクト別セッション数が集計される。"""
        sessions = [
            {"total_tool_calls": 5, "session_duration_seconds": 60, "error_count": 0,
             "human_message_count": 1, "tool_counts": {}, "user_intents": [], "project_name": "rl-anything"},
            {"total_tool_calls": 3, "session_duration_seconds": 60, "error_count": 0,
             "human_message_count": 1, "tool_counts": {}, "user_intents": [], "project_name": "rl-anything"},
            {"total_tool_calls": 8, "session_duration_seconds": 60, "error_count": 0,
             "human_message_count": 1, "tool_counts": {}, "user_intents": [], "project_name": "ooishi-kun"},
        ]
        result = analyze.analyze_sessions(sessions)
        assert result["sessions_by_project"]["rl-anything"] == 2
        assert result["sessions_by_project"]["ooishi-kun"] == 1

    def test_duration_buckets(self):
        """セッション長のバケット分類。"""
        sessions = [
            {"total_tool_calls": 1, "session_duration_seconds": 60, "error_count": 0,
             "human_message_count": 1, "tool_counts": {}, "user_intents": []},   # short
            {"total_tool_calls": 1, "session_duration_seconds": 600, "error_count": 0,
             "human_message_count": 1, "tool_counts": {}, "user_intents": []},   # medium
            {"total_tool_calls": 1, "session_duration_seconds": 2000, "error_count": 0,
             "human_message_count": 1, "tool_counts": {}, "user_intents": []},   # long
            {"total_tool_calls": 1, "session_duration_seconds": 3600, "error_count": 0,
             "human_message_count": 1, "tool_counts": {}, "user_intents": []},   # long
        ]
        result = analyze.analyze_sessions(sessions)
        assert result["sessions_by_duration"]["short"] == 1
        assert result["sessions_by_duration"]["medium"] == 1
        assert result["sessions_by_duration"]["long"] == 2

    def test_empty_sessions(self):
        """空のセッションリスト。"""
        result = analyze.analyze_sessions([])
        assert result["total_sessions"] == 0
        assert result["avg_tool_calls"] == 0


class TestGetProjectSessionIds:
    """get_project_session_ids() のテスト。"""

    def test_matching_project(self, patch_data_dir):
        """該当プロジェクトの session_id が返される。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        sessions_file.write_text(
            json.dumps({"session_id": "s1", "project_name": "my-project"}) + "\n"
            + json.dumps({"session_id": "s2", "project_name": "other-project"}) + "\n"
            + json.dumps({"session_id": "s3", "project_name": "my-project"}) + "\n",
            encoding="utf-8",
        )
        result = analyze.get_project_session_ids("my-project")
        assert result == {"s1", "s3"}

    def test_no_matching_project(self, patch_data_dir):
        """該当プロジェクトがない場合は空セットを返す。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        sessions_file.write_text(
            json.dumps({"session_id": "s1", "project_name": "other"}) + "\n",
            encoding="utf-8",
        )
        result = analyze.get_project_session_ids("nonexistent")
        assert result == set()

    def test_records_without_project_name(self, patch_data_dir):
        """project_name がないレコード（observe hooks 経由）はフィルタ対象外。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        sessions_file.write_text(
            json.dumps({"session_id": "s1", "project_name": "my-project"}) + "\n"
            + json.dumps({"session_id": "s2"}) + "\n"  # project_name なし
            + json.dumps({"session_id": "s3", "project_name": ""}) + "\n",
            encoding="utf-8",
        )
        result = analyze.get_project_session_ids("my-project")
        assert result == {"s1"}

    def test_no_sessions_file(self, patch_data_dir):
        """sessions.jsonl が存在しない場合は空セットを返す。"""
        result = analyze.get_project_session_ids("any")
        assert result == set()


class TestLoadJsonlWithFilter:
    """load_jsonl() の session_ids フィルタテスト。"""

    def test_filter_by_session_ids(self, patch_data_dir):
        """session_ids で指定したレコードのみ返される。"""
        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"skill_name": "A", "session_id": "s1"}) + "\n"
            + json.dumps({"skill_name": "B", "session_id": "s2"}) + "\n"
            + json.dumps({"skill_name": "C", "session_id": "s1"}) + "\n",
            encoding="utf-8",
        )
        result = analyze.load_jsonl(usage_file, session_ids={"s1"})
        assert len(result) == 2
        assert all(r["session_id"] == "s1" for r in result)

    def test_no_filter(self, patch_data_dir):
        """session_ids=None の場合は全レコードを返す。"""
        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"skill_name": "A", "session_id": "s1"}) + "\n"
            + json.dumps({"skill_name": "B", "session_id": "s2"}) + "\n",
            encoding="utf-8",
        )
        result = analyze.load_jsonl(usage_file)
        assert len(result) == 2


class TestRunAnalysis:
    """run_analysis() の統合テスト。"""

    def test_with_data(self, patch_data_dir):
        """データがある場合にレポートが生成される。"""
        workflows_file = patch_data_dir / "workflows.jsonl"
        wf = {
            "workflow_id": "wf-test1",
            "skill_name": "opsx:refine",
            "session_id": "s1",
            "steps": [
                {"tool": "Agent:Explore", "intent_category": "code-exploration", "timestamp": "2025-01-01T00:00:00Z"},
            ],
            "step_count": 1,
            "started_at": "2025-01-01T00:00:00Z",
            "ended_at": "2025-01-01T00:01:00Z",
            "source": "backfill",
        }
        workflows_file.write_text(json.dumps(wf) + "\n", encoding="utf-8")

        usage_file = patch_data_dir / "usage.jsonl"
        usage = {
            "skill_name": "Agent:Explore",
            "session_id": "s1",
            "workflow_id": "wf-test1",
            "parent_skill": "opsx:refine",
            "source": "backfill",
        }
        usage_file.write_text(json.dumps(usage) + "\n", encoding="utf-8")

        sessions_file = patch_data_dir / "sessions.jsonl"
        session = {
            "session_id": "s1",
            "project_name": "test-project",
            "total_tool_calls": 5,
            "session_duration_seconds": 120,
            "error_count": 0,
            "human_message_count": 2,
            "tool_counts": {"Read": 3, "Agent": 2},
            "user_intents": ["code-exploration"],
            "source": "backfill",
        }
        sessions_file.write_text(json.dumps(session) + "\n", encoding="utf-8")

        report = analyze.run_analysis(project="test-project")
        assert "# Workflow Analysis Report" in report
        assert "opsx:refine" in report
        assert "## 5. セッション分析" in report

    def test_empty_data(self, patch_data_dir):
        """データがない場合も正常にレポートが生成される。"""
        report = analyze.run_analysis(project="nonexistent")
        assert "# Workflow Analysis Report" in report
        assert "0" in report

    def test_project_filter_excludes_other_projects(self, patch_data_dir):
        """--project フィルタが他プロジェクトのデータを除外する。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        sessions_file.write_text(
            json.dumps({"session_id": "s1", "project_name": "proj-a", "total_tool_calls": 5,
                         "session_duration_seconds": 60, "error_count": 0, "human_message_count": 1,
                         "tool_counts": {}, "user_intents": []}) + "\n"
            + json.dumps({"session_id": "s2", "project_name": "proj-b", "total_tool_calls": 3,
                           "session_duration_seconds": 60, "error_count": 0, "human_message_count": 1,
                           "tool_counts": {}, "user_intents": []}) + "\n",
            encoding="utf-8",
        )
        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"skill_name": "Agent:Explore", "session_id": "s1", "source": "backfill"}) + "\n"
            + json.dumps({"skill_name": "Agent:Plan", "session_id": "s2", "source": "backfill"}) + "\n",
            encoding="utf-8",
        )
        workflows_file = patch_data_dir / "workflows.jsonl"
        workflows_file.write_text(
            json.dumps({"workflow_id": "wf-1", "skill_name": "sk-a", "session_id": "s1",
                         "steps": [{"tool": "Agent:Explore"}], "step_count": 1}) + "\n"
            + json.dumps({"workflow_id": "wf-2", "skill_name": "sk-b", "session_id": "s2",
                           "steps": [{"tool": "Agent:Plan"}], "step_count": 1}) + "\n",
            encoding="utf-8",
        )

        report = analyze.run_analysis(project="proj-a")
        assert "Agent:Explore" in report
        assert "Agent:Plan" not in report

    def test_without_project_returns_all(self, patch_data_dir):
        """project=None の場合は全データを返す。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        sessions_file.write_text(
            json.dumps({"session_id": "s1", "project_name": "proj-a", "total_tool_calls": 5,
                         "session_duration_seconds": 60, "error_count": 0, "human_message_count": 1,
                         "tool_counts": {}, "user_intents": []}) + "\n"
            + json.dumps({"session_id": "s2", "project_name": "proj-b", "total_tool_calls": 3,
                           "session_duration_seconds": 60, "error_count": 0, "human_message_count": 1,
                           "tool_counts": {}, "user_intents": []}) + "\n",
            encoding="utf-8",
        )
        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"skill_name": "Agent:Explore", "session_id": "s1", "source": "backfill"}) + "\n"
            + json.dumps({"skill_name": "Agent:Plan", "session_id": "s2", "source": "backfill"}) + "\n",
            encoding="utf-8",
        )

        report = analyze.run_analysis(project=None)
        # project=None → 全2セッション・全2 usage レコードが含まれる
        assert "usage.jsonl レコード数**: 2" in report
        assert "sessions.jsonl レコード数**: 2" in report
        assert "proj-a" in report
        assert "proj-b" in report
