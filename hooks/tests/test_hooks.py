"""observe hooks のスモークテスト。"""
import json
import os
import sys
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
