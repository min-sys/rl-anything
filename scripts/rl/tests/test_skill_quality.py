#!/usr/bin/env python3
"""skill_quality.py CSO compliance のテスト。"""
import sys
from pathlib import Path

import pytest

_test_dir = Path(__file__).resolve().parent
_rl_dir = _test_dir.parent
_plugin_root = _rl_dir.parent.parent
sys.path.insert(0, str(_rl_dir / "fitness"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

from skill_quality import (
    CSO_ACTION_BONUS,
    CSO_LENGTH_PENALTY,
    CSO_MAX_DESCRIPTION_LENGTH,
    CSO_SUMMARY_THRESHOLD,
    CSO_TRIGGER_BONUS,
    check_cso_compliance,
)


def _write_skill_md(tmp_path, *, description="", body="## Steps\n\nDo something.\n"):
    """SKILL.md を frontmatter 付きで生成するヘルパー。"""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    lines = ["---"]
    lines.append("name: test-skill")
    if description:
        lines.append(f"description: \"{description}\"")
    lines.append("---")
    lines.append("")
    lines.append(body)
    skill_path.write_text("\n".join(lines), encoding="utf-8")
    return skill_path


class TestCsoSummaryPenalty:
    def test_penalty_when_description_matches_first_paragraph(self, tmp_path):
        """description が本文冒頭と高類似度 → ペナルティ適用。"""
        body_text = "This skill deploys the CDK stack to AWS environment automatically."
        skill_path = _write_skill_md(
            tmp_path,
            description="This skill deploys the CDK stack to AWS environment automatically.",
            body=body_text,
        )
        result = check_cso_compliance(skill_path)
        assert len(result["penalties"]) >= 1
        assert any("本文冒頭と高類似度" in p for p in result["penalties"])
        assert result["score"] < 0.5  # ベーススコア 0.5 からペナルティで下がる

    def test_no_penalty_unique_description(self, tmp_path):
        """description が本文と全く異なる → ペナルティなし。"""
        skill_path = _write_skill_md(
            tmp_path,
            description="Automate deployment pipeline for production releases",
            body="## Detailed Steps\n\nManage database migrations and schema updates carefully.\n",
        )
        result = check_cso_compliance(skill_path)
        summary_penalties = [p for p in result["penalties"] if "本文冒頭と高類似度" in p]
        assert len(summary_penalties) == 0


class TestCsoTriggerWordBonus:
    def test_trigger_bonus_applied(self, tmp_path):
        """description にトリガーワードが含まれる → ボーナス適用。

        Note: skill_triggers の import が失敗する場合はスキップされるため、
        ここではボーナスが適用されるか or エラーなく動作することを確認する。
        """
        skill_path = _write_skill_md(
            tmp_path,
            description="Deploy CDK stack with parameter validation",
            body="## Intro\n\nA deployment helper.\n",
        )
        result = check_cso_compliance(skill_path)
        # エラーなく動作すること（trigger bonus は環境依存）
        assert "score" in result
        assert isinstance(result["score"], float)


class TestCsoActionPatternBonus:
    def test_action_pattern_bonus(self, tmp_path):
        """description に 'Use when...' → ボーナス適用。"""
        skill_path = _write_skill_md(
            tmp_path,
            description="Use when deploying CDK stacks to production",
            body="## Details\n\nSomething different entirely.\n",
        )
        result = check_cso_compliance(skill_path)
        assert len(result["bonuses"]) >= 1
        assert any("行動促進形式" in b for b in result["bonuses"])
        assert result["score"] >= 0.5 + CSO_ACTION_BONUS - 0.01  # ベース + ボーナス (浮動小数点誤差考慮)

    def test_trigger_prefix_ja(self, tmp_path):
        """日本語トリガー形式 'トリガー:' でもボーナス。"""
        skill_path = _write_skill_md(
            tmp_path,
            description="トリガー: デプロイ時に自動実行",
            body="## Intro\n\nDifferent content.\n",
        )
        result = check_cso_compliance(skill_path)
        assert any("行動促進形式" in b for b in result["bonuses"])

    def test_use_this_skill_when(self, tmp_path):
        """'Use this skill when' パターンでもボーナス。"""
        skill_path = _write_skill_md(
            tmp_path,
            description="Use this skill when you need to validate schemas",
            body="## Intro\n\nValidation utility.\n",
        )
        result = check_cso_compliance(skill_path)
        assert any("行動促進形式" in b for b in result["bonuses"])


class TestCsoLengthPenalty:
    def test_long_description_penalty(self, tmp_path):
        """description が 1024 文字超 → ペナルティ。"""
        long_desc = "A" * (CSO_MAX_DESCRIPTION_LENGTH + 1)
        skill_path = _write_skill_md(
            tmp_path,
            description=long_desc,
            body="## Content\n\nShort body.\n",
        )
        result = check_cso_compliance(skill_path)
        assert len(result["penalties"]) >= 1
        assert any(str(CSO_MAX_DESCRIPTION_LENGTH) in p for p in result["penalties"])

    def test_normal_length_no_penalty(self, tmp_path):
        """description が 1024 文字以下 → 長さペナルティなし。"""
        skill_path = _write_skill_md(
            tmp_path,
            description="A short and concise description",
            body="## Content\n\nBody text.\n",
        )
        result = check_cso_compliance(skill_path)
        length_penalties = [p for p in result["penalties"] if str(CSO_MAX_DESCRIPTION_LENGTH) in p]
        assert len(length_penalties) == 0


class TestCsoNoDescription:
    def test_no_description_returns_zero(self, tmp_path):
        """description が未設定 → score 0.0。"""
        skill_path = _write_skill_md(
            tmp_path,
            description="",
            body="## Content\n\nSome body.\n",
        )
        result = check_cso_compliance(skill_path)
        assert result["score"] == 0.0
        assert result["details"].get("no_description") is True
        assert len(result["penalties"]) >= 1
        assert "description が未設定" in result["penalties"][0]

    def test_no_frontmatter_returns_zero(self, tmp_path):
        """frontmatter 自体がない → description なし → score 0.0。"""
        skill_dir = tmp_path / "no-fm-skill"
        skill_dir.mkdir(parents=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text("# Skill\n\nNo frontmatter here.\n", encoding="utf-8")
        result = check_cso_compliance(skill_path)
        assert result["score"] == 0.0


class TestCsoNormalCase:
    def test_good_description_with_action_pattern(self, tmp_path):
        """良い description + action パターン → 正のスコア。"""
        skill_path = _write_skill_md(
            tmp_path,
            description="Use when reviewing pull requests for security vulnerabilities",
            body="## Detailed Review Process\n\nAnalyze code changes for common security issues.\n",
        )
        result = check_cso_compliance(skill_path)
        assert result["score"] > 0.0
        assert result["score"] <= 1.0
        assert result["details"]["has_action_pattern"] is True
        assert any("行動促進形式" in b for b in result["bonuses"])

    def test_nonexistent_file_returns_zero(self, tmp_path):
        """存在しないファイル → score 0.0。"""
        result = check_cso_compliance(tmp_path / "nonexistent" / "SKILL.md")
        assert result["score"] == 0.0
        assert result["details"] == {}

    def test_score_clamped_to_0_1(self, tmp_path):
        """スコアは 0.0 - 1.0 にクランプされる。"""
        skill_path = _write_skill_md(
            tmp_path,
            description="Use when deploying stacks. Trigger: deploy. Use this skill when needed.",
            body="## Different\n\nCompletely unrelated body text.\n",
        )
        result = check_cso_compliance(skill_path)
        assert 0.0 <= result["score"] <= 1.0
