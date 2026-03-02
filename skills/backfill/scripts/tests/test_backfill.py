"""backfill スクリプトのテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# backfill.py をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# hooks/ もインポートパスに追加（common.py 用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "hooks"))

import common
import backfill


@pytest.fixture
def tmp_data_dir(tmp_path):
    """テスト用の一時データディレクトリ。"""
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def patch_data_dir(tmp_data_dir):
    """common.DATA_DIR を一時ディレクトリに差し替える。"""
    with mock.patch.object(common, "DATA_DIR", tmp_data_dir):
        yield tmp_data_dir


@pytest.fixture
def transcript_dir(tmp_path):
    """テスト用のトランスクリプトディレクトリ。"""
    d = tmp_path / "transcripts"
    d.mkdir()
    return d


def make_assistant_record(
    session_id: str,
    tool_blocks: list,
    timestamp: str = "2025-06-15T10:30:00Z",
) -> str:
    """assistant レコードの JSONL 行を生成する。"""
    record = {
        "type": "assistant",
        "message": {"content": tool_blocks},
        "timestamp": timestamp,
        "sessionId": session_id,
        "uuid": "test-uuid",
    }
    return json.dumps(record, ensure_ascii=False)


def make_skill_tool_use(skill_name: str, args: str = "") -> dict:
    return {
        "type": "tool_use",
        "name": "Skill",
        "input": {"skill": skill_name, "args": args},
    }


def make_agent_tool_use(subagent_type: str, prompt: str = "test") -> dict:
    return {
        "type": "tool_use",
        "name": "Agent",
        "input": {"subagent_type": subagent_type, "prompt": prompt},
    }


class TestParseTranscript:
    """parse_transcript() のテスト。"""

    def test_skill_extraction(self, transcript_dir):
        """Skill ツール呼び出しが抽出される。"""
        tf = transcript_dir / "sess-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-001",
                [make_skill_tool_use("my-skill", "test.py")],
                "2025-06-15T10:30:00Z",
            )
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 1
        assert result.usage_records[0]["skill_name"] == "my-skill"
        assert result.usage_records[0]["session_id"] == "sess-001"
        assert result.usage_records[0]["timestamp"] == "2025-06-15T10:30:00Z"
        assert result.usage_records[0]["source"] == "backfill"
        assert result.errors == 0

    def test_agent_extraction(self, transcript_dir):
        """Agent ツール呼び出しが抽出される。"""
        tf = transcript_dir / "sess-002.jsonl"
        lines = [
            make_assistant_record(
                "sess-002",
                [make_agent_tool_use("Explore", "codebase を探索")],
                "2025-06-15T11:00:00Z",
            )
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 1
        assert result.usage_records[0]["skill_name"] == "Agent:Explore"
        assert result.usage_records[0]["subagent_type"] == "Explore"
        assert result.usage_records[0]["prompt"] == "codebase を探索"
        assert result.usage_records[0]["timestamp"] == "2025-06-15T11:00:00Z"
        assert result.usage_records[0]["source"] == "backfill"

    def test_agent_prompt_truncated(self, transcript_dir):
        """Agent の prompt が 200 文字に切り詰められる。"""
        long_prompt = "あ" * 300
        tf = transcript_dir / "sess-003.jsonl"
        lines = [
            make_assistant_record("sess-003", [make_agent_tool_use("Explore", long_prompt)])
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records[0]["prompt"]) == 200

    def test_agent_missing_subagent_type(self, transcript_dir):
        """subagent_type が未指定の場合 'unknown' になる。"""
        tf = transcript_dir / "sess-004.jsonl"
        record = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Agent", "input": {"prompt": "test"}}
                ]
            },
            "timestamp": "2025-06-15T12:00:00Z",
            "sessionId": "sess-004",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.usage_records[0]["subagent_type"] == "unknown"
        assert result.usage_records[0]["skill_name"] == "Agent:unknown"

    def test_agent_null_subagent_type(self, transcript_dir):
        """subagent_type が None の場合 'unknown' になる。"""
        tf = transcript_dir / "sess-005.jsonl"
        record = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Agent",
                        "input": {"subagent_type": None, "prompt": "test"},
                    }
                ]
            },
            "timestamp": "2025-06-15T12:00:00Z",
            "sessionId": "sess-005",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.usage_records[0]["subagent_type"] == "unknown"

    def test_invalid_json_skipped(self, transcript_dir):
        """不正 JSON 行はスキップされ errors がカウントされる。"""
        tf = transcript_dir / "sess-006.jsonl"
        lines = [
            "this is not valid json",
            make_assistant_record("sess-006", [make_skill_tool_use("valid-skill")]),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 1
        assert result.usage_records[0]["skill_name"] == "valid-skill"
        assert result.errors == 1

    def test_no_tool_use_skipped(self, transcript_dir):
        """tool_use のない assistant レコードはスキップ（エラーにならない）。"""
        tf = transcript_dir / "sess-007.jsonl"
        record = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hello"}]},
            "timestamp": "2025-06-15T12:00:00Z",
            "sessionId": "sess-007",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 0
        assert result.errors == 0

    def test_non_assistant_records_ignored(self, transcript_dir):
        """type != 'assistant' のレコードは無視される。"""
        tf = transcript_dir / "sess-008.jsonl"
        lines = [
            json.dumps({"type": "queue-operation", "timestamp": "2025-06-15T10:00:00Z", "sessionId": "sess-008"}),
            json.dumps({"type": "human", "timestamp": "2025-06-15T10:01:00Z", "sessionId": "sess-008"}),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 0
        assert result.errors == 0

    def test_multiple_tool_uses_in_one_record(self, transcript_dir):
        """1つの assistant レコードに Skill→Agent→Skill がある場合、ワークフロー境界が正しい。"""
        tf = transcript_dir / "sess-009.jsonl"
        lines = [
            make_assistant_record(
                "sess-009",
                [
                    make_skill_tool_use("skill-a"),
                    make_agent_tool_use("Explore"),
                    make_skill_tool_use("skill-b"),
                ],
            )
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 3
        assert result.usage_records[0]["skill_name"] == "skill-a"
        assert result.usage_records[1]["skill_name"] == "Agent:Explore"
        assert result.usage_records[2]["skill_name"] == "skill-b"

    def test_timestamp_from_record(self, transcript_dir):
        """timestamp はレコードのトップレベル timestamp から取得される。"""
        tf = transcript_dir / "sess-010.jsonl"
        lines = [
            make_assistant_record("sess-010", [make_skill_tool_use("ts-test")], "2025-12-25T00:00:00Z"),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.usage_records[0]["timestamp"] == "2025-12-25T00:00:00Z"


class TestWorkflowTracking:
    """ワークフロー追跡のテスト。"""

    def test_skill_then_agent_creates_workflow(self, transcript_dir):
        """Skill → Agent のシーケンスがワークフローレコードを生成する。"""
        tf = transcript_dir / "sess-wf-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-wf-001",
                [make_skill_tool_use("opsx:refine")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-wf-001",
                [make_agent_tool_use("Explore", "explore the codebase structure")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-wf-001",
                [make_agent_tool_use("general-purpose", "implement the changes")],
                "2025-06-15T10:02:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        # usage_records: Skill + 2 Agent = 3
        assert len(result.usage_records) == 3

        # Agent に parent_skill/workflow_id が付与されている
        agent1 = result.usage_records[1]
        assert agent1["parent_skill"] == "opsx:refine"
        assert agent1["workflow_id"] is not None
        assert agent1["workflow_id"].startswith("wf-")

        agent2 = result.usage_records[2]
        assert agent2["parent_skill"] == "opsx:refine"
        assert agent2["workflow_id"] == agent1["workflow_id"]

        # workflow_records: 1つのワークフロー
        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["skill_name"] == "opsx:refine"
        assert wf["step_count"] == 2
        assert len(wf["steps"]) == 2
        assert wf["steps"][0]["tool"] == "Agent:Explore"
        assert wf["steps"][0]["intent_category"] == "code-exploration"
        assert wf["steps"][1]["tool"] == "Agent:general-purpose"
        assert wf["steps"][1]["intent_category"] == "implementation"
        assert wf["source"] == "backfill"
        assert wf["started_at"] == "2025-06-15T10:00:00Z"
        assert wf["ended_at"] == "2025-06-15T10:02:00Z"

    def test_ad_hoc_agent_no_workflow(self, transcript_dir):
        """Skill なしの Agent は ad-hoc（parent_skill: null, workflow なし）。"""
        tf = transcript_dir / "sess-wf-002.jsonl"
        lines = [
            make_assistant_record(
                "sess-wf-002",
                [make_agent_tool_use("Explore", "explore manually")],
                "2025-06-15T10:00:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 1
        assert result.usage_records[0]["parent_skill"] is None
        assert result.usage_records[0]["workflow_id"] is None
        assert len(result.workflow_records) == 0

    def test_skill_without_agent_no_workflow(self, transcript_dir):
        """Skill だけで Agent がない場合、workflow_records に追加しない。"""
        tf = transcript_dir / "sess-wf-003.jsonl"
        lines = [
            make_assistant_record(
                "sess-wf-003",
                [make_skill_tool_use("my-skill")],
                "2025-06-15T10:00:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 1
        assert len(result.workflow_records) == 0

    def test_multiple_skills_create_separate_workflows(self, transcript_dir):
        """複数の Skill が別々のワークフローを生成する。"""
        tf = transcript_dir / "sess-wf-004.jsonl"
        lines = [
            make_assistant_record(
                "sess-wf-004",
                [make_skill_tool_use("opsx:refine")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-wf-004",
                [make_agent_tool_use("Explore", "explore structure")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-wf-004",
                [make_skill_tool_use("opsx:apply")],
                "2025-06-15T10:02:00Z",
            ),
            make_assistant_record(
                "sess-wf-004",
                [make_agent_tool_use("general-purpose", "implement feature")],
                "2025-06-15T10:03:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        assert len(result.workflow_records) == 2
        wf1 = result.workflow_records[0]
        wf2 = result.workflow_records[1]

        assert wf1["skill_name"] == "opsx:refine"
        assert wf1["step_count"] == 1
        assert wf2["skill_name"] == "opsx:apply"
        assert wf2["step_count"] == 1

        # workflow_id が異なる
        assert wf1["workflow_id"] != wf2["workflow_id"]

    def test_ad_hoc_then_skill_workflow(self, transcript_dir):
        """ad-hoc Agent の後に Skill → Agent がある場合、混在パターン。"""
        tf = transcript_dir / "sess-wf-005.jsonl"
        lines = [
            make_assistant_record(
                "sess-wf-005",
                [make_agent_tool_use("Explore", "ad-hoc explore")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-wf-005",
                [make_skill_tool_use("opsx:refine")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-wf-005",
                [make_agent_tool_use("Explore", "explore the spec requirements")],
                "2025-06-15T10:02:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        # ad-hoc Agent は parent_skill=None
        ad_hoc = result.usage_records[0]
        assert ad_hoc["parent_skill"] is None

        # Skill ワークフロー内の Agent は parent_skill あり
        wf_agent = result.usage_records[2]
        assert wf_agent["parent_skill"] == "opsx:refine"

        assert len(result.workflow_records) == 1
        assert result.workflow_records[0]["skill_name"] == "opsx:refine"
        assert result.workflow_records[0]["step_count"] == 1

    def test_workflow_schema_matches_session_summary(self, transcript_dir):
        """workflow_records のスキーマが session_summary.py の trace レコードと同じ。"""
        tf = transcript_dir / "sess-wf-006.jsonl"
        lines = [
            make_assistant_record(
                "sess-wf-006",
                [make_skill_tool_use("opsx:refine")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-wf-006",
                [make_agent_tool_use("Explore", "explore")],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        wf = result.workflow_records[0]

        # 必須フィールドの存在確認
        required_fields = [
            "workflow_id", "skill_name", "session_id",
            "steps", "step_count", "started_at", "ended_at", "source",
        ]
        for field in required_fields:
            assert field in wf, f"Missing field: {field}"

        # steps の構造確認
        step = wf["steps"][0]
        assert "tool" in step
        assert "intent_category" in step
        assert "timestamp" in step


class TestDeduplication:
    """重複防止のテスト。"""

    def test_already_backfilled_session_skipped(self, patch_data_dir, transcript_dir):
        """バックフィル済みセッションはスキップされる。"""
        # 既存バックフィルデータを作成
        usage_file = patch_data_dir / "usage.jsonl"
        existing = {"skill_name": "old", "session_id": "sess-001", "source": "backfill"}
        usage_file.write_text(json.dumps(existing) + "\n", encoding="utf-8")

        # トランスクリプトを作成
        tf = transcript_dir / "sess-001.jsonl"
        tf.write_text(
            make_assistant_record("sess-001", [make_skill_tool_use("new-skill")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["skipped_sessions"] == 1
        assert summary["sessions_processed"] == 0
        # 既存データが増えていないことを確認
        lines = usage_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_new_session_processed(self, patch_data_dir, transcript_dir):
        """新しいセッションは処理される。"""
        tf = transcript_dir / "sess-new.jsonl"
        tf.write_text(
            make_assistant_record("sess-new", [make_skill_tool_use("my-skill")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["sessions_processed"] == 1
        assert summary["skill_calls"] == 1

    def test_force_reprocesses_all(self, patch_data_dir, transcript_dir):
        """--force で既存バックフィルを削除して再処理する。"""
        usage_file = patch_data_dir / "usage.jsonl"
        existing_backfill = {"skill_name": "old", "session_id": "sess-001", "source": "backfill"}
        existing_realtime = {"skill_name": "realtime", "session_id": "sess-001", "source": "hook"}
        usage_file.write_text(
            json.dumps(existing_backfill) + "\n" + json.dumps(existing_realtime) + "\n",
            encoding="utf-8",
        )

        tf = transcript_dir / "sess-001.jsonl"
        tf.write_text(
            make_assistant_record("sess-001", [make_skill_tool_use("new-skill")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=True)

        assert summary["sessions_processed"] == 1
        assert summary["skipped_sessions"] == 0

        # リアルタイムデータは残り、新しいバックフィルデータが追加されている
        lines = usage_file.read_text(encoding="utf-8").strip().splitlines()
        records = [json.loads(l) for l in lines]
        sources = [r.get("source") for r in records]
        assert "hook" in sources  # リアルタイムデータは保持
        assert "backfill" in sources  # 新しいバックフィルデータ


class TestSummaryOutput:
    """サマリ出力のテスト。"""

    def test_summary_format(self, patch_data_dir, transcript_dir):
        """サマリが正しい形式で返される（workflows カウント含む）。"""
        tf1 = transcript_dir / "sess-a.jsonl"
        tf1.write_text(
            make_assistant_record("sess-a", [
                make_skill_tool_use("skill-1"),
                make_agent_tool_use("Explore"),
            ]),
            encoding="utf-8",
        )
        tf2 = transcript_dir / "sess-b.jsonl"
        tf2.write_text(
            "invalid json line\n"
            + make_assistant_record("sess-b", [make_skill_tool_use("skill-2")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["sessions_processed"] == 2
        assert summary["skill_calls"] == 2
        assert summary["agent_calls"] == 1
        assert summary["errors"] == 1
        assert summary["skipped_sessions"] == 0
        assert "workflows" in summary
        # sess-a: Skill→Agent = 1 ワークフロー、sess-b: Skill のみ = 0 ワークフロー
        assert summary["workflows"] == 1

    def test_workflows_written_to_jsonl(self, patch_data_dir, transcript_dir):
        """backfill() が workflows.jsonl にレコードを書き出す。"""
        tf = transcript_dir / "sess-wf.jsonl"
        lines = [
            make_assistant_record(
                "sess-wf",
                [make_skill_tool_use("opsx:refine")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-wf",
                [make_agent_tool_use("Explore", "explore codebase structure")],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["workflows"] == 1

        workflows_file = patch_data_dir / "workflows.jsonl"
        assert workflows_file.exists()
        wf = json.loads(workflows_file.read_text(encoding="utf-8").strip())
        assert wf["skill_name"] == "opsx:refine"
        assert wf["step_count"] == 1
        assert wf["source"] == "backfill"

    def test_force_removes_backfill_workflows(self, patch_data_dir, transcript_dir):
        """--force で backfill ワークフローが削除される（trace は保持）。"""
        workflows_file = patch_data_dir / "workflows.jsonl"
        backfill_wf = {"workflow_id": "wf-old", "source": "backfill", "skill_name": "old"}
        trace_wf = {"workflow_id": "wf-trace", "source": "trace", "skill_name": "trace"}
        workflows_file.write_text(
            json.dumps(backfill_wf) + "\n" + json.dumps(trace_wf) + "\n",
            encoding="utf-8",
        )

        tf = transcript_dir / "sess-force.jsonl"
        tf.write_text(
            make_assistant_record("sess-force", [make_skill_tool_use("new")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            backfill.backfill(force=True)

        lines = workflows_file.read_text(encoding="utf-8").strip().splitlines()
        records = [json.loads(l) for l in lines]
        sources = [r.get("source") for r in records]
        assert "trace" in sources
        # backfill の old は削除されている
        wf_ids = [r.get("workflow_id") for r in records]
        assert "wf-old" not in wf_ids

    def test_empty_project(self, patch_data_dir, transcript_dir):
        """トランスクリプトが空のプロジェクト。"""
        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["sessions_processed"] == 0
        assert summary["skill_calls"] == 0
        assert summary["agent_calls"] == 0


class TestResolveProjectDir:
    """resolve_project_dir() のテスト。"""

    def test_exact_match(self, tmp_path):
        """完全一致でディレクトリが見つかる。"""
        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()
        encoded_dir = projects_dir / "-Users-foo-bar"
        encoded_dir.mkdir()

        with mock.patch.object(backfill, "CLAUDE_PROJECTS_DIR", projects_dir):
            result = backfill.resolve_project_dir("/Users/foo/bar")
        assert result == encoded_dir

    def test_partial_match(self, tmp_path):
        """部分一致で検索される。"""
        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()
        encoded_dir = projects_dir / "-Users-foo-bar"
        encoded_dir.mkdir()

        with mock.patch.object(backfill, "CLAUDE_PROJECTS_DIR", projects_dir):
            result = backfill.resolve_project_dir("/Users/foo/bar")
        assert result == encoded_dir

    def test_not_found_raises(self, tmp_path):
        """見つからない場合は FileNotFoundError。"""
        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()

        with mock.patch.object(backfill, "CLAUDE_PROJECTS_DIR", projects_dir):
            with pytest.raises(FileNotFoundError):
                backfill.resolve_project_dir("/nonexistent/path")
