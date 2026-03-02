"""observe hooks のスモークテスト。"""
import importlib
import json
import os
import sys
import time
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# hooks/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common
import observe
import session_summary
import save_state
import restore_state
import subagent_observe
import workflow_context


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


class TestWorkflowContext:
    """workflow_context.py のテスト。"""

    def test_context_file_created(self, tmp_path):
        """Skill 呼び出し時に文脈ファイルが作成される。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "opsx:refine", "args": ""},
                "session_id": "sess-wf-001",
            }
            workflow_context.handle_pre_tool_use(event)

            ctx_path = tmp_path / "rl-anything-workflow-sess-wf-001.json"
            assert ctx_path.exists()
            ctx = json.loads(ctx_path.read_text())
            assert ctx["skill_name"] == "opsx:refine"
            assert ctx["session_id"] == "sess-wf-001"
            assert ctx["workflow_id"].startswith("wf-")
            assert len(ctx["workflow_id"]) == 11  # "wf-" + 8 hex chars
            assert "started_at" in ctx

    def test_context_overwritten_on_new_skill(self, tmp_path):
        """同一セッションで別の Skill が呼ばれると文脈が上書きされる。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event1 = {
                "tool_name": "Skill",
                "tool_input": {"skill": "opsx:refine"},
                "session_id": "sess-wf-002",
            }
            workflow_context.handle_pre_tool_use(event1)

            ctx_path = tmp_path / "rl-anything-workflow-sess-wf-002.json"
            ctx1 = json.loads(ctx_path.read_text())
            wf_id_1 = ctx1["workflow_id"]

            event2 = {
                "tool_name": "Skill",
                "tool_input": {"skill": "opsx:apply"},
                "session_id": "sess-wf-002",
            }
            workflow_context.handle_pre_tool_use(event2)

            ctx2 = json.loads(ctx_path.read_text())
            assert ctx2["skill_name"] == "opsx:apply"
            assert ctx2["workflow_id"] != wf_id_1

    def test_no_session_id_noop(self, tmp_path):
        """session_id がない場合は何もしない。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "test"},
                "session_id": "",
            }
            workflow_context.handle_pre_tool_use(event)
            assert not list(tmp_path.glob("rl-anything-workflow-*"))

    def test_no_skill_name_noop(self, tmp_path):
        """skill_name がない場合は何もしない。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "tool_name": "Skill",
                "tool_input": {},
                "session_id": "sess-wf-003",
            }
            workflow_context.handle_pre_tool_use(event)
            assert not list(tmp_path.glob("rl-anything-workflow-*"))


class TestReadWorkflowContext:
    """common.read_workflow_context() のテスト。"""

    def test_context_exists(self, tmp_path):
        """文脈ファイルが存在する場合、parent_skill と workflow_id を返す。"""
        ctx = {
            "skill_name": "opsx:refine",
            "session_id": "sess-rwc-001",
            "workflow_id": "wf-abc12345",
            "started_at": "2026-03-03T10:00:00+00:00",
        }
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-rwc-001.json"
            ctx_path.write_text(json.dumps(ctx))

            result = common.read_workflow_context("sess-rwc-001")
            assert result["parent_skill"] == "opsx:refine"
            assert result["workflow_id"] == "wf-abc12345"

    def test_context_not_exists(self, tmp_path):
        """文脈ファイルが存在しない場合、null を返す。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            result = common.read_workflow_context("sess-rwc-002")
            assert result["parent_skill"] is None
            assert result["workflow_id"] is None

    def test_context_corrupted(self, tmp_path):
        """文脈ファイルが破損している場合、null を返す。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-rwc-003.json"
            ctx_path.write_text("NOT VALID JSON{{{")

            result = common.read_workflow_context("sess-rwc-003")
            assert result["parent_skill"] is None
            assert result["workflow_id"] is None

    def test_context_expired(self, tmp_path):
        """24時間以上経過した文脈ファイルは無効。"""
        ctx = {
            "skill_name": "opsx:refine",
            "workflow_id": "wf-expired1",
        }
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-rwc-004.json"
            ctx_path.write_text(json.dumps(ctx))

            # mtime を25時間前に設定
            old_time = time.time() - (25 * 60 * 60)
            os.utime(ctx_path, (old_time, old_time))

            result = common.read_workflow_context("sess-rwc-004")
            assert result["parent_skill"] is None
            assert result["workflow_id"] is None


