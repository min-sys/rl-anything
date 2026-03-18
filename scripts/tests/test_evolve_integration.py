#!/usr/bin/env python3
"""assess_single_skill + apply_evolve_proposal + _try_evolve_skill の統合テスト。"""
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

_lib_dir = Path(__file__).resolve().parent.parent.parent / "scripts" / "lib"
sys.path.insert(0, str(_lib_dir))

_rl_loop_script = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "rl-loop-orchestrator" / "scripts" / "run-loop.py"
)


def _import_run_loop():
    """run-loop.py をモジュールとしてインポートする（ハイフン含みファイル名対策）。"""
    spec = importlib.util.spec_from_file_location("run_loop", _rl_loop_script)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_loop"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_skill_dir(tmp_path, evolved=False):
    """テスト用スキルディレクトリを作成する。"""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Test Skill\n\nContent here.\n")
    if evolved:
        refs = skill_dir / "references"
        refs.mkdir()
        (refs / "pitfalls.md").write_text("# Pitfalls\n")
        (skill_dir / "SKILL.md").write_text(
            "# Test Skill\n\n## Failure-triggered Learning\n\ncontent\n"
        )
    return skill_dir


# --- assess_single_skill + apply_evolve_proposal 統合 ---


@mock.patch("skill_evolve.compute_llm_scores")
@mock.patch("skill_evolve.compute_telemetry_scores")
def test_assess_then_apply(mock_telemetry, mock_llm, tmp_path):
    """適性判定 → 提案生成 → 適用の一連フロー。"""
    from skill_evolve import assess_single_skill, evolve_skill_proposal, apply_evolve_proposal

    skill_dir = _make_skill_dir(tmp_path)

    mock_telemetry.return_value = {
        "frequency": 3, "diversity": 3, "evaluability": 3,
        "usage_count": 20, "error_count": 8,
        "error_categories": ["a", "b", "c", "d"],
    }
    mock_llm.return_value = {
        "external_dependency": 2, "judgment_complexity": 3, "cached": True,
    }

    assessment = assess_single_skill("test-skill", skill_dir)
    assert assessment["suitability"] in ("high", "medium")

    with mock.patch("skill_evolve._customize_template") as mock_custom:
        mock_custom.return_value = (
            "## Pre-flight Check\n\nCheck pitfalls.\n\n"
            "## Failure-triggered Learning\n\n| Trigger | Action |\n"
        )
        with mock.patch("skill_evolve._plugin_root", tmp_path):
            # テンプレートを配置
            templates_dir = tmp_path / "skills" / "evolve" / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "self-evolve-sections.md").write_text(
                "## Pre-flight Check\n## Failure-triggered Learning\n"
            )
            (templates_dir / "pitfalls.md").write_text(
                "## Active Pitfalls\n## Graduated Pitfalls\n"
            )
            proposal = evolve_skill_proposal("test-skill", skill_dir)

    assert proposal["error"] is None
    result = apply_evolve_proposal(proposal)
    assert result["applied"] is True

    # SKILL.md が更新されている
    updated = (skill_dir / "SKILL.md").read_text()
    assert "Pre-flight Check" in updated
    assert "Failure-triggered Learning" in updated

    # pitfalls.md が作成されている
    assert (skill_dir / "references" / "pitfalls.md").exists()

    # バックアップが存在する
    backup = skill_dir / "SKILL.md.pre-evolve-backup"
    assert backup.exists()


# --- _try_evolve_skill テスト ---


@pytest.fixture
def run_loop_mod():
    """run-loop.py をモジュールとしてロードする fixture。"""
    return _import_run_loop()


def test_try_evolve_already_evolved(run_loop_mod, tmp_path):
    """既に自己進化済みスキルはスキップされる。"""
    skill_dir = _make_skill_dir(tmp_path, evolved=True)
    target = str(skill_dir / "SKILL.md")

    with mock.patch.object(run_loop_mod, "assess_single_skill") as mock_assess:
        mock_assess.return_value = {
            "suitability": "already_evolved",
            "already_evolved": True,
        }
        result = run_loop_mod._try_evolve_skill(target, dry_run=True)

    assert result["evolve_suitability"] == "already_evolved"
    assert result["evolve_applied"] is False


def test_try_evolve_low_suitability(run_loop_mod, tmp_path):
    """低適性スキルはスキップされる。"""
    skill_dir = _make_skill_dir(tmp_path)
    target = str(skill_dir / "SKILL.md")

    with mock.patch.object(run_loop_mod, "assess_single_skill") as mock_assess:
        mock_assess.return_value = {
            "suitability": "low",
            "already_evolved": False,
            "scores": {"frequency": 1, "diversity": 1, "evaluability": 1,
                       "external_dependency": 1, "judgment_complexity": 1, "error_count": 0},
            "recommendation": "変換非推奨",
        }
        result = run_loop_mod._try_evolve_skill(target, dry_run=True)

    assert result["evolve_suitability"] == "low"
    assert result["evolve_applied"] is False


