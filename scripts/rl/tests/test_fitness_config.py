#!/usr/bin/env python3
"""fitness config.py と environment.py 動的重み計算のテスト (TDD First)。"""
import importlib
import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest

_test_dir = Path(__file__).resolve().parent
_rl_dir = _test_dir.parent
_plugin_root = _rl_dir.parent.parent
_fitness_dir = _rl_dir / "fitness"

sys.path.insert(0, str(_rl_dir))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))


def _load_environment():
    """environment.py をモジュールとしてロードする。"""
    env_path = _fitness_dir / "environment.py"
    spec = importlib.util.spec_from_file_location("environment", env_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_config():
    """config.py をモジュールとしてロードする。"""
    cfg_path = _fitness_dir / "config.py"
    spec = importlib.util.spec_from_file_location("fitness_config", cfg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFitnessConfigImport:
    def test_fitness_config_import(self):
        """config.py から正しく各閾値が読み込める。"""
        config = _load_config()
        assert hasattr(config, "COHERENCE_THRESHOLDS")
        assert hasattr(config, "TELEMETRY_THRESHOLDS")
        assert hasattr(config, "CONSTITUTIONAL_THRESHOLDS")
        assert hasattr(config, "CHAOS_THRESHOLDS")
        assert hasattr(config, "PRINCIPLES_THRESHOLDS")
        assert hasattr(config, "BASE_WEIGHTS")

        # BASE_WEIGHTS の合計は 1.0
        total = sum(config.BASE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_fitness_config_values_match_existing(self):
        """config.py の値が既存モジュールの THRESHOLDS と一致する。"""
        config = _load_config()
        assert config.COHERENCE_THRESHOLDS["skill_min_lines"] == 50
        assert config.TELEMETRY_THRESHOLDS["min_sessions"] == 30
        assert config.CONSTITUTIONAL_THRESHOLDS["min_coverage_for_eval"] == 0.5
        assert config.CHAOS_THRESHOLDS["critical_delta"] == 0.10
        assert config.PRINCIPLES_THRESHOLDS["min_principle_quality"] == 0.3


class TestNormalizeWeights:
    def test_normalize_weights_3layer(self):
        """coherence + telemetry + constitutional -> sum=1.0"""
        env = _load_environment()
        result = env._normalize_weights(["coherence", "telemetry", "constitutional"])
        assert abs(sum(result.values()) - 1.0) < 0.0001
        assert len(result) == 3
        assert "coherence" in result
        assert "telemetry" in result
        assert "constitutional" in result

    def test_normalize_weights_1layer(self):
        """coherence のみ -> {"coherence": 1.0}"""
        env = _load_environment()
        result = env._normalize_weights(["coherence"])
        assert result == {"coherence": 1.0}

    def test_normalize_weights_empty(self):
        """軸なし -> {}"""
        env = _load_environment()
        result = env._normalize_weights([])
        assert result == {}

    def test_normalize_weights_4layer(self):
        """全4軸 -> sum=1.0, skill_quality が含まれる。"""
        env = _load_environment()
        result = env._normalize_weights(
            ["coherence", "telemetry", "constitutional", "skill_quality"]
        )
        assert abs(sum(result.values()) - 1.0) < 0.0001
        assert len(result) == 4
        assert "skill_quality" in result
        # skill_quality の比率確認
        config = _load_config()
        total_base = sum(config.BASE_WEIGHTS.values())
        expected_sq = config.BASE_WEIGHTS["skill_quality"] / total_base
        assert abs(result["skill_quality"] - expected_sq) < 0.0001

    def test_normalize_weights_unknown_axis_ignored(self):
        """存在しない軸は無視される。"""
        env = _load_environment()
        result = env._normalize_weights(["coherence", "nonexistent"])
        assert result == {"coherence": 1.0}


class TestEnvironment3LayerBackwardCompat:
    """CRITICAL REGRESSION: 既存3層重みと動的計算がほぼ同じスコアを返すことを保証。"""

    def _mock_load_sibling(self, coherence_result, telemetry_result, constitutional_result):
        def loader(name):
            m = mock.MagicMock()
            if name == "coherence":
                m.compute_coherence_score.return_value = coherence_result
            elif name == "telemetry":
                m.compute_telemetry_score.return_value = telemetry_result
            elif name == "constitutional":
                m.compute_constitutional_score.return_value = constitutional_result
            elif name == "skill_quality":
                # skill_quality が利用不可のケースをシミュレート
                raise ImportError("not available")
            return m
        return loader

    def test_environment_3layer_backward_compat(self, tmp_path):
        """既存3層重み(0.25/0.45/0.30)と動的計算が ±0.02 以内。"""
        env = _load_environment()

        # プロジェクト構成
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "CLAUDE.md").write_text("# Project\n\n## Skills\n\n- s: d\n")

        coh = {"overall": 0.8, "coverage": 0.8}
        tel = {"overall": 0.7, "data_sufficiency": True}
        con = {"overall": 0.9, "skip_reason": None}

        loader = self._mock_load_sibling(coh, tel, con)
        with mock.patch.object(env, "_load_sibling", side_effect=loader):
            result = env.compute_environment_fitness(tmp_path, days=30)

        # 旧来の3層重み計算
        old_score = 0.8 * 0.25 + 0.7 * 0.45 + 0.9 * 0.30
        assert abs(result["overall"] - old_score) < 0.02, (
            f"Dynamic score {result['overall']} differs from legacy {old_score} by more than 0.02"
        )


class TestFitnessConfigFallback:
    def test_fitness_config_fallback(self):
        """config.py が壊れても各モジュールがフォールバック値で動作する。

        coherence.py が THRESHOLDS を保持していることを確認。
        """
        # coherence.py を直接ロードし、THRESHOLDS が存在することを確認
        coh_path = _fitness_dir / "coherence.py"
        spec = importlib.util.spec_from_file_location("coherence_test", coh_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "THRESHOLDS")
        assert mod.THRESHOLDS["skill_min_lines"] == 50
