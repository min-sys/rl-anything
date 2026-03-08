#!/usr/bin/env python3
"""principles.py のテスト"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

_test_dir = Path(__file__).resolve().parent
_rl_dir = _test_dir.parent
_plugin_root = _rl_dir.parent.parent
sys.path.insert(0, str(_rl_dir))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))

_principles_path = _rl_dir / "fitness" / "principles.py"
_spec = importlib.util.spec_from_file_location("principles", _principles_path)
principles = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(principles)


def _make_project(tmp_path):
    """テスト用プロジェクトを作成する。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "CLAUDE.md").write_text("# Project\n\n## Skills\n\n- sample-skill: A sample\n")

    rules_dir = claude_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "sample.md").write_text("# Rule\nDo this.\n")

    return tmp_path


def _mock_llm_response(extracted_principles):
    """subprocess.run のモック戻り値を生成する。"""
    result = mock.MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(extracted_principles)
    return result


class TestCacheRoundtrip:
    def test_save_and_load(self, tmp_path):
        project = _make_project(tmp_path)
        data = {
            "principles": list(principles.SEED_PRINCIPLES),
            "excluded_low_quality": [],
            "source_hash": "abc123",
        }
        principles._save_cache(project, data)
        loaded = principles._load_cache(project)
        assert loaded is not None
        assert loaded["principles"] == data["principles"]
        assert loaded["source_hash"] == "abc123"

    def test_load_nonexistent_returns_none(self, tmp_path):
        project = _make_project(tmp_path)
        assert principles._load_cache(project) is None


class TestStalenessDetection:
    def test_hash_mismatch_marks_stale(self, tmp_path):
        project = _make_project(tmp_path)
        # キャッシュを保存（異なるハッシュ値で）
        data = {
            "principles": list(principles.SEED_PRINCIPLES),
            "excluded_low_quality": [],
            "source_hash": "old_hash_value",
        }
        principles._save_cache(project, data)

        result = principles.extract_principles(project, refresh=False)
        assert result["from_cache"] is True
        assert result["stale_cache"] is True

    def test_hash_match_not_stale(self, tmp_path):
        project = _make_project(tmp_path)
        current_hash = principles._compute_source_hash(project)
        data = {
            "principles": list(principles.SEED_PRINCIPLES),
            "excluded_low_quality": [],
            "source_hash": current_hash,
        }
        principles._save_cache(project, data)

        result = principles.extract_principles(project, refresh=False)
        assert result["from_cache"] is True
        assert result["stale_cache"] is False


class TestSeedPrinciples:
    def test_seeds_always_present(self, tmp_path):
        project = _make_project(tmp_path)
        llm_output = [
            {
                "id": "custom-rule",
                "text": "Custom rule",
                "source": "CLAUDE.md",
                "category": "quality",
                "specificity": 0.8,
                "testability": 0.8,
            }
        ]
        with mock.patch.object(
            principles, "_extract_via_llm", return_value=llm_output
        ):
            result = principles.extract_principles(project, refresh=True)

        ids = {p["id"] for p in result["principles"]}
        for seed in principles.SEED_PRINCIPLES:
            assert seed["id"] in ids, f"Seed principle {seed['id']} missing"


class TestUserDefinedPreservation:
    def test_user_defined_preserved_on_refresh(self, tmp_path):
        project = _make_project(tmp_path)
        # user_defined 原則を含むキャッシュを作成
        cached = {
            "principles": list(principles.SEED_PRINCIPLES) + [
                {
                    "id": "my-custom-principle",
                    "text": "My custom principle",
                    "source": "user",
                    "category": "convention",
                    "specificity": 0.9,
                    "testability": 0.9,
                    "user_defined": True,
                }
            ],
            "excluded_low_quality": [],
            "source_hash": "old_hash",
        }
        principles._save_cache(project, cached)

        llm_output = [
            {
                "id": "new-principle",
                "text": "New from LLM",
                "source": "CLAUDE.md",
                "category": "quality",
                "specificity": 0.7,
                "testability": 0.7,
            }
        ]
        with mock.patch.object(
            principles, "_extract_via_llm", return_value=llm_output
        ):
            result = principles.extract_principles(project, refresh=True)

        ids = {p["id"] for p in result["principles"]}
        assert "my-custom-principle" in ids


class TestQualityFiltering:
    def test_low_quality_excluded(self, tmp_path):
        project = _make_project(tmp_path)
        llm_output = [
            {
                "id": "low-quality",
                "text": "Vague rule",
                "source": "CLAUDE.md",
                "category": "quality",
                "specificity": 0.1,
                "testability": 0.1,
            },
            {
                "id": "high-quality",
                "text": "Specific rule",
                "source": "CLAUDE.md",
                "category": "quality",
                "specificity": 0.8,
                "testability": 0.8,
            },
        ]
        with mock.patch.object(
            principles, "_extract_via_llm", return_value=llm_output
        ):
            result = principles.extract_principles(project, refresh=True)

        passed_ids = {p["id"] for p in result["principles"]}
        excluded_ids = {p["id"] for p in result["excluded_low_quality"]}
        assert "low-quality" in excluded_ids
        assert "high-quality" in passed_ids

    def test_seeds_bypass_quality_check(self, tmp_path):
        """seed 原則は品質スコアに関係なく常に含まれる。"""
        # seed の品質スコアが閾値未満でも通過することを確認
        test_principles = [
            {
                "id": "test-seed",
                "text": "Test seed",
                "source": "seed",
                "category": "quality",
                "specificity": 0.0,
                "testability": 0.0,
                "seed": True,
            }
        ]
        passed, excluded = principles._filter_by_quality(test_principles)
        assert len(passed) == 1
        assert len(excluded) == 0
        assert passed[0]["id"] == "test-seed"


class TestLLMFailureFallback:
    def test_llm_failure_returns_seeds_only(self, tmp_path):
        project = _make_project(tmp_path)
        with mock.patch.object(
            principles, "_extract_via_llm", return_value=None
        ):
            result = principles.extract_principles(project, refresh=True)

        assert result["from_cache"] is False
        ids = {p["id"] for p in result["principles"]}
        seed_ids = {s["id"] for s in principles.SEED_PRINCIPLES}
        assert ids == seed_ids


class TestComputeSourceHash:
    def test_hash_changes_when_claudemd_changes(self, tmp_path):
        project = _make_project(tmp_path)
        hash1 = principles._compute_source_hash(project)

        # CLAUDE.md を変更
        (project / "CLAUDE.md").write_text("# Updated Project\n\nNew content.\n")
        hash2 = principles._compute_source_hash(project)

        assert hash1 != hash2

    def test_hash_changes_when_rules_change(self, tmp_path):
        project = _make_project(tmp_path)
        hash1 = principles._compute_source_hash(project)

        # ルールを追加
        rules_dir = project / ".claude" / "rules"
        (rules_dir / "new-rule.md").write_text("# New Rule\nDo something else.\n")
        hash2 = principles._compute_source_hash(project)

        assert hash1 != hash2

    def test_hash_stable_for_same_content(self, tmp_path):
        project = _make_project(tmp_path)
        hash1 = principles._compute_source_hash(project)
        hash2 = principles._compute_source_hash(project)
        assert hash1 == hash2
