#!/usr/bin/env python3
"""discover に統合された enrich (Jaccard 照合) のテスト。"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

PLUGIN_ROOT = SCRIPTS_DIR.parent.parent.parent
if str(PLUGIN_ROOT / "scripts" / "lib") not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT / "scripts" / "lib"))

from discover import _enrich_patterns


@pytest.fixture
def skill_tree(tmp_path):
    """テスト用のスキルディレクトリ構造を作成する。"""
    # スキル1: git-commit
    skill1 = tmp_path / ".claude" / "skills" / "git-commit" / "SKILL.md"
    skill1.parent.mkdir(parents=True)
    skill1.write_text("# Git Commit\n\nCreate conventional commits.\n\n## Usage\nUse for git operations.\n")

    # スキル2: test-runner
    skill2 = tmp_path / ".claude" / "skills" / "test-runner" / "SKILL.md"
    skill2.parent.mkdir(parents=True)
    skill2.write_text("# Test Runner\n\nRun pytest test suite.\n\n## Usage\nUse for testing.\n")

    return tmp_path


class TestEnrichPatterns:
    """_enrich_patterns() のテスト。"""

    def test_matched_skills(self, skill_tree):
        """パターンが既存スキルにマッチする場合。"""
        patterns = [
            {"type": "behavior", "pattern": "git commit", "count": 10, "suggestion": "skill_candidate"},
        ]

        with patch("discover.Path.cwd", return_value=skill_tree):
            result = _enrich_patterns(patterns, project_dir=skill_tree)

        assert len(result["matched_skills"]) >= 1
        matched_names = [m["matched_skill"] for m in result["matched_skills"]]
        assert "git-commit" in matched_names

    def test_unmatched_patterns(self, skill_tree):
        """マッチしないパターンが unmatched_patterns に含まれる。"""
        patterns = [
            {"type": "error", "pattern": "zzzz_unique_nonexistent_pattern_xyz", "count": 5, "suggestion": "rule_candidate"},
        ]

        with patch("discover.Path.cwd", return_value=skill_tree):
            result = _enrich_patterns(patterns, project_dir=skill_tree)

        assert len(result["unmatched_patterns"]) == 1
        assert result["unmatched_patterns"][0]["pattern"] == "zzzz_unique_nonexistent_pattern_xyz"

    def test_empty_patterns(self, skill_tree):
        """空のパターンリストの場合。"""
        with patch("discover.Path.cwd", return_value=skill_tree):
            result = _enrich_patterns([], project_dir=skill_tree)

        assert result["matched_skills"] == []
        assert result["unmatched_patterns"] == []

    def test_output_structure(self, skill_tree):
        """出力に matched_skills と unmatched_patterns が含まれる。"""
        patterns = [
            {"type": "behavior", "pattern": "test runner", "count": 5, "suggestion": "skill_candidate"},
        ]

        with patch("discover.Path.cwd", return_value=skill_tree):
            result = _enrich_patterns(patterns, project_dir=skill_tree)

        assert "matched_skills" in result
        assert "unmatched_patterns" in result

        if result["matched_skills"]:
            match = result["matched_skills"][0]
            assert "pattern_type" in match
            assert "pattern" in match
            assert "matched_skill" in match
            assert "jaccard_score" in match
