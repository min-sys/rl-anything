"""file_changed.py hook のユニットテスト。"""
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from file_changed import handle_file_changed, _discover_rule_files


class TestHandleFileChanged:
    """handle_file_changed() のテスト。"""

    def test_watched_file_triggers_evaluation(self, tmp_path):
        """CLAUDE.md 変更で evaluate_file_changed が呼び出される。"""
        event = {
            "session_id": "test-123",
            "file_path": "/project/CLAUDE.md",
            "event": "change",
            "hook_event_name": "FileChanged",
            "cwd": "/project",
        }
        with mock.patch("file_changed.evaluate_file_changed") as mock_eval:
            mock_eval.return_value = mock.MagicMock(
                triggered=True,
                message="claude_md ファイルが変更されました。推奨: /rl-anything:audit",
            )
            result = handle_file_changed(event)
        mock_eval.assert_called_once()
        assert result is not None
        assert "systemMessage" in result

    def test_non_watched_file_skipped(self):
        """random.py は無視される。"""
        event = {
            "session_id": "test-123",
            "file_path": "/project/src/main.py",
            "event": "change",
            "hook_event_name": "FileChanged",
            "cwd": "/project",
        }
        with mock.patch("file_changed.evaluate_file_changed") as mock_eval:
            result = handle_file_changed(event)
        mock_eval.assert_not_called()
        assert result is None

    def test_watchpaths_output(self, tmp_path):
        """watchPaths に .claude/rules/*.md のファイルが含まれる。"""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "tdd-first.md").write_text("# TDD", encoding="utf-8")
        (rules_dir / "verify.md").write_text("# Verify", encoding="utf-8")

        event = {
            "session_id": "test-123",
            "file_path": str(tmp_path / "CLAUDE.md"),
            "event": "change",
            "hook_event_name": "FileChanged",
            "cwd": str(tmp_path),
        }
        with mock.patch("file_changed.evaluate_file_changed") as mock_eval:
            mock_eval.return_value = mock.MagicMock(
                triggered=True,
                message="test",
            )
            result = handle_file_changed(event)
        assert result is not None
        watch_paths = result.get("watchPaths", [])
        assert len(watch_paths) >= 2
        assert any("tdd-first.md" in p for p in watch_paths)
        assert any("verify.md" in p for p in watch_paths)


class TestDiscoverRuleFiles:
    """_discover_rule_files() のテスト。"""

    def test_finds_rules(self, tmp_path):
        """rules ディレクトリ配下の .md ファイルを発見する。"""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "a.md").write_text("a", encoding="utf-8")
        (rules_dir / "b.md").write_text("b", encoding="utf-8")
        (rules_dir / "not-md.txt").write_text("x", encoding="utf-8")
        paths = _discover_rule_files(str(tmp_path))
        assert len(paths) == 2

    def test_missing_rules_dir(self, tmp_path):
        """.claude/rules/ がない場合は空リスト。"""
        paths = _discover_rule_files(str(tmp_path))
        assert paths == []