class TestClassifyPrompt:
    """common.classify_prompt() のテスト。"""

    def test_spec_review(self):
        assert common.classify_prompt("review the spec requirements") == "spec-review"

    def test_code_exploration(self):
        assert common.classify_prompt("explore the codebase structure") == "code-exploration"

    def test_research(self):
        assert common.classify_prompt("research best practice for caching") == "research"

    def test_code_review(self):
        assert common.classify_prompt("review code changes in auth module") == "code-review"

    def test_implementation(self):
        assert common.classify_prompt("implement the new feature") == "implementation"

    def test_other(self):
        assert common.classify_prompt("hello world") == "other"

    def test_case_insensitive(self):
        assert common.classify_prompt("EXPLORE the CODEBASE") == "code-exploration"

    def test_empty_prompt(self):
        assert common.classify_prompt("") == "other"


class TestObserve:
    """observe.py のテスト。"""

    def test_skill_usage_recorded(self, patch_data_dir):
        event = {
            "tool_name": "Skill",
            "tool_input": {"skill": "my-skill", "args": "test.py"},
            "tool_result": {},
            "session_id": "sess-001",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        assert usage_file.exists()
        record = json.loads(usage_file.read_text().strip())
        assert record["skill_name"] == "my-skill"
        assert record["session_id"] == "sess-001"

    def test_global_skill_registers(self, patch_data_dir):
        global_prefix = str(Path.home() / ".claude" / "skills")
        event = {
            "tool_name": "Skill",
            "tool_input": {"skill": f"{global_prefix}/my-global"},
            "tool_result": {},
            "session_id": "sess-002",
        }
        observe.handle_post_tool_use(event)

        registry_file = patch_data_dir / "usage-registry.jsonl"
        assert registry_file.exists()
        record = json.loads(registry_file.read_text().strip())
        assert "project_path" in record

    def test_error_recorded(self, patch_data_dir):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "false"},
            "tool_result": {"is_error": True, "content": "exit code 1"},
            "session_id": "sess-003",
        }
        observe.handle_post_tool_use(event)

        errors_file = patch_data_dir / "errors.jsonl"
        assert errors_file.exists()
        record = json.loads(errors_file.read_text().strip())
        assert record["tool_name"] == "Bash"

    def test_non_skill_tool_no_usage(self, patch_data_dir):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x"},
            "tool_result": {},
            "session_id": "sess-004",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        assert not usage_file.exists()

    def test_write_failure_silent(self, tmp_data_dir):
        """JSONL 書き込み失敗時、例外を投げない。"""
        bad_dir = tmp_data_dir / "nonexistent_sub" / "deep"
        with mock.patch.object(common, "DATA_DIR", bad_dir):
            with mock.patch.object(common, "ensure_data_dir"):
                # ensure_data_dir を無効化して書き込み先を壊す
                event = {
                    "tool_name": "Skill",
                    "tool_input": {"skill": "test"},
                    "tool_result": {},
                    "session_id": "sess-005",
                }
                # 例外が出ないことを確認
                observe.handle_post_tool_use(event)

    def test_directory_auto_created(self, tmp_path):
        """ディレクトリが存在しない場合 MUST 自動作成する。"""
        new_dir = tmp_path / "new-rl-anything"
        with mock.patch.object(common, "DATA_DIR", new_dir):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "test"},
                "tool_result": {},
                "session_id": "sess-006",
            }
            observe.handle_post_tool_use(event)

        assert new_dir.exists()

    def test_agent_tool_usage_recorded(self, patch_data_dir):
        """Agent ツール呼び出しが usage.jsonl に記録される。"""
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": "codebase を探索してください",
            },
            "tool_result": {},
            "session_id": "sess-100",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        assert usage_file.exists()
        record = json.loads(usage_file.read_text().strip())
        assert record["skill_name"] == "Agent:Explore"
        assert record["subagent_type"] == "Explore"
        assert record["prompt"] == "codebase を探索してください"
        assert record["session_id"] == "sess-100"

    def test_agent_tool_prompt_truncated(self, patch_data_dir):
        """Agent ツールの prompt が 200 文字に切り詰められる。"""
        long_prompt = "あ" * 300
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "general-purpose",
                "prompt": long_prompt,
            },
            "tool_result": {},
            "session_id": "sess-101",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert len(record["prompt"]) == 200

    def test_agent_tool_empty_prompt(self, patch_data_dir):
        """Agent ツールの prompt が空の場合、空文字列として記録される。"""
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": "",
            },
            "tool_result": {},
            "session_id": "sess-102",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["prompt"] == ""

    def test_agent_tool_missing_subagent_type(self, patch_data_dir):
        """Agent ツールの subagent_type が未指定の場合、'unknown' として記録される。"""
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "prompt": "何かやって",
            },
            "tool_result": {},
            "session_id": "sess-103",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["skill_name"] == "Agent:unknown"
        assert record["subagent_type"] == "unknown"

    def test_agent_tool_null_subagent_type(self, patch_data_dir):
        """Agent ツールの subagent_type が None の場合、'unknown' として記録される。"""
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": None,
                "prompt": "何かやって",
            },
            "tool_result": {},
            "session_id": "sess-104",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["subagent_type"] == "unknown"

    def test_agent_with_parent_skill(self, patch_data_dir, tmp_path):
        """ワークフロー文脈がある場合、parent_skill と workflow_id が付与される。"""
        ctx = {
            "skill_name": "opsx:refine",
            "session_id": "sess-110",
            "workflow_id": "wf-test1234",
            "started_at": "2026-03-03T10:00:00+00:00",
        }
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-110.json"
            ctx_path.write_text(json.dumps(ctx))

            event = {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "Explore", "prompt": "explore"},
                "tool_result": {},
                "session_id": "sess-110",
            }
            observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["parent_skill"] == "opsx:refine"
        assert record["workflow_id"] == "wf-test1234"

    def test_agent_without_parent_skill(self, patch_data_dir, tmp_path):
        """ワークフロー文脈がない場合、parent_skill と workflow_id は null。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "Explore", "prompt": "explore"},
                "tool_result": {},
                "session_id": "sess-111",
            }
            observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["parent_skill"] is None
        assert record["workflow_id"] is None


class TestSubagentObserve:
    """subagent_observe.py のテスト。"""

    def test_subagent_stop_recorded(self, patch_data_dir):
        """SubagentStop イベントが subagents.jsonl に記録される。"""
        event = {
            "agent_type": "Explore",
            "agent_id": "agent-001",
            "last_assistant_message": "探索が完了しました",
            "agent_transcript_path": "/tmp/transcript.jsonl",
            "session_id": "sess-200",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        assert subagents_file.exists()
        record = json.loads(subagents_file.read_text().strip())
        assert record["agent_type"] == "Explore"
        assert record["agent_id"] == "agent-001"
        assert record["last_assistant_message"] == "探索が完了しました"
        assert record["agent_transcript_path"] == "/tmp/transcript.jsonl"
        assert record["session_id"] == "sess-200"
        assert "timestamp" in record

    def test_last_message_truncated(self, patch_data_dir):
        """last_assistant_message が 500 文字に切り詰められる。"""
        long_message = "あ" * 600
        event = {
            "agent_type": "general-purpose",
            "agent_id": "agent-002",
            "last_assistant_message": long_message,
            "agent_transcript_path": "/tmp/t.jsonl",
            "session_id": "sess-201",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert len(record["last_assistant_message"]) == 500

    def test_empty_last_message(self, patch_data_dir):
        """last_assistant_message が空の場合、空文字列として記録される。"""
        event = {
            "agent_type": "Explore",
            "agent_id": "agent-003",
            "last_assistant_message": "",
            "agent_transcript_path": "/tmp/t.jsonl",
            "session_id": "sess-202",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["last_assistant_message"] == ""

    def test_null_last_message(self, patch_data_dir):
        """last_assistant_message が null の場合、空文字列として記録される。"""
        event = {
            "agent_type": "Explore",
            "agent_id": "agent-004",
            "last_assistant_message": None,
            "agent_transcript_path": "/tmp/t.jsonl",
            "session_id": "sess-203",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["last_assistant_message"] == ""

    def test_nonexistent_transcript_path(self, patch_data_dir):
        """agent_transcript_path が存在しないパスでもパスのみ記録する。"""
        event = {
            "agent_type": "Explore",
            "agent_id": "agent-005",
            "last_assistant_message": "done",
            "agent_transcript_path": "/nonexistent/path/transcript.jsonl",
            "session_id": "sess-204",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["agent_transcript_path"] == "/nonexistent/path/transcript.jsonl"

    def test_write_failure_silent(self, tmp_data_dir):
        """書き込み失敗時、例外を投げない（MUST NOT block session）。"""
        bad_dir = tmp_data_dir / "nonexistent_sub" / "deep"
        with mock.patch.object(common, "DATA_DIR", bad_dir):
            with mock.patch.object(common, "ensure_data_dir"):
                event = {
                    "agent_type": "Explore",
                    "agent_id": "agent-006",
                    "last_assistant_message": "test",
                    "agent_transcript_path": "/tmp/t.jsonl",
                    "session_id": "sess-205",
                }
                subagent_observe.handle_subagent_stop(event)

    def test_parent_skill_attached(self, patch_data_dir, tmp_path):
        """ワークフロー文脈がある場合、parent_skill が subagents.jsonl に付与される。"""
        ctx = {
            "skill_name": "opsx:refine",
            "session_id": "sess-210",
            "workflow_id": "wf-sub12345",
        }
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-210.json"
            ctx_path.write_text(json.dumps(ctx))

            event = {
                "agent_type": "Explore",
                "agent_id": "agent-010",
                "last_assistant_message": "done",
                "agent_transcript_path": "/tmp/t.jsonl",
                "session_id": "sess-210",
            }
            subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["parent_skill"] == "opsx:refine"
        assert record["workflow_id"] == "wf-sub12345"

    def test_no_parent_skill(self, patch_data_dir, tmp_path):
        """ワークフロー文脈がない場合、parent_skill は null。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "agent_type": "Explore",
                "agent_id": "agent-011",
                "last_assistant_message": "done",
                "agent_transcript_path": "/tmp/t.jsonl",
                "session_id": "sess-211",
            }
            subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["parent_skill"] is None
        assert record["workflow_id"] is None


