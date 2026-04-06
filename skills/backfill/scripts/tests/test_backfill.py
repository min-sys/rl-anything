"""backfill スクリプトのテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# backfill.py をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# scripts/lib/ を追加（rl_common 用）
_lib = Path(__file__).resolve().parent.parent.parent.parent.parent / "scripts" / "lib"
sys.path.insert(0, str(_lib))

import rl_common as common
import backfill


@pytest.fixture
def tmp_data_dir(tmp_path):
    """テスト用の一時データディレクトリ。"""
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def patch_data_dir(tmp_data_dir):
    """rl_common.DATA_DIR と backfill.common.DATA_DIR を一時ディレクトリに差し替える。

    backfill.py が import rl_common as common しているため両方パッチが必要。
    """
    with mock.patch.object(common, "DATA_DIR", tmp_data_dir), \
         mock.patch.object(backfill.common, "DATA_DIR", tmp_data_dir):
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


def make_task_tool_use(subagent_type: str, prompt: str = "test") -> dict:
    """旧 Claude Code の Task ツール（Agent と同一スキーマ）。"""
    return {
        "type": "tool_use",
        "name": "Task",
        "input": {"subagent_type": subagent_type, "prompt": prompt},
    }


def make_system_record(
    session_id: str,
    subtype: str,
    timestamp: str = "2025-06-15T10:00:00Z",
) -> str:
    """system レコードの JSONL 行を生成する。"""
    record = {
        "type": "system",
        "subtype": subtype,
        "timestamp": timestamp,
        "sessionId": session_id,
    }
    return json.dumps(record, ensure_ascii=False)


def make_thinking_block(text: str = "thinking...") -> dict:
    """thinking ブロックを生成する。"""
    return {"type": "thinking", "thinking": text}


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
        """Agent の prompt が 500 文字に切り詰められる。"""
        long_prompt = "あ" * 600
        tf = transcript_dir / "sess-003.jsonl"
        lines = [
            make_assistant_record("sess-003", [make_agent_tool_use("Explore", long_prompt)])
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records[0]["prompt"]) == 500

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
        assert wf["workflow_type"] == "skill-driven"
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

        assert wf1["workflow_type"] == "skill-driven"
        assert wf2["workflow_type"] == "skill-driven"

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
        assert result.workflow_records[0]["workflow_type"] == "skill-driven"

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
            "workflow_id", "workflow_type", "skill_name", "session_id",
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
        """--force で対象プロジェクトの既存バックフィルを削除して再処理する。"""
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

    def test_force_only_deletes_target_project(self, patch_data_dir, transcript_dir):
        """--force は対象プロジェクトのデータだけ削除し、他プロジェクトは保持する。"""
        usage_file = patch_data_dir / "usage.jsonl"
        # 対象プロジェクトのデータ（session_id = sess-target）
        target_rec = {"skill_name": "target", "session_id": "sess-target", "source": "backfill"}
        # 他プロジェクトのデータ（session_id = sess-other）
        other_rec = {"skill_name": "other", "session_id": "sess-other", "source": "backfill"}
        usage_file.write_text(
            json.dumps(target_rec) + "\n" + json.dumps(other_rec) + "\n",
            encoding="utf-8",
        )

        sessions_file = patch_data_dir / "sessions.jsonl"
        target_sess = {"session_id": "sess-target", "source": "backfill", "project_name": "target-pj"}
        other_sess = {"session_id": "sess-other", "source": "backfill", "project_name": "other-pj"}
        sessions_file.write_text(
            json.dumps(target_sess) + "\n" + json.dumps(other_sess) + "\n",
            encoding="utf-8",
        )

        # transcript_dir に sess-target.jsonl だけ置く（= 対象プロジェクト）
        tf = transcript_dir / "sess-target.jsonl"
        tf.write_text(
            make_assistant_record("sess-target", [make_skill_tool_use("new-skill")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            backfill.backfill(force=True)

        # usage: other-pj のレコードは残っている
        usage_lines = usage_file.read_text(encoding="utf-8").strip().splitlines()
        usage_records = [json.loads(l) for l in usage_lines]
        usage_sids = [r["session_id"] for r in usage_records]
        assert "sess-other" in usage_sids  # 他プロジェクトは保持

        # sessions: other-pj のレコードは残っている
        sess_lines = sessions_file.read_text(encoding="utf-8").strip().splitlines()
        sess_records = [json.loads(l) for l in sess_lines]
        sess_projects = [r.get("project_name") for r in sess_records]
        assert "other-pj" in sess_projects  # 他プロジェクトは保持


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
        assert summary["workflows_by_type"]["skill-driven"] == 1
        assert summary["workflows_by_type"]["team-driven"] == 0
        assert summary["workflows_by_type"]["agent-burst"] == 0

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
        assert wf["workflow_type"] == "skill-driven"

    def test_force_removes_backfill_workflows(self, patch_data_dir, transcript_dir):
        """--force で対象プロジェクトの backfill ワークフローが削除される（trace は保持）。"""
        workflows_file = patch_data_dir / "workflows.jsonl"
        # sess-force は対象プロジェクト、sess-other は別プロジェクト
        backfill_wf = {"workflow_id": "wf-old", "source": "backfill", "skill_name": "old", "session_id": "sess-force"}
        other_wf = {"workflow_id": "wf-other", "source": "backfill", "skill_name": "other", "session_id": "sess-other"}
        trace_wf = {"workflow_id": "wf-trace", "source": "trace", "skill_name": "trace", "session_id": "sess-force"}
        workflows_file.write_text(
            json.dumps(backfill_wf) + "\n" + json.dumps(other_wf) + "\n" + json.dumps(trace_wf) + "\n",
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
        assert "trace" in sources  # trace は保持
        wf_ids = [r.get("workflow_id") for r in records]
        assert "wf-old" not in wf_ids  # 対象プロジェクトの backfill は削除
        assert "wf-other" in wf_ids  # 他プロジェクトの backfill は保持

    def test_empty_project(self, patch_data_dir, transcript_dir):
        """トランスクリプトが空のプロジェクト。"""
        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["sessions_processed"] == 0
        assert summary["skill_calls"] == 0
        assert summary["agent_calls"] == 0


def make_human_record(
    session_id: str,
    text: str,
    timestamp: str = "2025-06-15T10:30:00Z",
) -> str:
    """human レコードの JSONL 行を生成する。"""
    record = {
        "type": "human",
        "message": {"content": [{"type": "text", "text": text}]},
        "timestamp": timestamp,
        "sessionId": session_id,
    }
    return json.dumps(record, ensure_ascii=False)


def make_tool_result_record(
    session_id: str,
    is_error: bool = False,
    timestamp: str = "2025-06-15T10:30:00Z",
) -> str:
    """tool_result レコードの JSONL 行を生成する。"""
    record = {
        "type": "tool_result",
        "tool_use_id": "toolu-test",
        "is_error": is_error,
        "content": "result text",
        "timestamp": timestamp,
        "sessionId": session_id,
    }
    return json.dumps(record, ensure_ascii=False)


def make_team_create_tool_use(team_name: str = "test-team") -> dict:
    return {
        "type": "tool_use",
        "name": "TeamCreate",
        "input": {"team_name": team_name},
    }


def make_team_delete_tool_use() -> dict:
    return {
        "type": "tool_use",
        "name": "TeamDelete",
        "input": {},
    }


def make_other_tool_use(tool_name: str, tool_input: dict = None) -> dict:
    """Skill/Agent 以外の tool_use ブロックを生成する。"""
    return {
        "type": "tool_use",
        "name": tool_name,
        "input": tool_input or {},
    }


class TestSessionMeta:
    """session_meta 収集のテスト。"""

    def test_tool_sequence_collected(self, transcript_dir):
        """全 tool_use の名前が順序付きで収集される。"""
        tf = transcript_dir / "sess-meta-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-meta-001",
                [
                    make_other_tool_use("Read", {"file_path": "/tmp/foo"}),
                    make_other_tool_use("Grep", {"pattern": "test"}),
                ],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-meta-001",
                [
                    make_other_tool_use("Edit", {"file_path": "/tmp/foo"}),
                    make_skill_tool_use("my-skill"),
                ],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["tool_sequence"] == ["Read", "Grep", "Edit", "Skill"]
        assert result.session_meta["total_tool_calls"] == 4
        assert result.session_meta["tool_counts"]["Read"] == 1
        assert result.session_meta["tool_counts"]["Grep"] == 1
        assert result.session_meta["tool_counts"]["Edit"] == 1
        assert result.session_meta["tool_counts"]["Skill"] == 1

    def test_session_duration_calculated(self, transcript_dir):
        """セッション開始〜終了の秒数が計算される。"""
        tf = transcript_dir / "sess-meta-002.jsonl"
        lines = [
            make_human_record("sess-meta-002", "hello", "2025-06-15T10:00:00Z"),
            make_assistant_record(
                "sess-meta-002",
                [make_other_tool_use("Read")],
                "2025-06-15T10:05:00Z",
            ),
            make_assistant_record(
                "sess-meta-002",
                [make_other_tool_use("Edit")],
                "2025-06-15T10:10:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["session_duration_seconds"] == 600.0  # 10 minutes

    def test_error_count_from_tool_result(self, transcript_dir):
        """tool_result の is_error=true がカウントされる。"""
        tf = transcript_dir / "sess-meta-003.jsonl"
        lines = [
            make_assistant_record(
                "sess-meta-003",
                [make_other_tool_use("Bash", {"command": "ls"})],
                "2025-06-15T10:00:00Z",
            ),
            make_tool_result_record("sess-meta-003", is_error=True, timestamp="2025-06-15T10:00:01Z"),
            make_assistant_record(
                "sess-meta-003",
                [make_other_tool_use("Bash", {"command": "pwd"})],
                "2025-06-15T10:00:02Z",
            ),
            make_tool_result_record("sess-meta-003", is_error=False, timestamp="2025-06-15T10:00:03Z"),
            make_tool_result_record("sess-meta-003", is_error=True, timestamp="2025-06-15T10:00:04Z"),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["error_count"] == 2

    def test_human_message_count_and_intents(self, transcript_dir):
        """human メッセージのカウントと intent 分類。"""
        tf = transcript_dir / "sess-meta-004.jsonl"
        lines = [
            make_human_record("sess-meta-004", "explore the codebase structure", "2025-06-15T10:00:00Z"),
            make_assistant_record(
                "sess-meta-004",
                [make_other_tool_use("Read")],
                "2025-06-15T10:00:30Z",
            ),
            make_human_record("sess-meta-004", "implement the feature", "2025-06-15T10:01:00Z"),
            make_assistant_record(
                "sess-meta-004",
                [make_other_tool_use("Write")],
                "2025-06-15T10:01:30Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["human_message_count"] == 2
        assert len(result.session_meta["user_intents"]) == 2
        assert result.session_meta["user_intents"][0] == "code-exploration"
        assert result.session_meta["user_intents"][1] == "implementation"

    def test_no_meta_for_empty_transcript(self, transcript_dir):
        """ツール呼び出しも human メッセージもない場合、session_meta は None。"""
        tf = transcript_dir / "sess-meta-005.jsonl"
        # type=assistant だが tool_use なし
        record = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hello"}]},
            "timestamp": "2025-06-15T10:00:00Z",
            "sessionId": "sess-meta-005",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is None

    def test_skill_and_agent_in_tool_sequence(self, transcript_dir):
        """Skill と Agent も tool_sequence に含まれる。"""
        tf = transcript_dir / "sess-meta-006.jsonl"
        lines = [
            make_assistant_record(
                "sess-meta-006",
                [
                    make_other_tool_use("Read"),
                    make_skill_tool_use("my-skill"),
                ],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-meta-006",
                [make_agent_tool_use("Explore", "explore")],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["tool_sequence"] == ["Read", "Skill", "Agent"]
        assert result.session_meta["source"] == "backfill"

    def test_human_content_as_string(self, transcript_dir):
        """human メッセージの content が文字列の場合も intent 分類される。"""
        tf = transcript_dir / "sess-meta-007.jsonl"
        record = {
            "type": "human",
            "message": {"content": "research the best practices for caching"},
            "timestamp": "2025-06-15T10:00:00Z",
            "sessionId": "sess-meta-007",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["human_message_count"] == 1
        assert result.session_meta["user_intents"] == ["research"]

    def test_user_type_record(self, transcript_dir):
        """type: 'user' レコード（Claude Code の実際の形式）も intent 分類される。"""
        tf = transcript_dir / "sess-meta-008.jsonl"
        record = {
            "type": "user",
            "message": {"role": "user", "content": "implement the new feature"},
            "timestamp": "2025-06-15T10:00:00Z",
            "sessionId": "sess-meta-008",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["human_message_count"] == 1
        assert result.session_meta["user_intents"] == ["implementation"]

    def test_user_prompts_collected(self, transcript_dir):
        """user_prompts がプロンプト原文を収集する。"""
        tf = transcript_dir / "sess-meta-009.jsonl"
        lines = [
            make_human_record("sess-meta-009", "explore the codebase structure", "2025-06-15T10:00:00Z"),
            make_assistant_record(
                "sess-meta-009",
                [make_other_tool_use("Read")],
                "2025-06-15T10:00:30Z",
            ),
            make_human_record("sess-meta-009", "implement the feature", "2025-06-15T10:01:00Z"),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["user_prompts"] == [
            "explore the codebase structure",
            "implement the feature",
        ]
        assert len(result.session_meta["user_prompts"]) == len(result.session_meta["user_intents"])

    def test_user_prompts_truncated(self, transcript_dir):
        """user_prompts が MAX_PROMPT_LENGTH で切り詰められる。"""
        long_text = "x" * 600
        tf = transcript_dir / "sess-meta-010.jsonl"
        record = {
            "type": "human",
            "message": {"content": long_text},
            "timestamp": "2025-06-15T10:00:00Z",
            "sessionId": "sess-meta-010",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert len(result.session_meta["user_prompts"][0]) == 500

    def test_user_prompts_from_content_list(self, transcript_dir):
        """content がリスト形式の場合も user_prompts に記録される。"""
        tf = transcript_dir / "sess-meta-011.jsonl"
        lines = [
            make_human_record("sess-meta-011", "debug the login error", "2025-06-15T10:00:00Z"),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["user_prompts"] == ["debug the login error"]


class TestSessionsIntegration:
    """sessions.jsonl 統合テスト。"""

    def test_sessions_written_to_jsonl(self, patch_data_dir, transcript_dir):
        """backfill() が sessions.jsonl にセッションメタデータを書き出す。"""
        tf = transcript_dir / "sess-int-001.jsonl"
        lines = [
            make_human_record("sess-int-001", "explore structure", "2025-06-15T10:00:00Z"),
            make_assistant_record(
                "sess-int-001",
                [make_other_tool_use("Read"), make_other_tool_use("Grep")],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(project_dir="/tmp/my-project", force=False)

        assert summary["sessions"] == 1

        sessions_file = patch_data_dir / "sessions.jsonl"
        assert sessions_file.exists()
        meta = json.loads(sessions_file.read_text(encoding="utf-8").strip())
        assert meta["session_id"] == "sess-int-001"
        assert meta["tool_sequence"] == ["Read", "Grep"]
        assert meta["human_message_count"] == 1
        assert meta["project_name"] == "my-project"
        assert meta["source"] == "backfill"

    def test_force_removes_backfill_sessions(self, patch_data_dir, transcript_dir):
        """--force で対象プロジェクトの backfill sessions のみ削除（hook・他プロジェクトは保持）。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        # sess-force は対象プロジェクト、other-sess は別プロジェクト
        target_sess = {"session_id": "sess-force", "source": "backfill", "total_tool_calls": 5}
        other_sess = {"session_id": "other-sess", "source": "backfill", "total_tool_calls": 8}
        hook_sess = {"session_id": "hook-sess", "source": "hook", "total_tool_calls": 3}
        sessions_file.write_text(
            json.dumps(target_sess) + "\n" + json.dumps(other_sess) + "\n" + json.dumps(hook_sess) + "\n",
            encoding="utf-8",
        )

        tf = transcript_dir / "sess-force.jsonl"
        tf.write_text(
            make_assistant_record("sess-force", [make_other_tool_use("Read")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            backfill.backfill(force=True)

        lines = sessions_file.read_text(encoding="utf-8").strip().splitlines()
        records = [json.loads(l) for l in lines]
        session_ids = [r.get("session_id") for r in records]
        assert "hook-sess" in session_ids  # hook は保持
        assert "other-sess" in session_ids  # 他プロジェクトは保持

    def test_summary_includes_sessions_count(self, patch_data_dir, transcript_dir):
        """サマリに sessions カウントが含まれる。"""
        tf = transcript_dir / "sess-cnt.jsonl"
        tf.write_text(
            make_assistant_record("sess-cnt", [make_other_tool_use("Bash")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert "sessions" in summary
        assert summary["sessions"] == 1


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


class TestClassifySystemMessage:
    """_classify_system_message() のユニットテスト。"""

    def test_interrupt_signal_excluded(self):
        """中断シグナルは除外される。"""
        assert backfill._classify_system_message("[Request interrupted by user]") is None

    def test_interrupt_signal_variant_excluded(self):
        """中断シグナルのバリエーションも除外される（prefix マッチ）。"""
        assert backfill._classify_system_message("[Request interrupted by user for tool use]") is None

    def test_local_command_stdout_excluded(self):
        """local-command-stdout は除外される。"""
        assert backfill._classify_system_message("<local-command-stdout>some output</local-command-stdout>") is None

    def test_local_command_caveat_excluded(self):
        """local-command-caveat は除外される。"""
        assert backfill._classify_system_message("<local-command-caveat>Caveat: ...</local-command-caveat>") is None

    def test_task_notification_excluded(self):
        """task-notification は除外される。"""
        assert backfill._classify_system_message("<task-notification>Agent completed</task-notification>") is None

    def test_command_name_slash_command(self):
        """スラッシュコマンドが抽出される。"""
        result = backfill._classify_system_message("<command-name>/commit</command-name> some args")
        assert result == ("skill-invocation", "/commit")

    def test_command_name_plugin_command(self):
        """プラグインコマンドが抽出される。"""
        result = backfill._classify_system_message("<command-name>/rl-anything:backfill</command-name>")
        assert result == ("skill-invocation", "/rl-anything:backfill")

    def test_command_name_parse_failure(self):
        """command-name タグのパース失敗は除外される。"""
        assert backfill._classify_system_message("<command-name></command-name>") is None

    def test_normal_prompt_passthrough(self):
        """通常プロンプトは passthrough される。"""
        result = backfill._classify_system_message("Fix the login bug")
        assert result == ("passthrough", "Fix the login bug")

    def test_bracket_non_interrupt_passthrough(self):
        """角括弧で始まるが中断シグナルではないプロンプトは passthrough される。"""
        result = backfill._classify_system_message("[重要] この関数を修正して")
        assert result == ("passthrough", "[重要] この関数を修正して")


class TestFilterIntegration:
    """parse_transcript() のフィルタ統合テスト。"""

    def test_interrupt_signal_filtered(self, transcript_dir):
        """中断シグナルがフィルタされ user_prompts/user_intents に含まれない。"""
        tf = transcript_dir / "sess-filter-001.jsonl"
        record = {
            "type": "human",
            "message": {"content": "[Request interrupted by user]"},
            "timestamp": "2025-06-15T10:00:00Z",
            "sessionId": "sess-filter-001",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["user_prompts"] == []
        assert result.session_meta["user_intents"] == []
        assert result.session_meta["filtered_messages"] == 1

    def test_command_name_extracted(self, transcript_dir):
        """command-name タグからスキル名が抽出される。"""
        tf = transcript_dir / "sess-filter-002.jsonl"
        record = {
            "type": "human",
            "message": {"content": "<command-name>/commit</command-name> fix typo"},
            "timestamp": "2025-06-15T10:00:00Z",
            "sessionId": "sess-filter-002",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["user_intents"] == ["skill-invocation"]
        assert result.session_meta["user_prompts"] == ["/commit"]
        assert result.session_meta["filtered_messages"] == 0

    def test_filtered_messages_count(self, transcript_dir):
        """複数のフィルタ対象がカウントされる。"""
        tf = transcript_dir / "sess-filter-003.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "[Request interrupted by user]"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-filter-003",
            }),
            json.dumps({
                "type": "human",
                "message": {"content": "<local-command-stdout>output</local-command-stdout>"},
                "timestamp": "2025-06-15T10:00:01Z",
                "sessionId": "sess-filter-003",
            }),
            json.dumps({
                "type": "human",
                "message": {"content": "Fix the bug"},
                "timestamp": "2025-06-15T10:00:02Z",
                "sessionId": "sess-filter-003",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["filtered_messages"] == 2
        assert result.session_meta["user_prompts"] == ["Fix the bug"]
        assert result.session_meta["user_intents"] == ["debug"]

    def test_content_list_format_filtered(self, transcript_dir):
        """content がリスト形式の場合もフィルタが適用される。"""
        tf = transcript_dir / "sess-filter-004.jsonl"
        record = {
            "type": "human",
            "message": {
                "content": [
                    {"type": "text", "text": "[Request interrupted by user]"}
                ]
            },
            "timestamp": "2025-06-15T10:00:00Z",
            "sessionId": "sess-filter-004",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["user_prompts"] == []
        assert result.session_meta["user_intents"] == []
        assert result.session_meta["filtered_messages"] == 1

    def test_content_list_command_name_extracted(self, transcript_dir):
        """content リスト形式でもコマンドタグが抽出される。"""
        tf = transcript_dir / "sess-filter-005.jsonl"
        record = {
            "type": "human",
            "message": {
                "content": [
                    {"type": "text", "text": "<command-name>/rl-anything:backfill</command-name> run it"}
                ]
            },
            "timestamp": "2025-06-15T10:00:00Z",
            "sessionId": "sess-filter-005",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["user_intents"] == ["skill-invocation"]
        assert result.session_meta["user_prompts"] == ["/rl-anything:backfill"]

    def test_mixed_patterns_in_session(self, transcript_dir):
        """同一セッション内に command-name + 通常テキスト + 中断シグナルが混在。"""
        tf = transcript_dir / "sess-filter-006.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/commit</command-name> initial"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-filter-006",
            }),
            json.dumps({
                "type": "human",
                "message": {"content": "implement the feature"},
                "timestamp": "2025-06-15T10:01:00Z",
                "sessionId": "sess-filter-006",
            }),
            json.dumps({
                "type": "human",
                "message": {"content": "[Request interrupted by user]"},
                "timestamp": "2025-06-15T10:02:00Z",
                "sessionId": "sess-filter-006",
            }),
            json.dumps({
                "type": "human",
                "message": {"content": "<task-notification>done</task-notification>"},
                "timestamp": "2025-06-15T10:03:00Z",
                "sessionId": "sess-filter-006",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta is not None
        assert result.session_meta["user_intents"] == ["skill-invocation", "implementation"]
        assert result.session_meta["user_prompts"] == ["/commit", "implement the feature"]
        assert result.session_meta["filtered_messages"] == 2
        assert result.session_meta["human_message_count"] == 4


class TestTeamDrivenWorkflow:
    """team-driven ワークフロー検出のテスト（タスク 4.1）。"""

    def test_team_create_agent_team_delete(self, transcript_dir):
        """TeamCreate→Agent→Agent→TeamDelete がワークフローを生成する。"""
        tf = transcript_dir / "sess-team-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-team-001",
                [make_team_create_tool_use("impl-team")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-team-001",
                [make_agent_tool_use("Explore", "explore the codebase")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-team-001",
                [make_agent_tool_use("general-purpose", "implement feature")],
                "2025-06-15T10:02:00Z",
            ),
            make_assistant_record(
                "sess-team-001",
                [make_team_delete_tool_use()],
                "2025-06-15T10:03:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "team-driven"
        assert wf["team_name"] == "impl-team"
        assert wf["skill_name"] is None
        assert wf["step_count"] == 2
        assert wf["steps"][0]["tool"] == "Agent:Explore"
        assert wf["steps"][1]["tool"] == "Agent:general-purpose"
        assert wf["source"] == "backfill"

        # Agent の usage レコードに workflow_id が付与される
        agents = [r for r in result.usage_records if r["skill_name"].startswith("Agent:")]
        assert len(agents) == 2
        assert agents[0]["workflow_id"] == wf["workflow_id"]
        assert agents[0]["parent_skill"] is None

    def test_team_no_team_delete(self, transcript_dir):
        """TeamDelete なしでトランスクリプト終了 → ワークフロー確定。"""
        tf = transcript_dir / "sess-team-002.jsonl"
        lines = [
            make_assistant_record(
                "sess-team-002",
                [make_team_create_tool_use("open-team")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-team-002",
                [make_agent_tool_use("Explore", "explore")],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "team-driven"
        assert wf["team_name"] == "open-team"
        assert wf["step_count"] == 1

    def test_team_no_agents(self, transcript_dir):
        """TeamCreate→TeamDelete の間に Agent がない → ワークフロー不生成。"""
        tf = transcript_dir / "sess-team-003.jsonl"
        lines = [
            make_assistant_record(
                "sess-team-003",
                [make_team_create_tool_use("empty-team")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-team-003",
                [make_team_delete_tool_use()],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.workflow_records) == 0


class TestAgentBurst:
    """agent-burst 検出のテスト（タスク 4.2）。"""

    def test_two_agents_burst(self, transcript_dir):
        """Skill/Team 外の 2 Agent が 5 分以内 → agent-burst ワークフロー。"""
        tf = transcript_dir / "sess-burst-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-burst-001",
                [make_agent_tool_use("Explore", "explore")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-burst-001",
                [make_agent_tool_use("general-purpose", "implement")],
                "2025-06-15T10:03:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "agent-burst"
        assert wf["skill_name"] is None
        assert wf["team_name"] is None
        assert wf["step_count"] == 2

    def test_gap_splits_burst(self, transcript_dir):
        """5 分以上の gap → ワークフロー不生成（各 Agent は ad-hoc）。"""
        tf = transcript_dir / "sess-burst-002.jsonl"
        lines = [
            make_assistant_record(
                "sess-burst-002",
                [make_agent_tool_use("Explore", "explore")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-burst-002",
                [make_agent_tool_use("general-purpose", "implement")],
                "2025-06-15T10:06:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.workflow_records) == 0

    def test_single_ad_hoc(self, transcript_dir):
        """Skill/Team 外で Agent 1 回 → ワークフロー不生成。"""
        tf = transcript_dir / "sess-burst-003.jsonl"
        lines = [
            make_assistant_record(
                "sess-burst-003",
                [make_agent_tool_use("Explore", "explore")],
                "2025-06-15T10:00:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.workflow_records) == 0

    def test_three_agents_mid_gap(self, transcript_dir):
        """3 Agent で途中に gap → 最初の 2 が burst、3 つ目は ad-hoc。"""
        tf = transcript_dir / "sess-burst-004.jsonl"
        lines = [
            make_assistant_record(
                "sess-burst-004",
                [make_agent_tool_use("Explore", "first")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-burst-004",
                [make_agent_tool_use("general-purpose", "second")],
                "2025-06-15T10:02:00Z",
            ),
            make_assistant_record(
                "sess-burst-004",
                [make_agent_tool_use("Explore", "third")],
                "2025-06-15T10:09:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "agent-burst"
        assert wf["step_count"] == 2
        assert wf["steps"][0]["tool"] == "Agent:Explore"
        assert wf["steps"][1]["tool"] == "Agent:general-purpose"

    def test_exactly_300_seconds_boundary(self, transcript_dir):
        """ちょうど 300 秒（5 分）の間隔 → 同一ワークフロー（閾値以内）。"""
        tf = transcript_dir / "sess-burst-005.jsonl"
        lines = [
            make_assistant_record(
                "sess-burst-005",
                [make_agent_tool_use("Explore", "first")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-burst-005",
                [make_agent_tool_use("general-purpose", "second")],
                "2025-06-15T10:05:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "agent-burst"
        assert wf["step_count"] == 2


class TestMixedPatterns:
    """混在パターンのテスト（タスク 4.3）。"""

    def test_skill_in_team(self, transcript_dir):
        """Team 内 Skill→Agent → team-driven のステップとして記録（skill-driven 不生成）。"""
        tf = transcript_dir / "sess-mix-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-mix-001",
                [make_team_create_tool_use("mix-team")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-mix-001",
                [make_skill_tool_use("opsx:refine")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-mix-001",
                [make_agent_tool_use("Explore", "explore for refine")],
                "2025-06-15T10:02:00Z",
            ),
            make_assistant_record(
                "sess-mix-001",
                [make_team_delete_tool_use()],
                "2025-06-15T10:03:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        # ワークフローは team-driven のみ（skill-driven は生成されない）
        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "team-driven"
        assert wf["team_name"] == "mix-team"
        assert wf["step_count"] == 1
        assert wf["steps"][0]["tool"] == "Agent:Explore"

    def test_team_then_agent_burst(self, transcript_dir):
        """Team ワークフロー後に agent-burst が続く。"""
        tf = transcript_dir / "sess-mix-002.jsonl"
        lines = [
            make_assistant_record(
                "sess-mix-002",
                [make_team_create_tool_use("first-team")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-mix-002",
                [make_agent_tool_use("Explore", "team explore")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-mix-002",
                [make_team_delete_tool_use()],
                "2025-06-15T10:02:00Z",
            ),
            # Team 後の ad-hoc Agent 連続 → agent-burst
            make_assistant_record(
                "sess-mix-002",
                [make_agent_tool_use("Explore", "burst explore")],
                "2025-06-15T10:03:00Z",
            ),
            make_assistant_record(
                "sess-mix-002",
                [make_agent_tool_use("general-purpose", "burst implement")],
                "2025-06-15T10:04:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        assert len(result.workflow_records) == 2
        wf_team = result.workflow_records[0]
        wf_burst = result.workflow_records[1]
        assert wf_team["workflow_type"] == "team-driven"
        assert wf_team["step_count"] == 1
        assert wf_burst["workflow_type"] == "agent-burst"
        assert wf_burst["step_count"] == 2


class TestCommandNameWorkflowAnchor:
    """command-name タグからのワークフローアンカーテスト。"""

    def test_command_name_anchors_workflow(self, transcript_dir):
        """<command-name> → Agent がワークフローを生成する。"""
        tf = transcript_dir / "sess-cmd-001.jsonl"
        lines = [
            # ユーザーが /opsx:apply を実行
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/opsx:apply</command-name> backfill"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-cmd-001",
            }),
            # Claude が Agent を起動（Skill tool_use なし）
            make_assistant_record(
                "sess-cmd-001",
                [make_agent_tool_use("Explore", "explore codebase")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-cmd-001",
                [make_agent_tool_use("general-purpose", "implement changes")],
                "2025-06-15T10:02:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "skill-driven"
        assert wf["skill_name"] == "opsx:apply"
        assert wf["step_count"] == 2

    def test_command_name_then_skill_tool_use_dedup(self, transcript_dir):
        """command-name + 同じスキルの Skill tool_use → 重複しない。"""
        tf = transcript_dir / "sess-cmd-002.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/commit</command-name> fix typo"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-cmd-002",
            }),
            # Claude が同じスキルの Skill tool_use も呼ぶ
            make_assistant_record(
                "sess-cmd-002",
                [make_skill_tool_use("commit", "fix typo")],
                "2025-06-15T10:00:01Z",
            ),
            make_assistant_record(
                "sess-cmd-002",
                [make_agent_tool_use("general-purpose", "create commit")],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        # ワークフローは1つだけ
        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["skill_name"] == "commit"
        assert wf["step_count"] == 1

        # usage: command-name の1件のみ（Skill tool_use はスキップ）
        skill_usage = [r for r in result.usage_records if not r["skill_name"].startswith("Agent:")]
        assert len(skill_usage) == 1

    def test_command_name_without_agent_no_workflow(self, transcript_dir):
        """command-name の後に Agent がない → ワークフロー不生成。"""
        tf = transcript_dir / "sess-cmd-003.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/clear</command-name>"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-cmd-003",
            }),
            make_assistant_record(
                "sess-cmd-003",
                [make_other_tool_use("Read", {"file_path": "/tmp/foo"})],
                "2025-06-15T10:00:30Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.workflow_records) == 0

    def test_multiple_command_names_separate_workflows(self, transcript_dir):
        """複数の command-name が別々のワークフローを生成する。"""
        tf = transcript_dir / "sess-cmd-004.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/opsx:ff</command-name> design"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-cmd-004",
            }),
            make_assistant_record(
                "sess-cmd-004",
                [make_agent_tool_use("Explore", "explore")],
                "2025-06-15T10:01:00Z",
            ),
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/opsx:apply</command-name> task1"},
                "timestamp": "2025-06-15T10:05:00Z",
                "sessionId": "sess-cmd-004",
            }),
            make_assistant_record(
                "sess-cmd-004",
                [make_agent_tool_use("general-purpose", "implement")],
                "2025-06-15T10:06:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)

        assert len(result.workflow_records) == 2
        assert result.workflow_records[0]["skill_name"] == "opsx:ff"
        assert result.workflow_records[0]["step_count"] == 1
        assert result.workflow_records[1]["skill_name"] == "opsx:apply"
        assert result.workflow_records[1]["step_count"] == 1


class TestTaskToolAlias:
    """旧 Task ツール（= Agent）のエイリアス対応テスト。"""

    def test_task_tool_treated_as_agent(self, transcript_dir):
        """Task ツールが Agent と同等に処理される。"""
        tf = transcript_dir / "sess-task-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-task-001",
                [make_task_tool_use("Explore", "explore codebase")],
                "2025-06-15T10:00:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 1
        assert result.usage_records[0]["skill_name"] == "Agent:Explore"
        assert result.usage_records[0]["subagent_type"] == "Explore"
        assert result.usage_records[0]["source"] == "backfill"

    def test_task_tool_in_skill_workflow(self, transcript_dir):
        """Skill → Task がワークフローステップとして記録される。"""
        tf = transcript_dir / "sess-task-002.jsonl"
        lines = [
            make_assistant_record(
                "sess-task-002",
                [make_skill_tool_use("opsx:apply")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-task-002",
                [make_task_tool_use("general-purpose", "implement changes")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-task-002",
                [make_task_tool_use("Explore", "verify output")],
                "2025-06-15T10:02:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "skill-driven"
        assert wf["skill_name"] == "opsx:apply"
        assert wf["step_count"] == 2

        # Task も parent_skill/workflow_id を持つ
        assert result.usage_records[1]["parent_skill"] == "opsx:apply"
        assert result.usage_records[2]["parent_skill"] == "opsx:apply"

    def test_task_tool_in_team_workflow(self, transcript_dir):
        """TeamCreate → Task がチームワークフローステップとして記録される。"""
        tf = transcript_dir / "sess-task-003.jsonl"
        lines = [
            make_assistant_record(
                "sess-task-003",
                [make_team_create_tool_use("my-team")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-task-003",
                [make_task_tool_use("general-purpose", "do work")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-task-003",
                [make_team_delete_tool_use()],
                "2025-06-15T10:05:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "team-driven"
        assert wf["team_name"] == "my-team"
        assert wf["step_count"] == 1

    def test_task_tool_agent_burst(self, transcript_dir):
        """連続する Task ツールが agent-burst ワークフローを生成する。"""
        tf = transcript_dir / "sess-task-004.jsonl"
        lines = [
            make_assistant_record(
                "sess-task-004",
                [make_task_tool_use("Explore", "explore 1")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-task-004",
                [make_task_tool_use("general-purpose", "work 1")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-task-004",
                [make_task_tool_use("Explore", "explore 2")],
                "2025-06-15T10:02:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["workflow_type"] == "agent-burst"
        assert wf["step_count"] == 3

    def test_mixed_task_and_agent(self, transcript_dir):
        """Task と Agent が混在してもワークフローに正しく含まれる。"""
        tf = transcript_dir / "sess-task-005.jsonl"
        lines = [
            make_assistant_record(
                "sess-task-005",
                [make_skill_tool_use("opsx:refine")],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-task-005",
                [make_task_tool_use("Explore", "old agent call")],
                "2025-06-15T10:01:00Z",
            ),
            make_assistant_record(
                "sess-task-005",
                [make_agent_tool_use("general-purpose", "new agent call")],
                "2025-06-15T10:02:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.workflow_records) == 1
        wf = result.workflow_records[0]
        assert wf["step_count"] == 2
        assert wf["steps"][0]["tool"] == "Agent:Explore"
        assert wf["steps"][1]["tool"] == "Agent:general-purpose"


class TestBuiltinCommandFilter:
    """ビルトイン CLI コマンドのフィルタリングテスト。"""

    def test_clear_command_filtered(self, transcript_dir):
        """/clear はスキル起動として扱わない。"""
        tf = transcript_dir / "sess-builtin-001.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/clear</command-name>"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-builtin-001",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 0
        assert len(result.workflow_records) == 0
        # intent に skill-invocation が含まれない
        assert "skill-invocation" not in (result.session_meta or {}).get("user_intents", [])

    def test_compact_command_filtered(self, transcript_dir):
        """/compact はスキル起動として扱わない。"""
        tf = transcript_dir / "sess-builtin-002.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/compact</command-name>"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-builtin-002",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 0

    def test_model_command_filtered(self, transcript_dir):
        """/model はスキル起動として扱わない。"""
        tf = transcript_dir / "sess-builtin-003.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/model</command-name> sonnet"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-builtin-003",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 0

    def test_skill_with_colon_not_filtered(self, transcript_dir):
        """コロン付きスキル（opsx:apply等）はフィルタされない。"""
        tf = transcript_dir / "sess-builtin-004.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/opsx:apply</command-name> task1"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-builtin-004",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert len(result.usage_records) == 1
        assert result.usage_records[0]["skill_name"] == "opsx:apply"

    def test_builtin_then_skill_no_interference(self, transcript_dir):
        """/clear の後に /opsx:apply → clear はフィルタされ apply だけ記録される。"""
        tf = transcript_dir / "sess-builtin-005.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/clear</command-name>"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-builtin-005",
            }),
            json.dumps({
                "type": "human",
                "message": {"content": "<command-name>/opsx:apply</command-name> task"},
                "timestamp": "2025-06-15T10:01:00Z",
                "sessionId": "sess-builtin-005",
            }),
            make_assistant_record(
                "sess-builtin-005",
                [make_agent_tool_use("general-purpose", "implement")],
                "2025-06-15T10:02:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        skill_usage = [r for r in result.usage_records if not r["skill_name"].startswith("Agent:")]
        assert len(skill_usage) == 1
        assert skill_usage[0]["skill_name"] == "opsx:apply"
        assert len(result.workflow_records) == 1
        assert result.workflow_records[0]["skill_name"] == "opsx:apply"

    def test_all_builtin_commands_filtered(self):
        """_BUILTIN_COMMANDS の全コマンドがフィルタされることを確認。"""
        for cmd in backfill._BUILTIN_COMMANDS:
            result = backfill._classify_system_message(f"<command-name>/{cmd}</command-name>")
            assert result is None, f"/{cmd} should be filtered but got {result}"


class TestSessionMetaEnrichment:
    """セッションメタデータ拡充のテスト。"""

    def test_thinking_count(self, transcript_dir):
        """thinking ブロックがカウントされる。"""
        tf = transcript_dir / "sess-meta-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-meta-001",
                [
                    make_thinking_block("first thought"),
                    make_other_tool_use("Read", {"file_path": "/tmp/a"}),
                    make_thinking_block("second thought"),
                ],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-meta-001",
                [make_thinking_block("third thought")],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta["thinking_count"] == 3

    def test_api_error_count(self, transcript_dir):
        """system api_error レコードがエラーとしてカウントされる。"""
        tf = transcript_dir / "sess-meta-002.jsonl"
        lines = [
            make_system_record("sess-meta-002", "api_error", "2025-06-15T10:00:00Z"),
            make_system_record("sess-meta-002", "api_error", "2025-06-15T10:01:00Z"),
            make_assistant_record(
                "sess-meta-002",
                [make_other_tool_use("Read", {"file_path": "/tmp/a"})],
                "2025-06-15T10:02:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta["error_count"] == 2

    def test_compact_count(self, transcript_dir):
        """compact_boundary レコードがカウントされる。"""
        tf = transcript_dir / "sess-meta-003.jsonl"
        lines = [
            make_system_record("sess-meta-003", "compact_boundary", "2025-06-15T10:00:00Z"),
            make_assistant_record(
                "sess-meta-003",
                [make_other_tool_use("Read", {"file_path": "/tmp/a"})],
                "2025-06-15T10:30:00Z",
            ),
            make_system_record("sess-meta-003", "compact_boundary", "2025-06-15T11:00:00Z"),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta["compact_count"] == 2

    def test_plan_mode_count(self, transcript_dir):
        """EnterPlanMode のツール呼び出し数が plan_mode_count に記録される。"""
        tf = transcript_dir / "sess-meta-004.jsonl"
        lines = [
            make_assistant_record(
                "sess-meta-004",
                [make_other_tool_use("EnterPlanMode", {})],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-meta-004",
                [make_other_tool_use("ExitPlanMode", {})],
                "2025-06-15T10:05:00Z",
            ),
            make_assistant_record(
                "sess-meta-004",
                [make_other_tool_use("EnterPlanMode", {})],
                "2025-06-15T10:10:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        assert result.session_meta["plan_mode_count"] == 2

    def test_session_meta_has_all_new_fields(self, transcript_dir):
        """セッションメタデータに新フィールドが全て存在する。"""
        tf = transcript_dir / "sess-meta-005.jsonl"
        lines = [
            make_assistant_record(
                "sess-meta-005",
                [make_other_tool_use("Read", {"file_path": "/tmp/a"})],
                "2025-06-15T10:00:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        result = backfill.parse_transcript(tf)
        meta = result.session_meta
        assert "thinking_count" in meta
        assert "compact_count" in meta
        assert "plan_mode_count" in meta
        assert meta["thinking_count"] == 0
        assert meta["compact_count"] == 0
        assert meta["plan_mode_count"] == 0


class TestExtractCorrections:
    """extract_corrections_from_transcript() のテスト。"""

    def test_detects_correction_with_last_skill(self, transcript_dir):
        """修正パターンと直前スキルが紐付けられる。拡張スキーマで出力される。"""
        tf = transcript_dir / "sess-corr-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-corr-001",
                [{"type": "tool_use", "name": "Skill", "input": {"skill": "evolve"}, "id": "tu-1"}],
                "2025-06-15T10:00:00Z",
            ),
            json.dumps({
                "type": "human",
                "message": {"content": "そうじゃなくて optimize を使って"},
                "timestamp": "2025-06-15T10:01:00Z",
                "sessionId": "sess-corr-001",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        corrections = backfill.extract_corrections_from_transcript(tf)
        assert len(corrections) == 1
        c = corrections[0]
        assert c["correction_type"] == "souja-nakute"
        assert c["last_skill"] == "evolve"
        assert c["source"] == "backfill"
        assert c["session_id"] == "sess-corr-001"
        # 拡張スキーマフィールド
        assert "matched_patterns" in c
        assert "souja-nakute" in c["matched_patterns"]
        assert "sentiment" in c
        assert "decay_days" in c
        assert "routing_hint" in c
        assert "guardrail" in c
        assert "reflect_status" in c and c["reflect_status"] == "pending"
        assert "extracted_learning" in c
        assert "project_path" in c

    def test_no_prior_skill(self, transcript_dir):
        """直前スキルがない場合は last_skill: null。"""
        tf = transcript_dir / "sess-corr-002.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "いや、違う"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-corr-002",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        corrections = backfill.extract_corrections_from_transcript(tf)
        assert len(corrections) == 1
        assert corrections[0]["last_skill"] is None

    def test_no_correction_patterns(self, transcript_dir):
        """修正パターンがない場合は空リスト。"""
        tf = transcript_dir / "sess-corr-003.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "ありがとう、完璧です"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-corr-003",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        corrections = backfill.extract_corrections_from_transcript(tf)
        assert len(corrections) == 0

    def test_question_excluded(self, transcript_dir):
        """疑問文は除外される。"""
        tf = transcript_dir / "sess-corr-004.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "いや、それでいいの？"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-corr-004",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        corrections = backfill.extract_corrections_from_transcript(tf)
        assert len(corrections) == 0

    def test_confidence_calculated_dynamically(self, transcript_dir):
        """confidence は calculate_confidence() で動的に計算される。"""
        tf = transcript_dir / "sess-corr-005.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "no, that's wrong"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-corr-005",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        corrections = backfill.extract_corrections_from_transcript(tf)
        # "no" と "thats-wrong" の2パターンマッチ → 動的信頼度
        assert corrections[0]["confidence"] > 0
        assert 0.0 <= corrections[0]["confidence"] <= 1.0
        assert "matched_patterns" in corrections[0]
        assert len(corrections[0]["matched_patterns"]) >= 2

    def test_tool_rejection_detected(self, transcript_dir):
        """ツール拒否パターンが correction として検出される。"""
        tf = transcript_dir / "sess-corr-006.jsonl"
        lines = [
            make_assistant_record(
                "sess-corr-006",
                [{"type": "tool_use", "name": "Skill", "input": {"skill": "evolve"}, "id": "tu-1"}],
                "2025-06-15T10:00:00Z",
            ),
            make_assistant_record(
                "sess-corr-006",
                [{"type": "text", "text": "The user doesn't want to proceed with this action. the user said: I don't want that"}],
                "2025-06-15T10:01:00Z",
            ),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        corrections = backfill.extract_corrections_from_transcript(tf)
        assert len(corrections) == 1
        c = corrections[0]
        assert c["correction_type"] == "tool-rejection"
        assert c["last_skill"] == "evolve"
        assert c["guardrail"] is True
        assert c["routing_hint"] == "guardrail"
        assert c["source"] == "backfill"

    def test_extended_schema_fields_present(self, transcript_dir):
        """拡張スキーマの全フィールドが correction レコードに存在する。"""
        tf = transcript_dir / "sess-corr-007.jsonl"
        lines = [
            json.dumps({
                "type": "human",
                "message": {"content": "いや、違う"},
                "timestamp": "2025-06-15T10:00:00Z",
                "sessionId": "sess-corr-007",
            }),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        corrections = backfill.extract_corrections_from_transcript(tf)
        assert len(corrections) == 1
        c = corrections[0]
        required_fields = [
            "correction_type", "matched_patterns", "message", "last_skill",
            "confidence", "decay_days", "sentiment", "routing_hint",
            "guardrail", "reflect_status", "extracted_learning",
            "project_path", "timestamp", "session_id", "source",
        ]
        for field in required_fields:
            assert field in c, f"Missing field: {field}"
