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

    def test_deploy_state_shown_in_preview(self, tmp_path, capsys):
        """Deploy State セクションがプレビューに含まれる。"""
        hdir = tmp_path / ".claude" / "handovers"
        hdir.mkdir(parents=True)
        # Deploy State が 15 行目以降に配置されたノート
        content = (
            "# Handover: 2026-03-25 10:00\n\n"
            "## Decisions\n"
            + "\n".join(f"- Decision {i}" for i in range(20))
            + "\n\n## Deploy State\n- dev: deployed (abc1234)\n- prod: deployed (abc1234)\n\n"
            "## Next Actions\n- Merge PR #99\n"
        )
        (hdir / "2026-03-25_1000.md").write_text(content, encoding="utf-8")

        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            restore_state._detect_handover()

        captured = capsys.readouterr()
        assert "[rl-anything:handover]" in captured.out
        # Deploy State が表示される（先頭15行には含まれないが優先抽出される）
        assert "dev: deployed" in captured.out
        assert "prod: deployed" in captured.out

    def test_next_actions_shown_in_preview(self, tmp_path, capsys):
        """Next Actions セクションがプレビューに含まれる。"""
        hdir = tmp_path / ".claude" / "handovers"
        hdir.mkdir(parents=True)
        content = (
            "# Handover: 2026-03-25 10:00\n\n"
            "## Decisions\n"
            + "\n".join(f"- Decision {i}" for i in range(20))
            + "\n\n## Next Actions\n1. Fix critical bug\n2. Deploy to staging\n"
        )
        (hdir / "2026-03-25_1000.md").write_text(content, encoding="utf-8")

        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            restore_state._detect_handover()

        captured = capsys.readouterr()
        assert "Fix critical bug" in captured.out

    def test_fallback_to_head_when_no_key_sections(self, tmp_path, capsys):
        """キーセクションがない場合は従来通り先頭行プレビュー。"""
        hdir = tmp_path / ".claude" / "handovers"
        hdir.mkdir(parents=True)
        content = "# Handover: 2026-03-25\n\n## Decisions\n- Used new API\n\n## Discarded\n- Old approach\n"
        (hdir / "2026-03-25_1000.md").write_text(content, encoding="utf-8")

        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            restore_state._detect_handover()

        captured = capsys.readouterr()
        assert "Handover: 2026-03-25" in captured.out
        assert "Used new API" in captured.out
