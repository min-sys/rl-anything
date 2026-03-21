"""save_state.py handover suggestion tests."""
import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

_hooks_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_hooks_dir))

import save_state


class TestSuggestHandover:
    def test_suggests_on_precompact(self, tmp_path, capsys):
        """PreCompact 時に提案メッセージが stdout に出る。"""
        hdir = tmp_path / ".claude" / "handovers"
        hdir.mkdir(parents=True)

        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            save_state._suggest_handover()

        captured = capsys.readouterr()
        assert "/rl-anything:handover" in captured.out

    def test_cooldown_suppresses(self, tmp_path, capsys):
        """直近 1 時間以内に handover 済みなら提案しない。"""
        hdir = tmp_path / ".claude" / "handovers"
        hdir.mkdir(parents=True)
        # 直近のファイルを作成
        recent = hdir / "2026-03-22_1500.md"
        recent.write_text("# Recent handover", encoding="utf-8")

        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            save_state._suggest_handover()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_no_project_dir(self, capsys):
        """CLAUDE_PROJECT_DIR 未設定で提案しない。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            # CLAUDE_PROJECT_DIR を確実に除去
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            save_state._suggest_handover()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_old_handover_suggests(self, tmp_path, capsys):
        """古い handover がある場合は提案する。"""
        hdir = tmp_path / ".claude" / "handovers"
        hdir.mkdir(parents=True)
        old = hdir / "2026-03-20_0900.md"
        old.write_text("# Old handover", encoding="utf-8")
        # mtime を 2 時間前に設定
        old_mtime = time.time() - 7200
        os.utime(old, (old_mtime, old_mtime))

        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            save_state._suggest_handover()

        captured = capsys.readouterr()
        assert "/rl-anything:handover" in captured.out
