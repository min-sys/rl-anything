#!/usr/bin/env python3
"""constitutional.py のテスト"""

import importlib.util
import json
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

_constitutional_path = _rl_dir / "fitness" / "constitutional.py"
_spec = importlib.util.spec_from_file_location("constitutional", _constitutional_path)
constitutional = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(constitutional)


def _make_project(tmp_path):
    """テスト用プロジェクトを作成する。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "CLAUDE.md").write_text("# Project\n\n## Skills\n\n- sample-skill: A sample\n")

    rules_dir = claude_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "sample.md").write_text("# Rule\nDo this.\n")

    skill_dir = claude_dir / "skills" / "sample-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Sample Skill\n\n## Usage\n\nUse it.\n")

    mem_dir = claude_dir / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "MEMORY.md").write_text("# Memory\n\n## Notes\n\nSome notes.\n")

    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": ["echo test"]}]}}
    (claude_dir / "settings.json").write_text(json.dumps(settings))

    return tmp_path


_TEST_PRINCIPLES = [
    {
        "id": "single-responsibility",
        "text": "各スキル/ルールは単一の責務を持つ",
        "source": "seed",
        "category": "quality",
        "specificity": 0.7,
        "testability": 0.8,
        "seed": True,
    },
    {
        "id": "user-consent",
        "text": "破壊的操作の前にユーザー確認を取る",
        "source": "seed",
        "category": "safety",
        "specificity": 0.8,
        "testability": 0.9,
        "seed": True,
    },
]


def _make_llm_eval_response(principle_ids, score=0.8):
    """LLM 評価レスポンスのモック戻り値を生成する。"""
    evaluations = [
        {
            "principle_id": pid,
            "score": score,
            "rationale": "Compliant",
            "violations": [],
        }
        for pid in principle_ids
    ]
    result = mock.MagicMock()
    result.returncode = 0
    result.stdout = json.dumps({"evaluations": evaluations})
    return result


def _mock_coherence_low_coverage(project_dir):
    """coverage < 0.5 を返すモック。"""
    return {"overall": 0.3, "coverage": 0.3}


def _mock_coherence_sufficient(project_dir):
    """coverage >= 0.5 を返すモック。"""
    return {"overall": 0.8, "coverage": 0.8}


def _mock_principles_result(project_dir):
    """テスト用の原則リストを返すモック。"""
    return {
        "principles": list(_TEST_PRINCIPLES),
        "excluded_low_quality": [],
        "source_hash": "test_hash",
        "stale_cache": False,
        "from_cache": False,
    }


def _mock_find_artifacts(project_dir):
    """テスト用アーティファクトを返すモック。"""
    claude_dir = project_dir / ".claude"
    result = {
        "claude_md": [project_dir / "CLAUDE.md"],
        "rules": list((claude_dir / "rules").glob("*.md")) if (claude_dir / "rules").exists() else [],
        "skills": list(claude_dir.rglob("SKILL.md")) if (claude_dir / "skills").exists() else [],
        "memory": list((claude_dir / "memory").glob("*.md")) if (claude_dir / "memory").exists() else [],
    }
    return result


class TestCoverageGate:
    def test_low_coverage_returns_skip(self, tmp_path):
        """coverage < 0.5 の場合、skip_reason 付きで None overall を返す。"""
        project = _make_project(tmp_path)

        mock_coherence = mock.MagicMock()
        mock_coherence.compute_coherence_score = _mock_coherence_low_coverage

        with mock.patch.object(constitutional, "_load_sibling") as mock_load:
            mock_load.return_value = mock_coherence
            result = constitutional.compute_constitutional_score(project)

        assert result is not None
        assert result["overall"] is None
        assert result["skip_reason"] == "low_coverage"
        assert result["coverage_value"] < 0.5

    def test_sufficient_coverage_proceeds(self, tmp_path):
        """coverage >= 0.5 の場合、評価を実行する。"""
        project = _make_project(tmp_path)
        pids = [p["id"] for p in _TEST_PRINCIPLES]

        def mock_load_sibling(name):
            if name == "coherence":
                m = mock.MagicMock()
                m.compute_coherence_score = _mock_coherence_sufficient
                m._find_artifacts_local = _mock_find_artifacts
                return m
            if name == "principles":
                m = mock.MagicMock()
                m.extract_principles = _mock_principles_result
                return m
            raise ValueError(f"Unexpected sibling: {name}")

        with mock.patch.object(constitutional, "_load_sibling", side_effect=mock_load_sibling), \
             mock.patch("subprocess.run", return_value=_make_llm_eval_response(pids, 0.8)):
            result = constitutional.compute_constitutional_score(project, refresh=True)

        assert result is not None
        assert result["overall"] is not None
        assert 0.0 <= result["overall"] <= 1.0


class TestAllLayersFail:
    def test_all_layers_fail_returns_none(self, tmp_path):
        """全レイヤーの LLM 評価が失敗した場合、None を返す。"""
        project = _make_project(tmp_path)

        def mock_load_sibling(name):
            if name == "coherence":
                m = mock.MagicMock()
                m.compute_coherence_score = _mock_coherence_sufficient
                m._find_artifacts_local = _mock_find_artifacts
                return m
            if name == "principles":
                m = mock.MagicMock()
                m.extract_principles = _mock_principles_result
                return m
            raise ValueError(f"Unexpected sibling: {name}")

        # subprocess.run がタイムアウトを起こす
        with mock.patch.object(constitutional, "_load_sibling", side_effect=mock_load_sibling), \
             mock.patch("subprocess.run", side_effect=Exception("LLM failure")):
            result = constitutional.compute_constitutional_score(project, refresh=True)

        assert result is None


class TestPartialLayerFailure:
    def test_partial_failure_uses_remaining(self, tmp_path):
        """一部レイヤーが失敗しても、残りのレイヤーからスコアを算出する。"""
        project = _make_project(tmp_path)
        pids = [p["id"] for p in _TEST_PRINCIPLES]

        call_count = [0]

        def mock_subprocess_run(*args, **kwargs):
            call_count[0] += 1
            # 最初のレイヤーは2回のリトライ(attempt loop)とも失敗させる
            if call_count[0] <= 2:
                raise Exception("LLM failure")
            return _make_llm_eval_response(pids, 0.7)

        def mock_load_sibling(name):
            if name == "coherence":
                m = mock.MagicMock()
                m.compute_coherence_score = _mock_coherence_sufficient
                m._find_artifacts_local = _mock_find_artifacts
                return m
            if name == "principles":
                m = mock.MagicMock()
                m.extract_principles = _mock_principles_result
                return m
            raise ValueError(f"Unexpected sibling: {name}")

        with mock.patch.object(constitutional, "_load_sibling", side_effect=mock_load_sibling), \
             mock.patch("subprocess.run", side_effect=mock_subprocess_run):
            result = constitutional.compute_constitutional_score(project, refresh=True)

        assert result is not None
        assert result["overall"] is not None
        assert result["evaluated_layers"] < result["total_layers"]


class TestScoreAggregation:
    def test_per_principle_is_mean_of_layer_scores(self, tmp_path):
        """per_principle は各レイヤースコアの平均。"""
        project = _make_project(tmp_path)
        pids = [p["id"] for p in _TEST_PRINCIPLES]

        def mock_load_sibling(name):
            if name == "coherence":
                m = mock.MagicMock()
                m.compute_coherence_score = _mock_coherence_sufficient
                m._find_artifacts_local = _mock_find_artifacts
                return m
            if name == "principles":
                m = mock.MagicMock()
                m.extract_principles = _mock_principles_result
                return m
            raise ValueError(f"Unexpected sibling: {name}")

        with mock.patch.object(constitutional, "_load_sibling", side_effect=mock_load_sibling), \
             mock.patch("subprocess.run", return_value=_make_llm_eval_response(pids, 0.6)):
            result = constitutional.compute_constitutional_score(project, refresh=True)

        assert result is not None
        for pp in result["per_principle"]:
            # 全レイヤーで同じスコア (0.6) なので平均も 0.6
            assert abs(pp["score"] - 0.6) < 0.01


class TestScoreClamp:
    def test_clamp_above_one(self):
        assert constitutional._clamp(1.5) == 1.0

    def test_clamp_below_zero(self):
        assert constitutional._clamp(-0.5) == 0.0

    def test_clamp_normal_value(self):
        assert constitutional._clamp(0.7) == 0.7


class TestCacheSaveLoad:
    def test_cache_saves_layer_hashes(self, tmp_path):
        """キャッシュにレイヤーハッシュが保存される。"""
        project = _make_project(tmp_path)
        pids = [p["id"] for p in _TEST_PRINCIPLES]

        def mock_load_sibling(name):
            if name == "coherence":
                m = mock.MagicMock()
                m.compute_coherence_score = _mock_coherence_sufficient
                m._find_artifacts_local = _mock_find_artifacts
                return m
            if name == "principles":
                m = mock.MagicMock()
                m.extract_principles = _mock_principles_result
                return m
            raise ValueError(f"Unexpected sibling: {name}")

        with mock.patch.object(constitutional, "_load_sibling", side_effect=mock_load_sibling), \
             mock.patch("subprocess.run", return_value=_make_llm_eval_response(pids, 0.8)):
            constitutional.compute_constitutional_score(project, refresh=True)

        cache = constitutional._load_cache(project)
        assert cache is not None
        assert "layer_hashes" in cache
        assert "layer_results" in cache


class TestCostTracking:
    def test_cost_fields_present(self, tmp_path):
        """estimated_cost_usd と llm_calls_count が結果に含まれる。"""
        project = _make_project(tmp_path)
        pids = [p["id"] for p in _TEST_PRINCIPLES]

        def mock_load_sibling(name):
            if name == "coherence":
                m = mock.MagicMock()
                m.compute_coherence_score = _mock_coherence_sufficient
                m._find_artifacts_local = _mock_find_artifacts
                return m
            if name == "principles":
                m = mock.MagicMock()
                m.extract_principles = _mock_principles_result
                return m
            raise ValueError(f"Unexpected sibling: {name}")

        with mock.patch.object(constitutional, "_load_sibling", side_effect=mock_load_sibling), \
             mock.patch("subprocess.run", return_value=_make_llm_eval_response(pids, 0.8)):
            result = constitutional.compute_constitutional_score(project, refresh=True)

        assert result is not None
        assert "estimated_cost_usd" in result
        assert "llm_calls_count" in result
        assert result["estimated_cost_usd"] >= 0
        assert result["llm_calls_count"] >= 0
