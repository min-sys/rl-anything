#!/usr/bin/env python3
"""growth_engine のテスト — Phase 判定 + 進捗率 + キャッシュ層。"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from growth_engine import (
    Phase,
    PhaseInfo,
    detect_phase,
    compute_phase_progress,
    update_cache,
    read_cache,
    PHASE_DISPLAY_NAMES,
    STALENESS_WARN_DAYS,
    STALENESS_HIDE_DAYS,
)


# ── detect_phase: 降順判定 ──────────────────────────────────────


class TestDetectPhase:
    """降順 (Mature → Structured → Initial → Bootstrap) で判定。"""

    def test_mature_operation(self):
        """sessions>200, crystallized_rules>=10, coherence>=0.7 → Mature。"""
        result = detect_phase(
            sessions_count=250,
            corrections_count=30,
            crystallized_rules=12,
            coherence_score=0.75,
        )
        assert result == Phase.MATURE_OPERATION

    def test_structured_nurturing(self):
        """sessions 50-200, corrections>=10, crystallized_rules>=3 → Structured。"""
        result = detect_phase(
            sessions_count=150,
            corrections_count=15,
            crystallized_rules=5,
            coherence_score=0.5,
        )
        assert result == Phase.STRUCTURED_NURTURING

    def test_initial_nurturing(self):
        """sessions>=10 but not enough for Structured → Initial。"""
        result = detect_phase(
            sessions_count=30,
            corrections_count=5,
            crystallized_rules=0,
            coherence_score=0.3,
        )
        assert result == Phase.INITIAL_NURTURING

    def test_bootstrap(self):
        """sessions<10 → Bootstrap。"""
        result = detect_phase(
            sessions_count=5,
            corrections_count=2,
            crystallized_rules=0,
            coherence_score=0.0,
        )
        assert result == Phase.BOOTSTRAP

    def test_fallback_to_initial_when_gap(self):
        """sessions=100, corrections=5 → Initial (Structured 条件未達)。"""
        result = detect_phase(
            sessions_count=100,
            corrections_count=5,
            crystallized_rules=1,
            coherence_score=0.3,
        )
        assert result == Phase.INITIAL_NURTURING

    def test_data_insufficient(self):
        """全て 0 → Bootstrap。"""
        result = detect_phase(
            sessions_count=0,
            corrections_count=0,
            crystallized_rules=0,
            coherence_score=0.0,
        )
        assert result == Phase.BOOTSTRAP


# ── compute_phase_progress ──────────────────────────────────────


class TestComputePhaseProgress:
    """各フェーズ内での進捗率 (0.0-1.0)。"""

    def test_bootstrap_progress(self):
        """Bootstrap: sessions/10 で進捗。"""
        progress = compute_phase_progress(
            Phase.BOOTSTRAP,
            sessions_count=5,
            corrections_count=0,
            crystallized_rules=0,
            coherence_score=0.0,
        )
        assert 0.0 <= progress <= 1.0
        assert progress == pytest.approx(0.5, abs=0.1)

    def test_initial_progress(self):
        """Initial: sessions と corrections の複合進捗。"""
        progress = compute_phase_progress(
            Phase.INITIAL_NURTURING,
            sessions_count=30,
            corrections_count=5,
            crystallized_rules=0,
            coherence_score=0.3,
        )
        assert 0.0 <= progress <= 1.0

    def test_structured_progress(self):
        """Structured: sessions, crystallized_rules, coherence の複合。"""
        progress = compute_phase_progress(
            Phase.STRUCTURED_NURTURING,
            sessions_count=150,
            corrections_count=20,
            crystallized_rules=7,
            coherence_score=0.65,
        )
        assert 0.0 <= progress <= 1.0

    def test_mature_progress_capped(self):
        """Mature: 常に 1.0 (最終フェーズ)。"""
        progress = compute_phase_progress(
            Phase.MATURE_OPERATION,
            sessions_count=300,
            corrections_count=50,
            crystallized_rules=15,
            coherence_score=0.85,
        )
        assert progress == 1.0


# ── update_cache / read_cache ───────────────────────────────────


class TestCacheOperations:
    """PJ別ファイル DATA_DIR/growth-state-<project>.json の読み書き。"""

    def test_update_and_read(self, tmp_path):
        """初回書き込み + 読み取り。"""
        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            update_cache(
                project="my-project",
                phase=Phase.STRUCTURED_NURTURING,
                progress=0.72,
                extra={"sessions_count": 156, "crystallizations_count": 12},
            )
            result = read_cache("my-project")

        assert result is not None
        assert result["phase"] == "structured_nurturing"
        assert result["progress"] == pytest.approx(0.72)
        assert result["sessions_count"] == 156
        assert "updated_at" in result

    def test_update_overwrites(self, tmp_path):
        """既存データを上書き。"""
        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            update_cache("proj", Phase.BOOTSTRAP, 0.3, {})
            update_cache("proj", Phase.INITIAL_NURTURING, 0.5, {})
            result = read_cache("proj")

        assert result["phase"] == "initial_nurturing"
        assert result["progress"] == pytest.approx(0.5)

    def test_read_missing_file(self, tmp_path):
        """ファイル未存在 → None。"""
        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            result = read_cache("nonexistent")
        assert result is None

    def test_read_corrupt_json(self, tmp_path):
        """JSON parse エラー → None。"""
        bad_file = tmp_path / "growth-state-bad.json"
        bad_file.write_text("not json{{{", encoding="utf-8")
        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            result = read_cache("bad")
        assert result is None

    def test_read_staleness_warn(self, tmp_path):
        """7日超 → stale=True フラグ付き。"""
        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        cache_file = tmp_path / "growth-state-old.json"
        cache_file.write_text(
            json.dumps({"phase": "bootstrap", "progress": 0.1, "updated_at": old_ts}),
            encoding="utf-8",
        )
        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            result = read_cache("old")

        assert result is not None
        assert result.get("stale") is True

    def test_read_staleness_hide(self, tmp_path):
        """30日超 → None (非表示)。"""
        old_ts = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
        cache_file = tmp_path / "growth-state-ancient.json"
        cache_file.write_text(
            json.dumps({"phase": "bootstrap", "progress": 0.1, "updated_at": old_ts}),
            encoding="utf-8",
        )
        with mock.patch("growth_engine._data_dir", return_value=tmp_path):
            result = read_cache("ancient")

        assert result is None

    def test_update_creates_directory(self, tmp_path):
        """ディレクトリが存在しない場合に作成。"""
        nested = tmp_path / "nested" / "dir"
        with mock.patch("growth_engine._data_dir", return_value=nested):
            update_cache("proj", Phase.BOOTSTRAP, 0.1, {})
            result = read_cache("proj")
        assert result is not None


# ── Phase display names ─────────────────────────────────────────


class TestPhaseDisplayNames:
    """Phase の表示名が定義されていること。"""

    def test_all_phases_have_display_names(self):
        for phase in Phase:
            assert phase in PHASE_DISPLAY_NAMES
            names = PHASE_DISPLAY_NAMES[phase]
            assert "en" in names
            assert "ja" in names
