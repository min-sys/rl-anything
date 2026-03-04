#!/usr/bin/env python3
"""Enrich フェーズのユニットテスト。"""
import sys
from pathlib import Path
from unittest import mock

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "enrich" / "scripts"))

import audit
import enrich


class TestTokenize:
    """tokenize のユニットテスト。"""

    def test_basic_tokenization(self):
        """基本的なトークン化: 空白・句読点で分割、小文字化。"""
        result = enrich.tokenize("Hello World, foo-bar_baz")
        assert "hello" in result
        assert "world" in result
        assert "foo" in result
        assert "bar" in result
        assert "baz" in result

    def test_empty_string(self):
        """空文字列は空集合を返す。"""
        assert enrich.tokenize("") == set()

    def test_duplicate_words(self):
        """重複ワードは集合なので1つになる。"""
        result = enrich.tokenize("test test test")
        assert result == {"test"}


class TestJaccardCoefficient:
    """jaccard_coefficient のユニットテスト。"""

    def test_exact_match(self):
        """完全一致で 1.0 を返す。"""
        assert enrich.jaccard_coefficient({"a", "b"}, {"a", "b"}) == 1.0

    def test_partial_overlap(self):
        """部分一致: {a,b} vs {b,c} => 1/3。"""
        score = enrich.jaccard_coefficient({"a", "b"}, {"b", "c"})
        assert abs(score - 1 / 3) < 1e-9

    def test_no_overlap(self):
        """重複なしで 0.0 を返す。"""
        assert enrich.jaccard_coefficient({"a"}, {"b"}) == 0.0

    def test_both_empty(self):
        """両方空で 0.0 を返す。"""
        assert enrich.jaccard_coefficient(set(), set()) == 0.0

    def test_one_empty(self):
        """片方空で 0.0 を返す。"""
        assert enrich.jaccard_coefficient({"a"}, set()) == 0.0


class TestMatchExcludesPluginSkills:
    """プラグイン由来スキルがマッチング対象から除外されるテスト。"""

    def test_plugin_skills_excluded(self, tmp_path):
        """classify_artifact_origin が plugin を返すスキルは除外される。"""
        # カスタムスキルの SKILL.md を作成
        custom_skill_dir = tmp_path / "custom-error-handler"
        custom_skill_dir.mkdir()
        skill_md = custom_skill_dir / "SKILL.md"
        skill_md.write_text("# Error Handler\nHandle errors gracefully")

        # プラグインスキルの SKILL.md を作成
        plugin_skill_dir = tmp_path / "plugin-error-tool"
        plugin_skill_dir.mkdir()
        plugin_skill_md = plugin_skill_dir / "SKILL.md"
        plugin_skill_md.write_text("# Plugin Error Tool\nPlugin error handling")

        artifacts = {
            "skills": [skill_md, plugin_skill_md],
            "rules": [],
        }

        patterns = [
            {"type": "error", "pattern": "error handler gracefully"},
        ]

        def mock_classify(path):
            if "plugin-error-tool" in str(path):
                return "plugin"
            return "custom"

        with mock.patch("enrich.classify_artifact_origin", side_effect=mock_classify):
            matches = enrich.match_patterns_to_skills(patterns, artifacts)

        # プラグインスキルはマッチに含まれない
        matched_skills = [m["matched_skill"] for m in matches]
        assert "plugin-error-tool" not in matched_skills
        # カスタムスキルはマッチする可能性がある
        for m in matches:
            assert m["matched_skill"] != "plugin-error-tool"


