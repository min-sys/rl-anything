"""prune の decay 計算、pin 保護、corrections 減点のユニットテスト。"""
import json
import math
import sys
from pathlib import Path
from unittest import mock

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import prune


class TestComputeDecayScore:
    """compute_decay_score() のテスト。"""

    def test_recent_no_corrections(self):
        """5日前使用、corrections なし → ≈ 0.946"""
        score = prune.compute_decay_score(age_days=5, correction_count=0)
        expected = 1.0 * math.exp(-5 / 90)
        assert abs(score - expected) < 0.001

    def test_long_unused_no_corrections(self):
        """180日前使用、corrections なし → ≈ 0.135"""
        score = prune.compute_decay_score(age_days=180, correction_count=0)
        expected = 1.0 * math.exp(-180 / 90)
        assert abs(score - expected) < 0.001

    def test_with_corrections(self):
        """10日前使用、correction 2件 → base_score 0.7"""
        score = prune.compute_decay_score(age_days=10, correction_count=2)
        expected = 0.7 * math.exp(-10 / 90)
        assert abs(score - expected) < 0.001

    def test_many_corrections_floor(self):
        """correction が多すぎても base_score は 0.0 で下限"""
        score = prune.compute_decay_score(age_days=0, correction_count=100)
        assert score == 0.0

    def test_zero_days(self):
        """0日 → base_score そのまま"""
        score = prune.compute_decay_score(age_days=0, correction_count=0)
        assert score == 1.0

    def test_custom_decay_days(self):
        """decay_days をカスタム設定"""
        score = prune.compute_decay_score(age_days=30, correction_count=0, decay_days=30)
        expected = math.exp(-1)
        assert abs(score - expected) < 0.001


class TestIsPinned:
    """is_pinned() のテスト。"""

    def test_pinned_skill(self, tmp_path):
        """pin ファイルが存在する場合 True"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / ".pin").touch()
        skill_file = skill_dir / "skill.md"
        skill_file.touch()
        assert prune.is_pinned(skill_file) is True

    def test_not_pinned(self, tmp_path):
        """pin ファイルがない場合 False"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "skill.md"
        skill_file.touch()
        assert prune.is_pinned(skill_file) is False


class TestLoadCorrections:
    """load_corrections() のテスト。"""

    def test_loads_and_groups(self, tmp_path):
        corrections_file = tmp_path / "corrections.jsonl"
        records = [
            {"last_skill": "evolve", "correction_type": "iya"},
            {"last_skill": "evolve", "correction_type": "chigau"},
            {"last_skill": "commit", "correction_type": "no"},
            {"last_skill": None, "correction_type": "stop"},
        ]
        corrections_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )
        with mock.patch.object(prune, "DATA_DIR", tmp_path):
            result = prune.load_corrections()
        assert len(result["evolve"]) == 2
        assert len(result["commit"]) == 1
        # last_skill が null のレコードはグループ化されない
        assert None not in result

    def test_missing_file(self, tmp_path):
        with mock.patch.object(prune, "DATA_DIR", tmp_path):
            result = prune.load_corrections()
        assert result == {}


class TestLoadDecayThreshold:
    """load_decay_threshold() のテスト。"""

    def test_default(self, tmp_path):
        with mock.patch.object(prune, "DATA_DIR", tmp_path):
            assert prune.load_decay_threshold() == 0.2

    def test_custom(self, tmp_path):
        state_file = tmp_path / "evolve-state.json"
        state_file.write_text(json.dumps({"decay_threshold": 0.3}))
        with mock.patch.object(prune, "DATA_DIR", tmp_path):
            assert prune.load_decay_threshold() == 0.3