class TestSessionSummary:
    """session_summary.py のテスト。"""

    def test_session_summary_recorded(self, patch_data_dir):
        # まず usage を書き込む
        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"session_id": "sess-010", "skill_name": "a"}) + "\n"
            + json.dumps({"session_id": "sess-010", "skill_name": "b"}) + "\n"
        )

        event = {"session_id": "sess-010"}
        session_summary.handle_stop(event)

        sessions_file = patch_data_dir / "sessions.jsonl"
        assert sessions_file.exists()
        record = json.loads(sessions_file.read_text().strip())
        assert record["session_id"] == "sess-010"
        assert record["skill_count"] == 2
        assert record["error_count"] == 0


    def test_workflow_sequence_recorded(self, patch_data_dir, tmp_path):
        """ワークフローシーケンスが workflows.jsonl に書き出される。"""
        usage_file = patch_data_dir / "usage.jsonl"
        records = [
            {
                "session_id": "sess-wfs-001",
                "skill_name": "Agent:Explore",
                "workflow_id": "wf-seqtest1",
                "parent_skill": "opsx:refine",
                "prompt": "explore the codebase structure",
                "timestamp": "2026-03-03T10:00:00+00:00",
            },
            {
                "session_id": "sess-wfs-001",
                "skill_name": "Agent:Explore",
                "workflow_id": "wf-seqtest1",
                "parent_skill": "opsx:refine",
                "prompt": "review spec requirements",
                "timestamp": "2026-03-03T10:01:00+00:00",
            },
            {
                "session_id": "sess-wfs-001",
                "skill_name": "Agent:general-purpose",
                "workflow_id": "wf-seqtest1",
                "parent_skill": "opsx:refine",
                "prompt": "implement the changes",
                "timestamp": "2026-03-03T10:02:00+00:00",
            },
        ]
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {"session_id": "sess-wfs-001"}
            session_summary.handle_stop(event)

        workflows_file = patch_data_dir / "workflows.jsonl"
        assert workflows_file.exists()
        wf = json.loads(workflows_file.read_text().strip())
        assert wf["workflow_id"] == "wf-seqtest1"
        assert wf["skill_name"] == "opsx:refine"
        assert wf["step_count"] == 3
        assert len(wf["steps"]) == 3
        assert wf["steps"][0]["tool"] == "Agent:Explore"
        assert wf["steps"][0]["intent_category"] == "code-exploration"
        assert wf["steps"][1]["intent_category"] == "spec-review"
        assert wf["steps"][2]["intent_category"] == "implementation"
        assert wf["source"] == "trace"

    def test_no_workflow_no_record(self, patch_data_dir, tmp_path):
        """ワークフローがないセッションでは workflows.jsonl に何も書き出さない。"""
        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"session_id": "sess-wfs-002", "skill_name": "my-skill"}) + "\n"
        )

        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {"session_id": "sess-wfs-002"}
            session_summary.handle_stop(event)

        workflows_file = patch_data_dir / "workflows.jsonl"
        assert not workflows_file.exists()

    def test_context_file_cleanup(self, patch_data_dir, tmp_path):
        """セッション終了時に文脈ファイルが削除される。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-wfs-003.json"
            ctx_path.write_text('{"skill_name":"test"}')
            assert ctx_path.exists()

            event = {"session_id": "sess-wfs-003"}
            session_summary.handle_stop(event)

            assert not ctx_path.exists()

    def test_context_file_cleanup_not_exists(self, patch_data_dir, tmp_path):
        """文脈ファイルが存在しない場合、エラーは発生しない。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {"session_id": "sess-wfs-004"}
            session_summary.handle_stop(event)  # no error