class TestBehaviorFallback:
    """error/rejection が空の場合に behavior にフォールバックするテスト。"""

    def test_behavior_fallback_when_errors_empty(self, tmp_path):
        """error_patterns と rejection_patterns が空なら behavior_patterns を使用。"""
        # スキルを作成
        skill_dir = tmp_path / ".claude" / "skills" / "git-commit-helper"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Git Commit Helper\nAutomate git commit messages")

        discover_result = {
            "error_patterns": [],
            "rejection_patterns": [],
            "behavior_patterns": [
                {"type": "behavior", "pattern": "git commit helper", "suggestion": "skill_candidate"},
            ],
        }

        with mock.patch("enrich.find_artifacts") as mock_find:
            mock_find.return_value = {
                "skills": [skill_dir / "SKILL.md"],
                "rules": [],
                "memory": [],
                "claude_md": [],
            }
            with mock.patch("enrich.classify_artifact_origin", return_value="custom"):
                result = enrich.run_enrich(discover_result, str(tmp_path))

        # behavior パターンが使用され、skipped ではない
        assert "skipped_reason" not in result
        # enrichments または unmatched_patterns に behavior パターンが含まれる
        all_patterns = [e["pattern"] for e in result["enrichments"]] + [
            u["pattern"] for u in result["unmatched_patterns"]
        ]
        assert "git commit helper" in all_patterns


class TestAllPatternsEmptyReturnsSkipped:
    """全パターンが空の場合に skipped_reason を返すテスト。"""

    def test_all_patterns_empty_returns_skipped(self):
        """全パターンが空の場合、skipped_reason: no_patterns_available を返す。"""
        discover_result = {
            "error_patterns": [],
            "rejection_patterns": [],
            "behavior_patterns": [],
        }

        result = enrich.run_enrich(discover_result, "/tmp/dummy")

        assert result["skipped_reason"] == "no_patterns_available"
        assert result["enrichments"] == []
        assert result["unmatched_patterns"] == []
        assert result["total_enrichments"] == 0
        assert result["total_unmatched"] == 0


class TestMax3Matches:
    """パターンあたり最大 3 件のマッチ制限テスト。"""

    def test_max_3_matches(self, tmp_path):
        """1パターンに対してマッチは最大 3 件まで。"""
        # 5 つのスキルを作成（全て共通キーワードを含む）
        skill_paths = []
        for i in range(5):
            skill_dir = tmp_path / f"skill-test-{i}"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            # 全スキルに共通トークンを含める
            skill_md.write_text(f"# Test Skill {i}\ntest common keyword match alpha")
            skill_paths.append(skill_md)

        artifacts = {
            "skills": skill_paths,
            "rules": [],
        }

        patterns = [
            {"type": "error", "pattern": "test common keyword match alpha"},
        ]

        with mock.patch("enrich.classify_artifact_origin", return_value="custom"):
            matches = enrich.match_patterns_to_skills(patterns, artifacts, max_matches=3)

        # 1パターンに対して最大 3 件
        assert len(matches) <= 3


class TestUnmatchedPatternsTracked:
    """マッチしないパターンが unmatched_patterns に記録されるテスト。"""

    def test_unmatched_patterns_tracked(self, tmp_path):
        """Jaccard < 0.15 のパターンは unmatched_patterns に含まれる。"""
        # 全く関連のないスキルを作成
        skill_dir = tmp_path / ".claude" / "skills" / "database-migration"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Database Migration\nSchema versioning and rollback")

        discover_result = {
            "error_patterns": [
                {"type": "error", "pattern": "zzzzunique_xyz_pattern_nomatch_999", "suggestion": "rule_candidate"},
            ],
            "rejection_patterns": [],
            "behavior_patterns": [],
        }

        with mock.patch("enrich.find_artifacts") as mock_find:
            mock_find.return_value = {
                "skills": [skill_dir / "SKILL.md"],
                "rules": [],
                "memory": [],
                "claude_md": [],
            }
            with mock.patch("enrich.classify_artifact_origin", return_value="custom"):
                result = enrich.run_enrich(discover_result, str(tmp_path))

        # マッチしないパターンは unmatched に入る
        assert result["total_unmatched"] >= 1
        unmatched_texts = [u["pattern"] for u in result["unmatched_patterns"]]
        assert "zzzzunique_xyz_pattern_nomatch_999" in unmatched_texts

        # unmatched の各エントリに必要なキーがある
        for u in result["unmatched_patterns"]:
            assert "pattern_type" in u
            assert "pattern" in u
            assert "suggestion" in u