def test_try_evolve_dry_run_no_apply(run_loop_mod, tmp_path):
    """--dry-run 時は適用しない。"""
    skill_dir = _make_skill_dir(tmp_path)
    target = str(skill_dir / "SKILL.md")

    with mock.patch.object(run_loop_mod, "assess_single_skill") as mock_assess, \
         mock.patch.object(run_loop_mod, "evolve_skill_proposal") as mock_proposal, \
         mock.patch.object(run_loop_mod, "apply_evolve_proposal") as mock_apply:
        mock_assess.return_value = {
            "suitability": "high",
            "already_evolved": False,
            "scores": {"frequency": 3, "diversity": 3, "evaluability": 3,
                       "external_dependency": 2, "judgment_complexity": 3, "error_count": 8},
            "recommendation": "変換を推奨",
        }
        result = run_loop_mod._try_evolve_skill(target, dry_run=True)

    assert result["evolve_suitability"] == "high"
    assert result["evolve_applied"] is False
    mock_proposal.assert_not_called()
    mock_apply.assert_not_called()


def test_try_evolve_auto_applies(run_loop_mod, tmp_path):
    """--auto 時は自動承認で適用する。"""
    skill_dir = _make_skill_dir(tmp_path)
    target = str(skill_dir / "SKILL.md")

    with mock.patch.object(run_loop_mod, "assess_single_skill") as mock_assess, \
         mock.patch.object(run_loop_mod, "evolve_skill_proposal") as mock_proposal, \
         mock.patch.object(run_loop_mod, "apply_evolve_proposal") as mock_apply:
        mock_assess.return_value = {
            "suitability": "high",
            "already_evolved": False,
            "scores": {"frequency": 3, "diversity": 3, "evaluability": 3,
                       "external_dependency": 2, "judgment_complexity": 3, "error_count": 8},
            "recommendation": "変換を推奨",
        }
        mock_proposal.return_value = {
            "skill_name": "test-skill",
            "sections_to_add": "## Pre-flight\n",
            "pitfalls_template": "## Active\n",
            "skill_md_path": target,
            "pitfalls_path": str(skill_dir / "references" / "pitfalls.md"),
            "error": None,
        }
        mock_apply.return_value = {
            "applied": True,
            "backup_path": str(skill_dir / "SKILL.md.pre-evolve-backup"),
            "error": None,
        }
        result = run_loop_mod._try_evolve_skill(target, auto=True)

    assert result["evolve_suitability"] == "high"
    assert result["evolve_applied"] is True
    mock_apply.assert_called_once()


# --- run_loop --evolve フラグテスト ---


def test_run_loop_evolve_flag_calls_try_evolve(run_loop_mod, tmp_path):
    """--evolve フラグ有効時に _try_evolve_skill が呼ばれる。"""
    skill_dir = _make_skill_dir(tmp_path)
    target = str(skill_dir / "SKILL.md")

    with mock.patch.object(run_loop_mod, "get_baseline_score") as mock_baseline, \
         mock.patch.object(run_loop_mod, "generate_variants") as mock_variants, \
         mock.patch.object(run_loop_mod, "score_variant") as mock_score, \
         mock.patch.object(run_loop_mod, "_try_evolve_skill") as mock_try_evolve:
        mock_baseline.return_value = {"integrated_score": 0.65}
        mock_variants.return_value = {
            "history": [{"individuals": [{"id": "v1", "content": "# Improved\n"}]}],
        }
        mock_score.return_value = 0.70
        mock_try_evolve.return_value = {
            "evolve_suitability": "high",
            "evolve_applied": True,
            "evolve_scores": {},
        }

        results = run_loop_mod.run_loop(
            target_path=target,
            loops=1, auto=True, dry_run=False,
            output_dir=str(tmp_path / "out"),
            evolve=True,
        )

    assert len(results) == 1
    assert results[0]["evolve_suitability"] == "high"
    assert results[0]["evolve_applied"] is True
    mock_try_evolve.assert_called_once()


def test_run_loop_no_evolve_flag(run_loop_mod, tmp_path):
    """--evolve フラグなしでは _try_evolve_skill は呼ばれない。"""
    skill_dir = _make_skill_dir(tmp_path)
    target = str(skill_dir / "SKILL.md")

    with mock.patch.object(run_loop_mod, "get_baseline_score") as mock_baseline, \
         mock.patch.object(run_loop_mod, "generate_variants") as mock_variants, \
         mock.patch.object(run_loop_mod, "score_variant") as mock_score, \
         mock.patch.object(run_loop_mod, "_try_evolve_skill") as mock_try_evolve:
        mock_baseline.return_value = {"integrated_score": 0.65}
        mock_variants.return_value = {
            "history": [{"individuals": [{"id": "v1", "content": "# Improved\n"}]}],
        }
        mock_score.return_value = 0.70

        results = run_loop_mod.run_loop(
            target_path=target,
            loops=1, auto=True, dry_run=True,
            output_dir=str(tmp_path / "out"),
            evolve=False,
        )

    assert len(results) == 1
    assert "evolve_suitability" not in results[0]
    mock_try_evolve.assert_not_called()