class TestSaveState:
    """save_state.py のテスト。"""

    def test_checkpoint_saved(self, patch_data_dir):
        event = {
            "session_id": "sess-020",
            "evolve_state": {"generation": 3},
        }
        save_state.handle_pre_compact(event)

        checkpoint_file = patch_data_dir / "checkpoint.json"
        assert checkpoint_file.exists()
        data = json.loads(checkpoint_file.read_text())
        assert data["session_id"] == "sess-020"
        assert data["evolve_state"]["generation"] == 3


class TestRestoreState:
    """restore_state.py のテスト。"""

    def test_checkpoint_restored(self, patch_data_dir, capsys):
        checkpoint = {
            "session_id": "sess-030",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "evolve_state": {"generation": 5},
        }
        (patch_data_dir / "checkpoint.json").write_text(json.dumps(checkpoint))

        restore_state.handle_session_start({})

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())
        assert result["restored"] is True
        assert result["checkpoint"]["evolve_state"]["generation"] == 5

    def test_no_checkpoint_noop(self, patch_data_dir, capsys):
        restore_state.handle_session_start({})

        captured = capsys.readouterr()
        assert captured.out.strip() == ""


# --- discover.py / prune.py のワークフロートレーシング関連テスト ---

# discover/prune のインポートパスを追加
# skills/ 配下を scripts/ より先に挿入（scripts/ にも discover.py があるため優先度を上げる）
_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "prune" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "discover" / "scripts"))


