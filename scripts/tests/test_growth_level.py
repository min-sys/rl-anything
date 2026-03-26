#!/usr/bin/env python3
"""growth_level のテスト — env_score → レベル + 称号 + XP 進捗。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from growth_level import (
    LEVEL_THRESHOLDS,
    LevelInfo,
    XPProgress,
    compute_level,
    compute_xp_progress,
)


# ── compute_level ────────────────────────────────────────────────


class TestComputeLevel:
    """env_score → LevelInfo のマッピング。"""

    def test_zero_score_seedling(self):
        """env_score=0.0 → Lv.1 Seedling。"""
        result = compute_level(0.0)
        assert result.level == 1
        assert result.title_en == "Seedling"
        assert result.title_ja == "芽生え"

    def test_below_threshold_stays_at_level(self):
        """env_score=0.14 → Lv.1（Lv.2 の 0.15 未満）。"""
        result = compute_level(0.14)
        assert result.level == 1

    def test_exact_threshold_promotes(self):
        """env_score=0.15 → Lv.2 Sprout（境界値でちょうど昇格）。"""
        result = compute_level(0.15)
        assert result.level == 2
        assert result.title_en == "Sprout"
        assert result.title_ja == "若芽"

    def test_mid_score(self):
        """env_score=0.50 → Lv.5 Established。"""
        result = compute_level(0.50)
        assert result.level == 5
        assert result.title_en == "Established"

    def test_max_level(self):
        """env_score=0.90 → Lv.10 Evolutionist。"""
        result = compute_level(0.90)
        assert result.level == 10
        assert result.title_en == "Evolutionist"
        assert result.title_ja == "進化の体現者"

    def test_above_max_capped(self):
        """env_score=0.99 → Lv.10（キャップ）。"""
        result = compute_level(0.99)
        assert result.level == 10

    def test_negative_score_safe(self):
        """env_score=-0.1 → Lv.1（安全ガード）。"""
        result = compute_level(-0.1)
        assert result.level == 1

    def test_perfect_score(self):
        """env_score=1.0 → Lv.10。"""
        result = compute_level(1.0)
        assert result.level == 10

    def test_returns_level_info(self):
        """戻り値が LevelInfo インスタンス。"""
        result = compute_level(0.5)
        assert isinstance(result, LevelInfo)
        assert isinstance(result.env_score, float)
        assert isinstance(result.threshold, float)


# ── compute_xp_progress ──────────────────────────────────────────


class TestComputeXPProgress:
    """次レベルまでの進捗率。"""

    def test_level_1_progress(self):
        """Lv.1 内の進捗率が 0.0-1.0 の範囲。"""
        result = compute_xp_progress(0.07)
        assert isinstance(result, XPProgress)
        assert 0.0 <= result.progress <= 1.0
        assert result.current_level.level == 1

    def test_mid_level_progress(self):
        """Lv.5 の中間地点 → ~50% progress。"""
        # Lv.5 = 0.45, Lv.6 = 0.55, midpoint = 0.50
        result = compute_xp_progress(0.50)
        assert result.current_level.level == 5
        assert result.progress == pytest.approx(0.5, abs=0.05)

    def test_max_level_progress(self):
        """Lv.10 → progress=1.0, score_needed=0.0。"""
        result = compute_xp_progress(0.95)
        assert result.current_level.level == 10
        assert result.progress == 1.0
        assert result.score_needed == 0.0

    def test_exact_threshold(self):
        """ちょうど次レベルの threshold → progress=0.0 (新レベルの開始)。"""
        result = compute_xp_progress(0.55)
        assert result.current_level.level == 6
        assert result.progress == pytest.approx(0.0, abs=0.01)


# ── LEVEL_THRESHOLDS ──────────────────────────────────────────────


class TestLevelThresholds:
    """テーブルの構造的整合性。"""

    def test_has_10_levels(self):
        assert len(LEVEL_THRESHOLDS) == 10

    def test_thresholds_ascending(self):
        """閾値が昇順。"""
        thresholds = [t[0] for t in LEVEL_THRESHOLDS]
        assert thresholds == sorted(thresholds)

    def test_levels_sequential(self):
        """レベル番号が 1-10 の連番。"""
        levels = [t[1] for t in LEVEL_THRESHOLDS]
        assert levels == list(range(1, 11))

    def test_all_have_titles(self):
        """全エントリに en/ja タイトル。"""
        for threshold, level, title_en, title_ja in LEVEL_THRESHOLDS:
            assert len(title_en) > 0
            assert len(title_ja) > 0
