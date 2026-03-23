#!/usr/bin/env python3
"""_compute_env_tier() のユニットテスト (TDD First)。"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "evolve" / "scripts"))

_evolve_path = _plugin_root / "skills" / "evolve" / "scripts" / "evolve.py"
_spec = importlib.util.spec_from_file_location("evolve", _evolve_path)
evolve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evolve)


def _setup_project(tmp_path, n_skill_dirs=0, n_rules=0, skills_in_claudemd=0):
    """テスト用プロジェクトを構成する。

    Args:
        n_skill_dirs: .claude/skills/ 配下のディレクトリ数
        n_rules: .claude/rules/ 配下のファイル数
        skills_in_claudemd: CLAUDE.md の Skills セクションに記載するスキル数
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    # Skills directories
    skills_dir = claude_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n_skill_dirs):
        d = skills_dir / f"skill-{i}"
        d.mkdir()
        (d / "SKILL.md").write_text(f"# Skill {i}\n")

    # Rules files
    rules_dir = claude_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n_rules):
        (rules_dir / f"rule-{i}.md").write_text(f"# Rule {i}\n")

    # CLAUDE.md with Skills section
    lines = ["# Project\n"]
    if skills_in_claudemd > 0:
        lines.append("## Skills\n")
        for i in range(skills_in_claudemd):
            lines.append(f"- claudemd-skill-{i}: description\n")
    (tmp_path / "CLAUDE.md").write_text("\n".join(lines))

    return tmp_path


class TestComputeEnvTier:
    def test_compute_env_tier_small(self, tmp_path):
        """19 artifacts -> 'small'"""
        # 10 skill dirs + 5 skills in CLAUDE.md + 4 rules = 19
        project = _setup_project(tmp_path, n_skill_dirs=10, n_rules=4, skills_in_claudemd=5)
        assert evolve._compute_env_tier(project) == "small"

    def test_compute_env_tier_medium(self, tmp_path):
        """20 artifacts -> 'medium'"""
        # 10 skill dirs + 5 skills in CLAUDE.md + 5 rules = 20
        project = _setup_project(tmp_path, n_skill_dirs=10, n_rules=5, skills_in_claudemd=5)
        assert evolve._compute_env_tier(project) == "medium"

    def test_compute_env_tier_large(self, tmp_path):
        """50 artifacts -> 'large'"""
        # 30 skill dirs + 10 skills in CLAUDE.md + 10 rules = 50
        project = _setup_project(tmp_path, n_skill_dirs=30, n_rules=10, skills_in_claudemd=10)
        assert evolve._compute_env_tier(project) == "large"

    def test_compute_env_tier_zero(self, tmp_path):
        """0 artifacts -> 'small'"""
        project = _setup_project(tmp_path, n_skill_dirs=0, n_rules=0, skills_in_claudemd=0)
        assert evolve._compute_env_tier(project) == "small"

    def test_compute_env_tier_no_claude_dir(self, tmp_path):
        """CLAUDE.md も .claude/ もないプロジェクト -> 'small'"""
        assert evolve._compute_env_tier(tmp_path) == "small"

    def test_compute_env_tier_boundary_49(self, tmp_path):
        """49 artifacts -> 'medium'"""
        project = _setup_project(tmp_path, n_skill_dirs=30, n_rules=10, skills_in_claudemd=9)
        assert evolve._compute_env_tier(project) == "medium"