class TestDiscoverContextualization:
    """discover.py の contextualized/ad-hoc 分類テスト。"""

    def test_ad_hoc_only_counted(self, patch_data_dir):
        """ad-hoc レコードのみがスキル候補としてカウントされる。"""
        import discover
        importlib.reload(discover)

        usage_file = patch_data_dir / "usage.jsonl"
        records = []
        # contextualized: 15回（parent_skill あり）
        for i in range(15):
            records.append({
                "skill_name": "Agent:Explore",
                "parent_skill": "opsx:refine",
                "workflow_id": f"wf-ctx{i:04d}",
                "prompt": "explore",
            })
        # ad-hoc: 6回（parent_skill なし、backfill でない）
        for i in range(6):
            records.append({
                "skill_name": "Agent:Explore",
                "prompt": "explore manually",
            })
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.object(discover, "DATA_DIR", patch_data_dir):
            with mock.patch.object(discover, "SUPPRESSION_FILE", patch_data_dir / "suppress.jsonl"):
                patterns = discover.detect_behavior_patterns(threshold=5)

        assert len(patterns) == 1
        assert patterns[0]["count"] == 6  # ad-hoc のみ
        assert patterns[0]["total_count"] == 21  # 全体

    def test_backfill_excluded_as_unknown(self, patch_data_dir):
        """backfill データは unknown として除外される。"""
        import discover
        importlib.reload(discover)

        usage_file = patch_data_dir / "usage.jsonl"
        records = []
        # backfill: 10回
        for i in range(10):
            records.append({
                "skill_name": "Agent:Explore",
                "source": "backfill",
                "prompt": "explore",
            })
        # ad-hoc: 3回（閾値未満）
        for i in range(3):
            records.append({
                "skill_name": "Agent:Explore",
                "prompt": "explore",
            })
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.object(discover, "DATA_DIR", patch_data_dir):
            with mock.patch.object(discover, "SUPPRESSION_FILE", patch_data_dir / "suppress.jsonl"):
                patterns = discover.detect_behavior_patterns(threshold=5)

        # ad-hoc 3回は閾値5未満なので候補なし
        assert len(patterns) == 0


