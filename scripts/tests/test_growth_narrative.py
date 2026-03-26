#!/usr/bin/env python3
"""growth_narrative のテスト — 環境プロファイル + 成長ストーリー。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from growth_narrative import (
    EnvironmentProfile,
    compute_profile,
    generate_story,
    TRAIT_DEFINITIONS,
)


# ── compute_profile ─────────────────────────────────────────────


class TestComputeProfile:
    def test_strengths_from_usage(self):
        """usage.jsonl のスキル使用頻度から top-3 カテゴリ。"""
        usage_data = [
            {"skill_name": "commit", "count": 50},
            {"skill_name": "review", "count": 30},
            {"skill_name": "ship", "count": 20},
            {"skill_name": "browse", "count": 5},
        ]
        with mock.patch("growth_narrative._query_skill_counts", return_value=usage_data):
            with mock.patch("growth_narrative._query_corrections_stats", return_value={}):
                with mock.patch("growth_narrative._query_crystallization_stats", return_value={"eta": 0.0, "count": 0, "crystallized": 0}):
                    with mock.patch("growth_narrative._query_commit_frequency", return_value=0.0):
                        profile = compute_profile("test-proj")

        assert len(profile.strengths) <= 3
        assert "commit" in profile.strengths

    def test_personality_traits_careful(self):
        """verify 系 corrections > 30% → 慎重派。"""
        stats = {"total": 20, "verify_count": 8, "refactor_count": 1}
        with mock.patch("growth_narrative._query_skill_counts", return_value=[]):
            with mock.patch("growth_narrative._query_corrections_stats", return_value=stats):
                with mock.patch("growth_narrative._query_crystallization_stats", return_value={"eta": 0.0, "count": 0, "crystallized": 0}):
                    with mock.patch("growth_narrative._query_commit_frequency", return_value=0.0):
                        profile = compute_profile("test-proj")

        assert "careful" in profile.personality_traits

    def test_personality_traits_organizer(self):
        """refactor 系 corrections > 25% → 整理好き。"""
        stats = {"total": 20, "verify_count": 1, "refactor_count": 6}
        with mock.patch("growth_narrative._query_skill_counts", return_value=[]):
            with mock.patch("growth_narrative._query_corrections_stats", return_value=stats):
                with mock.patch("growth_narrative._query_crystallization_stats", return_value={"eta": 0.0, "count": 0, "crystallized": 0}):
                    with mock.patch("growth_narrative._query_commit_frequency", return_value=0.0):
                        profile = compute_profile("test-proj")

        assert "organizer" in profile.personality_traits

    def test_empty_telemetry(self):
        """テレメトリ不足 → 空プロファイル。"""
        with mock.patch("growth_narrative._query_skill_counts", return_value=[]):
            with mock.patch("growth_narrative._query_corrections_stats", return_value={}):
                with mock.patch("growth_narrative._query_crystallization_stats", return_value={"eta": 0.0, "count": 0, "crystallized": 0}):
                    with mock.patch("growth_narrative._query_commit_frequency", return_value=0.0):
                        profile = compute_profile("empty-proj")

        assert profile.strengths == []
        assert profile.personality_traits == []
        assert profile.crystallization_style == "unknown"

    def test_crystallization_style_correction_driven(self):
        """結晶化効率 η > 0.5 → correction-driven。"""
        with mock.patch("growth_narrative._query_skill_counts", return_value=[]):
            with mock.patch("growth_narrative._query_corrections_stats", return_value={"total": 10}):
                with mock.patch("growth_narrative._query_crystallization_stats", return_value={"eta": 0.6, "count": 5, "crystallized": 6}):
                    with mock.patch("growth_narrative._query_commit_frequency", return_value=0.0):
                        profile = compute_profile("proj")

        assert profile.crystallization_style == "correction-driven"

    def test_fast_shipper_trait(self):
        """commit/session > 2.0 → fast_shipper。"""
        with mock.patch("growth_narrative._query_skill_counts", return_value=[]):
            with mock.patch("growth_narrative._query_corrections_stats", return_value={}):
                with mock.patch("growth_narrative._query_crystallization_stats", return_value={"eta": 0.0, "count": 0, "crystallized": 0}):
                    with mock.patch("growth_narrative._query_commit_frequency", return_value=2.5):
                        profile = compute_profile("proj")

        assert "fast_shipper" in profile.personality_traits

    def test_fast_shipper_not_triggered_below_threshold(self):
        """commit/session <= 2.0 → fast_shipper なし。"""
        with mock.patch("growth_narrative._query_skill_counts", return_value=[]):
            with mock.patch("growth_narrative._query_corrections_stats", return_value={}):
                with mock.patch("growth_narrative._query_crystallization_stats", return_value={"eta": 0.0, "count": 0, "crystallized": 0}):
                    with mock.patch("growth_narrative._query_commit_frequency", return_value=1.5):
                        profile = compute_profile("proj")

        assert "fast_shipper" not in profile.personality_traits


# ── generate_story ──────────────────────────────────────────────


class TestGenerateStory:
    def test_story_with_events(self):
        """結晶化イベントあり → ストーリー生成。"""
        events = [
            {"ts": "2026-03-10T00:00:00Z", "targets": ["a.md"], "evidence_count": 3, "phase": "initial_nurturing"},
            {"ts": "2026-03-20T00:00:00Z", "targets": ["b.md", "c.md"], "evidence_count": 5, "phase": "structured_nurturing"},
        ]
        with mock.patch("growth_narrative._get_crystallization_events", return_value=events):
            story = generate_story("proj")

        assert len(story) > 0
        assert "a.md" in story or "結晶化" in story

    def test_story_empty_events(self):
        """結晶化イベントなし → 「まだ結晶化イベントがありません」。"""
        with mock.patch("growth_narrative._get_crystallization_events", return_value=[]):
            story = generate_story("proj")

        assert "まだ" in story or "no crystallization" in story.lower()


# ── TRAIT_DEFINITIONS ───────────────────────────────────────────


class TestTraitDefinitions:
    def test_all_traits_have_required_fields(self):
        for trait_id, defn in TRAIT_DEFINITIONS.items():
            assert "name_en" in defn
            assert "name_ja" in defn
            assert "check" in defn
