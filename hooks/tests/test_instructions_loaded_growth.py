#!/usr/bin/env python3
"""InstructionsLoaded hook の growth greeting テスト。"""
import json
import os
import sys
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "lib"))

import instructions_loaded


class TestGrowthGreeting:
    """_emit_growth_greeting のテスト。"""

    def test_emits_growth_data_with_level(self, tmp_path, capsys):
        """キャッシュに level あり → GROWTH Lv.N Title 表示。"""
        cache_data = {
            "phase": "structured_nurturing",
            "progress": 0.72,
            "updated_at": "2026-03-25T15:00:00+00:00",
            "level": 7,
            "title_en": "Experienced",
        }
        cache_file = tmp_path / "growth-state-myproj.json"
        cache_file.write_text(json.dumps(cache_data))

        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            with mock.patch.dict(os.environ, {}, clear=False):
                instructions_loaded._emit_growth_greeting("myproj")

        captured = capsys.readouterr()
        assert "GROWTH:" in captured.out
        assert "Lv.7" in captured.out
        assert "Experienced" in captured.out
        assert "structured_nurturing" in captured.out
        assert "72%" in captured.out

    def test_emits_growth_data_without_level(self, tmp_path, capsys):
        """キャッシュに level なし → 旧フォーマット。"""
        cache_data = {
            "phase": "structured_nurturing",
            "progress": 0.72,
            "updated_at": "2026-03-25T15:00:00+00:00",
        }
        cache_file = tmp_path / "growth-state-myproj.json"
        cache_file.write_text(json.dumps(cache_data))

        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            with mock.patch.dict(os.environ, {}, clear=False):
                instructions_loaded._emit_growth_greeting("myproj")

        captured = capsys.readouterr()
        assert "GROWTH:" in captured.out
        assert "Lv." not in captured.out
        assert "structured_nurturing" in captured.out
        assert "72%" in captured.out

    def test_no_output_when_cache_missing(self, tmp_path, capsys):
        """キャッシュ未存在 → 出力なし。"""
        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            instructions_loaded._emit_growth_greeting("nonexistent")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_no_output_when_display_disabled(self, tmp_path, capsys):
        """growth_display=false → 出力なし。"""
        cache_data = {"phase": "bootstrap", "progress": 0.5, "updated_at": "2026-03-25T15:00:00+00:00"}
        cache_file = tmp_path / "growth-state-proj.json"
        cache_file.write_text(json.dumps(cache_data))

        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_OPTION_growth_display": "false"}):
                instructions_loaded._emit_growth_greeting("proj")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_stale_warning(self, tmp_path, capsys):
        """7日超 → stale 表示。"""
        from datetime import datetime, timedelta, timezone

        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        cache_data = {"phase": "bootstrap", "progress": 0.3, "updated_at": old_ts}
        cache_file = tmp_path / "growth-state-old.json"
        cache_file.write_text(json.dumps(cache_data))

        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            instructions_loaded._emit_growth_greeting("old")

        captured = capsys.readouterr()
        assert "stale" in captured.out

    def test_no_output_when_project_none(self, capsys):
        """project=None → 出力なし。"""
        instructions_loaded._emit_growth_greeting(None)
        captured = capsys.readouterr()
        assert captured.out == ""