class TestPruneParentSkill:
    """prune.py の parent_skill 経由カウントテスト。"""

    def test_parent_skill_prevents_zero_invocation(self, patch_data_dir):
        """parent_skill 経由で使用されているスキルは淘汰候補にならない。"""
        import prune
        import audit

        usage_file = patch_data_dir / "usage.jsonl"
        # opsx:refine を直接呼んだ記録はないが、parent_skill として参照されている
        records = [
            {
                "skill_name": "Agent:Explore",
                "parent_skill": "opsx:refine",
                "workflow_id": "wf-prune001",
                "timestamp": "2026-03-03T10:00:00+00:00",
            },
        ]
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.object(audit, "DATA_DIR", patch_data_dir):
            usage_records = audit.load_usage_data(days=30)

        used_skills = set()
        for rec in usage_records:
            used_skills.add(rec.get("skill_name", ""))
            parent = rec.get("parent_skill")
            if parent:
                used_skills.add(parent)

        assert "opsx:refine" in used_skills

    def test_no_usage_detected(self, patch_data_dir):
        """直接呼び出しも parent_skill 参照もないスキルは淘汰候補。"""
        import audit

        usage_file = patch_data_dir / "usage.jsonl"
        records = [
            {
                "skill_name": "Agent:Explore",
                "timestamp": "2026-03-03T10:00:00+00:00",
            },
        ]
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.object(audit, "DATA_DIR", patch_data_dir):
            usage_records = audit.load_usage_data(days=30)

        used_skills = set()
        for rec in usage_records:
            used_skills.add(rec.get("skill_name", ""))
            parent = rec.get("parent_skill")
            if parent:
                used_skills.add(parent)

        assert "some-unused-skill" not in used_skills
