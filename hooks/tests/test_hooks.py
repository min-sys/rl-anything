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

import observe
import session_summary
import save_state
import restore_state


@pytest.fixture
def tmp_data_dir(tmp_path):
    """テスト用の一時データディレクトリ。"""
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    return data_dir


class TestObserve:
    """observe.py のテスト。"""

    def test_skill_usage_recorded(self, tmp_data_dir):
        with mock.patch.object(observe, "DATA_DIR", tmp_data_dir):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "my-skill", "args": "test.py"},
                "tool_result": {},
                "session_id": "sess-001",
            }
            observe.handle_post_tool_use(event)

        usage_file = tmp_data_dir / "usage.jsonl"
        assert usage_file.exists()
        record = json.loads(usage_file.read_text().strip())
        assert record["skill_name"] == "my-skill"
        assert record["session_id"] == "sess-001"

    def test_global_skill_registers(self, tmp_data_dir):
        global_prefix = str(Path.home() / ".claude" / "skills")
        with mock.patch.object(observe, "DATA_DIR", tmp_data_dir):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": f"{global_prefix}/my-global"},
                "tool_result": {},
                "session_id": "sess-002",
            }
            observe.handle_post_tool_use(event)

        registry_file = tmp_data_dir / "usage-registry.jsonl"
        assert registry_file.exists()
        record = json.loads(registry_file.read_text().strip())
        assert "project_path" in record

    def test_error_recorded(self, tmp_data_dir):
        with mock.patch.object(observe, "DATA_DIR", tmp_data_dir):
            event = {
                "tool_name": "Bash",
                "tool_input": {"command": "false"},
                "tool_result": {"is_error": True, "content": "exit code 1"},
                "session_id": "sess-003",
            }
            observe.handle_post_tool_use(event)

        errors_file = tmp_data_dir / "errors.jsonl"
        assert errors_file.exists()
        record = json.loads(errors_file.read_text().strip())
        assert record["tool_name"] == "Bash"

    def test_non_skill_tool_no_usage(self, tmp_data_dir):
        with mock.patch.object(observe, "DATA_DIR", tmp_data_dir):
            event = {
                "tool_name": "Read",
                "tool_input": {"file_path": "/tmp/x"},
                "tool_result": {},
                "session_id": "sess-004",
            }
            observe.handle_post_tool_use(event)

        usage_file = tmp_data_dir / "usage.jsonl"
        assert not usage_file.exists()

    def test_write_failure_silent(self, tmp_data_dir):
        """JSONL 書き込み失敗時、例外を投げない。"""
        bad_dir = tmp_data_dir / "nonexistent_sub" / "deep"
        with mock.patch.object(observe, "DATA_DIR", bad_dir):
            with mock.patch.object(observe, "ensure_data_dir"):
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
        with mock.patch.object(observe, "DATA_DIR", new_dir):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "test"},
                "tool_result": {},
                "session_id": "sess-006",
            }
            observe.handle_post_tool_use(event)

        assert new_dir.exists()


class TestSessionSummary:
    """session_summary.py のテスト。"""

    def test_session_summary_recorded(self, tmp_data_dir):
        # まず usage を書き込む
        usage_file = tmp_data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"session_id": "sess-010", "skill_name": "a"}) + "\n"
            + json.dumps({"session_id": "sess-010", "skill_name": "b"}) + "\n"
        )

        with mock.patch.object(session_summary, "DATA_DIR", tmp_data_dir):
            event = {"session_id": "sess-010"}
            session_summary.handle_stop(event)

        sessions_file = tmp_data_dir / "sessions.jsonl"
        assert sessions_file.exists()
        record = json.loads(sessions_file.read_text().strip())
        assert record["session_id"] == "sess-010"
        assert record["skill_count"] == 2
        assert record["error_count"] == 0


class TestSaveState:
    """save_state.py のテスト。"""

    def test_checkpoint_saved(self, tmp_data_dir):
        with mock.patch.object(save_state, "DATA_DIR", tmp_data_dir):
            event = {
                "session_id": "sess-020",
                "evolve_state": {"generation": 3},
            }
            save_state.handle_pre_compact(event)

        checkpoint_file = tmp_data_dir / "checkpoint.json"
        assert checkpoint_file.exists()
        data = json.loads(checkpoint_file.read_text())
        assert data["session_id"] == "sess-020"
        assert data["evolve_state"]["generation"] == 3


class TestRestoreState:
    """restore_state.py のテスト。"""

    def test_checkpoint_restored(self, tmp_data_dir, capsys):
        checkpoint = {
            "session_id": "sess-030",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "evolve_state": {"generation": 5},
        }
        (tmp_data_dir / "checkpoint.json").write_text(json.dumps(checkpoint))

        with mock.patch.object(restore_state, "DATA_DIR", tmp_data_dir):
            restore_state.handle_session_start({})

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())
        assert result["restored"] is True
        assert result["checkpoint"]["evolve_state"]["generation"] == 5

    def test_no_checkpoint_noop(self, tmp_data_dir, capsys):
        with mock.patch.object(restore_state, "DATA_DIR", tmp_data_dir):
            restore_state.handle_session_start({})

        captured = capsys.readouterr()
        assert captured.out.strip() == ""
