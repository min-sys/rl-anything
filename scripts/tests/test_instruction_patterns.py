"""Tests for instruction_patterns — 7パターン検出 + defaults_first + context_efficiency."""
import sys
from pathlib import Path

import pytest

# ── path setup ────────────────────────────────────────
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.instruction_patterns import (
    CONTEXT_EFFICIENCY_MIN_LINES,
    DEFAULTS_FIRST_LLM_THRESHOLD,
    UNIVERSAL_KNOWLEDGE_PATTERNS,
    analyze_context_efficiency,
    check_defaults_first,
    detect_patterns,
)


# ============================================================
# detect_patterns — 7パターン検出
# ============================================================

class TestDetectPatternsGotchas:
    """gotchas パターン: # Gotchas / # Pitfalls / # 注意点 セクション検出。"""

    def test_gotchas_detected_with_gotchas_heading(self):
        content = "# Overview\nSome text\n\n# Gotchas\n- Watch out for X\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["gotchas"] is True
        assert "gotchas" in result["used_patterns"]

    def test_gotchas_detected_with_pitfalls_heading(self):
        content = "# Setup\n\n# Pitfalls\n- Don't do Y\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["gotchas"] is True

    def test_gotchas_detected_with_japanese_heading(self):
        content = "# 概要\n\n# 注意点\n- Zに注意\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["gotchas"] is True

    def test_gotchas_not_detected_without_heading(self):
        content = "# Overview\nJust some normal content.\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["gotchas"] is False
        assert "gotchas" not in result["used_patterns"]


class TestDetectPatternsOutputTemplate:
    """output_template パターン: コードブロック内の構造化例。"""

    def test_output_template_detected(self):
        content = "# Output\n```json\n{\"key\": \"value\"}\n```\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["output_template"] is True
        assert "output_template" in result["used_patterns"]

    def test_output_template_detected_yaml(self):
        content = "# Example\n```yaml\nname: test\nvalue: 123\n```\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["output_template"] is True

    def test_output_template_not_detected_without_codeblock(self):
        content = "# Overview\nNo code blocks here.\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["output_template"] is False


class TestDetectPatternsChecklist:
    """checklist パターン: 3つ以上の番号付き手順。"""

    def test_checklist_detected_with_three_steps(self):
        content = "# Steps\n1. Do A\n2. Do B\n3. Do C\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["checklist"] is True
        assert "checklist" in result["used_patterns"]

    def test_checklist_not_detected_with_two_steps(self):
        content = "# Steps\n1. Do A\n2. Do B\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["checklist"] is False

    def test_checklist_detected_non_contiguous(self):
        content = "1. First step\nSome explanation.\n2. Second step\nMore text.\n3. Third step\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["checklist"] is True


class TestDetectPatternsValidationLoop:
    """validation_loop パターン: validate/check/verify → fix/修正。"""

    def test_validation_loop_detected(self):
        content = "1. Run validate\n2. If errors, fix them\n3. Repeat\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["validation_loop"] is True
        assert "validation_loop" in result["used_patterns"]

    def test_validation_loop_detected_check_fix(self):
        content = "Check the output.\nIf wrong, fix the issue.\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["validation_loop"] is True

    def test_validation_loop_detected_verify_shuusei(self):
        content = "結果をverifyする。問題があれば修正する。\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["validation_loop"] is True

    def test_validation_loop_not_detected_without_fix(self):
        content = "Run validate to see the output.\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["validation_loop"] is False


class TestDetectPatternsPlanValidateExecute:
    """plan_validate_execute パターン: plan/確認 → execute/実行。"""

    def test_pve_detected(self):
        content = "1. Create a plan\n2. Review it\n3. Execute the plan\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["plan_validate_execute"] is True
        assert "plan_validate_execute" in result["used_patterns"]

    def test_pve_detected_japanese(self):
        content = "まず確認する。次に実行する。\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["plan_validate_execute"] is True

    def test_pve_not_detected_execute_only(self):
        content = "Execute the deployment immediately.\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["plan_validate_execute"] is False


class TestDetectPatternsProgressiveDisclosure:
    """progressive_disclosure パターン: references/ 条件参照 or Read ... if。"""

    def test_progressive_disclosure_detected_references(self):
        content = "See references/details.md for advanced config.\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["progressive_disclosure"] is True
        assert "progressive_disclosure" in result["used_patterns"]

    def test_progressive_disclosure_detected_read_if(self):
        content = "Read the config file if you need custom settings.\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["progressive_disclosure"] is True

    def test_progressive_disclosure_not_detected(self):
        content = "# Simple instructions\nDo the thing.\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["progressive_disclosure"] is False


