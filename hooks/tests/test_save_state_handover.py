"""save_state.py handover suggestion tests."""
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

_hooks_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_hooks_dir))

import save_state


class TestSuggestHandover:
    def test_suggests_on_precompact(self, tmp_path, capsys):
        """PreCompact 時に提案メッセージが stdout に出る。"""
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            save_state._suggest_handover()

        captured = capsys.readouterr()
        assert "/rl-anything:handover" in captured.out

    def test_no_project_dir(self, capsys):
        """CLAUDE_PROJECT_DIR 未設定で提案しない。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            save_state._suggest_handover()

        captured = capsys.readouterr()
        assert captured.out == ""
