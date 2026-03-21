"""restore_state.py handover detection tests."""
import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

_hooks_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_hooks_dir))

import restore_state


class TestDetectHandover:
    def test_shows_preview(self, tmp_path, capsys):
        """最新 handover のプレビューが表示される。"""
        hdir = tmp_path / ".claude" / "handovers"
        hdir.mkdir(parents=True)
        content = "# Session Handover\n\n## Summary\nDid important work\n\n## Next Steps\n- Fix bug\n"
        (hdir / "2026-03-22_1500.md").write_text(content, encoding="utf-8")

        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            restore_state._detect_handover()

        captured = capsys.readouterr()
        assert "[rl-anything:handover]" in captured.out
        assert "Session Handover" in captured.out
        assert "2026-03-22_1500.md" in captured.out

    def test_stale_ignored(self, tmp_path, capsys):
        """STALE_HOURS 超のファイルは無視される。"""
        hdir = tmp_path / ".claude" / "handovers"
        hdir.mkdir(parents=True)
        f = hdir / "2026-03-18_0900.md"
        f.write_text("# Old notes", encoding="utf-8")
        # mtime を 72 時間前に設定（48h 超）
        old_mtime = time.time() - 72 * 3600
        os.utime(f, (old_mtime, old_mtime))

        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            restore_state._detect_handover()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_no_project_dir(self, capsys):
        """CLAUDE_PROJECT_DIR 未設定で何もしない。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            restore_state._detect_handover()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_no_handover_dir(self, tmp_path, capsys):
        """handovers/ が存在しない場合は何もしない。"""
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            restore_state._detect_handover()

        captured = capsys.readouterr()
        assert captured.out == ""