class TestDetectPatternsDefaultsFirst:
    """defaults_first パターン: DefaultsFirstDetector のスコア。"""

    def test_defaults_first_is_float(self):
        content = "Use option A or option B. Recommended: option A.\n"
        result = detect_patterns(content)
        assert isinstance(result["pattern_details"]["defaults_first"], float)

    def test_defaults_first_no_choices_is_1(self):
        content = "Do the thing this way.\n"
        result = detect_patterns(content)
        assert result["pattern_details"]["defaults_first"] == 1.0


class TestDetectPatternsScore:
    """score は検出パターン数 / 7。"""

    def test_score_zero_for_empty(self):
        result = detect_patterns("")
        assert result["score"] == pytest.approx(0.0)

    def test_score_partial(self):
        # gotchas + checklist = 2 patterns → 2/7
        content = "# Gotchas\n- Watch out\n\n1. Do A\n2. Do B\n3. Do C\n"
        result = detect_patterns(content)
        # gotchas=True, checklist=True, defaults_first の float は >0.5 で True 扱い
        detected = sum(
            1 for k, v in result["pattern_details"].items()
            if (isinstance(v, bool) and v) or (isinstance(v, float) and v > 0.5)
        )
        assert result["score"] == pytest.approx(detected / 7, abs=0.01)

    def test_used_patterns_matches_pattern_details(self):
        content = "# Pitfalls\n- X\n```json\n{}\n```\n1. A\n2. B\n3. C\n"
        result = detect_patterns(content)
        bool_true = [k for k, v in result["pattern_details"].items()
                     if isinstance(v, bool) and v]
        for p in bool_true:
            assert p in result["used_patterns"]

    def test_all_patterns_detected(self):
        content = (
            "# Gotchas\n- Watch out\n\n"
            "```json\n{\"output\": true}\n```\n\n"
            "1. Plan first\n2. Validate output\n3. Execute deploy\n\n"
            "Run validate, then fix errors.\n"
            "First plan, then execute.\n"
            "See references/advanced.md for details.\n"
            "Use option A or option B. Recommended: option A.\n"
        )
        result = detect_patterns(content)
        assert result["score"] == pytest.approx(1.0)
        assert len(result["used_patterns"]) == 7


# ============================================================
# check_defaults_first
# ============================================================

class TestCheckDefaultsFirst:
    """DefaultsFirstDetector: 選択肢×推奨マーカーの組み合わせ。"""

    def test_no_choices_returns_1(self):
        """選択肢がない = メニューなし = 良い → 1.0。"""
        content = "Do the thing this exact way.\nNo alternatives.\n"
        assert check_defaults_first(content) == 1.0

    def test_choices_with_recommendation_high_score(self):
        """選択肢あり + 推奨マーカーあり → 0.5-1.0。"""
        content = (
            "Use option A or option B.\n"
            "Recommended: option A.\n"
            "Choose between method 1 or method 2.\n"
            "デフォルトは method 1。\n"
        )
        score = check_defaults_first(content)
        assert 0.5 <= score <= 1.0

    def test_choices_without_recommendation_low_score(self):
        """選択肢あり + 推奨マーカーなし → 0.0-0.3。"""
        content = (
            "Use option A or option B.\n"
            "Choose between method 1 or method 2.\n"
            "Either approach works.\n"
        )
        score = check_defaults_first(content)
        assert 0.0 <= score <= 0.3

    def test_single_choice_with_recommendation(self):
        content = "Use either approach. 推奨は A.\n"
        score = check_defaults_first(content)
        assert 0.5 <= score <= 1.0

    def test_japanese_choice_patterns(self):
        """方法1/方法2 パターン。"""
        content = "方法1: 直接実行\n方法2: テスト後実行\n"
        score = check_defaults_first(content)
        assert score <= 0.3  # 推奨マーカーなし

    def test_a_b_pattern(self):
        """A) B) パターン。"""
        content = "A) Quick setup\nB) Full setup\n"
        score = check_defaults_first(content)
        assert score <= 0.3  # 推奨マーカーなし


# ============================================================
# analyze_context_efficiency
# ============================================================

class TestAnalyzeContextEfficiency:
    """ContextEfficiencyAnalyzer: 普遍的知識 + signal/noise + CLAUDE.md 重複。"""

    def test_basic_structure(self):
        content = "# Skill\nDo `something --flag`.\nEdit `path/to/file.py`.\n"
        result = analyze_context_efficiency(content)
        assert "universal_knowledge_matches" in result
        assert "signal_noise_ratio" in result
        assert "claude_md_overlap" in result
        assert "efficiency_score" in result

    def test_no_universal_knowledge(self):
        content = "# Custom\nRun `my-tool --optimize`.\nCheck `src/main.rs`.\n"
        result = analyze_context_efficiency(content)
        assert result["universal_knowledge_matches"] == 0
        assert result["efficiency_score"] >= 0.9

    def test_universal_knowledge_detected(self):
        content = (
            "git commit -m 'msg'  # commit changes\n"
            "HTTP GET request with status code 200\n"
            "pip install requests  # install the library\n"
            "npm install express  # install express\n"
        )
        result = analyze_context_efficiency(content)
        assert result["universal_knowledge_matches"] >= 2

    def test_signal_noise_ratio(self):
        """signal 行（インラインコード / ファイルパス）vs noise 行。"""
        content = (
            "Run `pytest -v` to test.\n"
            "Edit `scripts/lib/foo.py`.\n"
            "This is a general instruction.\n"
            "Be careful about edge cases.\n"
        )
        result = analyze_context_efficiency(content)
        # 2 signal lines / 4 total = 0.5
        assert 0.3 <= result["signal_noise_ratio"] <= 0.7

    def test_claude_md_none_when_not_provided(self):
        content = "# Skill\nDo something.\n"
        result = analyze_context_efficiency(content)
        assert result["claude_md_overlap"] is None

    def test_claude_md_overlap_detected(self):
        """CLAUDE.md との重複がある場合。"""
        shared_text = "Run pytest -v to execute tests. Check the output carefully."
        skill_lines = [f"Line {i}: unique content for padding." for i in range(60)]
        skill_content = "\n".join(skill_lines) + "\n" + shared_text + "\n"
        claude_md = "# Project\n" + shared_text + "\nOther project info.\n"
        result = analyze_context_efficiency(skill_content, claude_md)
        assert result["claude_md_overlap"] is not None
        assert result["claude_md_overlap"] >= 0.0

    def test_claude_md_overlap_skipped_short_skill(self):
        """CONTEXT_EFFICIENCY_MIN_LINES 未満はスキップ。"""
        content = "# Short\nDo X.\n"
        claude_md = "# Project\nDo X.\n"
        result = analyze_context_efficiency(content, claude_md)
        assert result["claude_md_overlap"] is None

    def test_efficiency_score_range(self):
        content = "# Skill\nRun `cmd`.\n"
        result = analyze_context_efficiency(content)
        assert 0.0 <= result["efficiency_score"] <= 1.0

    def test_efficiency_penalized_by_universal_knowledge(self):
        """普遍的知識が多いとスコアが下がる。"""
        bad_content = "\n".join([
            "git commit -m 'save'  # commit",
            "git push origin main  # push",
            "pip install flask  # install flask",
            "npm run build  # install and build",
            "docker run nginx  # basic container",
            "HTTP POST with status code 201",
            "JSON is a format for data",
            "what a variable is in programming",
            "Some unique line 1",
            "Some unique line 2",
        ])
        good_content = "\n".join([
            "Run `scripts/deploy.sh --env prod`.",
            "Edit `config/settings.yaml` to set timeout.",
            "Check `logs/error.log` for failures.",
            "Unique instruction 1",
            "Unique instruction 2",
            "Unique instruction 3",
            "Unique instruction 4",
            "Unique instruction 5",
            "Unique instruction 6",
            "Unique instruction 7",
        ])
        bad_result = analyze_context_efficiency(bad_content)
        good_result = analyze_context_efficiency(good_content)
        assert good_result["efficiency_score"] > bad_result["efficiency_score"]


# ============================================================
# Constants
# ============================================================

class TestConstants:
    def test_universal_knowledge_patterns_count(self):
        assert len(UNIVERSAL_KNOWLEDGE_PATTERNS) == 8

    def test_context_efficiency_min_lines(self):
        assert CONTEXT_EFFICIENCY_MIN_LINES == 50

    def test_defaults_first_llm_threshold(self):
        assert DEFAULTS_FIRST_LLM_THRESHOLD == 0.5
