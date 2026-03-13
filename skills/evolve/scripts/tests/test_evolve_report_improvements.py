"""evolve-report-improvements のユニットテスト。

Task 1.5, 2.4, 3.5, 4.5, 5.3 のテストを網羅。
"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "evolve" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "evolve-fitness" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "scripts"))


# ========== 1.5: Mitigation Trend テスト ==========

class TestComputeTrend:
    def test_no_previous_snapshot(self):
        """初回実行 → has_previous: False。"""
        from evolve import compute_trend
        current = {"builtin_replaceable": 15, "sleep_patterns": 3, "bash_ratio": 0.45}
        result = compute_trend(current, None)
        assert result["has_previous"] is False

    def test_decrease_trend(self):
        """件数減少 → ↓ 表示。"""
        from evolve import compute_trend
        current = {"builtin_replaceable": 10, "sleep_patterns": 2, "bash_ratio": 0.38}
        previous = {"builtin_replaceable": 15, "sleep_patterns": 5, "bash_ratio": 0.45}
        result = compute_trend(current, previous)
        assert result["has_previous"] is True
        assert result["builtin_replaceable"]["diff"] == -5
        assert "↓" in result["builtin_replaceable"]["label"]
        assert "5件減少" in result["builtin_replaceable"]["label"]

    def test_increase_trend(self):
        """件数増加 → ↑ 表示。"""
        from evolve import compute_trend
        current = {"builtin_replaceable": 20, "sleep_patterns": 5, "bash_ratio": 0.50}
        previous = {"builtin_replaceable": 15, "sleep_patterns": 3, "bash_ratio": 0.45}
        result = compute_trend(current, previous)
        assert result["builtin_replaceable"]["diff"] == 5
        assert "↑" in result["builtin_replaceable"]["label"]
        assert "5件増加" in result["builtin_replaceable"]["label"]

    def test_no_change_trend(self):
        """件数変化なし → → 表示。"""
        from evolve import compute_trend
        current = {"builtin_replaceable": 15, "sleep_patterns": 3, "bash_ratio": 0.45}
        previous = {"builtin_replaceable": 15, "sleep_patterns": 3, "bash_ratio": 0.45}
        result = compute_trend(current, previous)
        assert result["builtin_replaceable"]["diff"] == 0
        assert "変化なし" in result["builtin_replaceable"]["label"]

    def test_ratio_trend_decrease(self):
        """bash_ratio 減少 → pp 差表示。"""
        from evolve import compute_trend
        current = {"builtin_replaceable": 10, "sleep_patterns": 2, "bash_ratio": 0.382}
        previous = {"builtin_replaceable": 15, "sleep_patterns": 5, "bash_ratio": 0.454}
        result = compute_trend(current, previous)
        ratio = result["bash_ratio"]
        assert ratio["pp_diff"] < 0
        assert "↓" in ratio["label"]
        assert "pp" in ratio["label"]

    def test_ratio_trend_no_change(self):
        """bash_ratio 変化なし → 変化なし表示。"""
        from evolve import compute_trend
        current = {"builtin_replaceable": 10, "sleep_patterns": 2, "bash_ratio": 0.40}
        previous = {"builtin_replaceable": 10, "sleep_patterns": 2, "bash_ratio": 0.40}
        result = compute_trend(current, previous)
        assert "変化なし" in result["bash_ratio"]["label"]

    def test_previous_zero_count(self):
        """前回値が 0 → 100% 増加。"""
        from evolve import compute_trend
        current = {"builtin_replaceable": 5, "sleep_patterns": 0, "bash_ratio": 0.30}
        previous = {"builtin_replaceable": 0, "sleep_patterns": 0, "bash_ratio": 0.30}
        result = compute_trend(current, previous)
        assert result["builtin_replaceable"]["diff"] == 5
        assert result["builtin_replaceable"]["pct"] == 100.0


# ========== 2.4: Remediation auto_fixable 拡張テスト ==========

class TestLineLimitClassification:
    def test_1_line_excess_auto_fixable(self):
        """1行超過 → confidence 0.95 → auto_fixable。"""
        from remediation import classify_issue
        issue = {
            "type": "line_limit_violation",
            "file": "/project/.claude/rules/test.md",
            "detail": {"lines": 4, "limit": 3},
            "source": "check_line_limits",
        }
        result = classify_issue(issue)
        assert result["confidence_score"] == 0.95
        assert result["category"] == "auto_fixable"

    def test_2_line_excess_proposable(self):
        """2行超過 → proposable 維持（ratio < 1.6 の場合）。"""
        from remediation import classify_issue
        issue = {
            "type": "line_limit_violation",
            "file": "/project/.claude/rules/test.md",
            "detail": {"lines": 7, "limit": 5},  # excess=2, ratio=1.4
            "source": "check_line_limits",
        }
        result = classify_issue(issue)
        assert result["category"] == "proposable"

    def test_fix_dispatch_has_line_limit(self):
        """FIX_DISPATCH に line_limit_violation が登録されている。"""
        from remediation import FIX_DISPATCH, fix_line_limit_violation
        assert FIX_DISPATCH["line_limit_violation"] is fix_line_limit_violation

    def test_fix_line_limit_llm_failure(self, tmp_path):
        """LLM 呼び出し失敗 → proposable に降格。"""
        from remediation import fix_line_limit_violation
        f = tmp_path / "rule.md"
        f.write_text("# Rule\nLine 1\nLine 2\nLine 3\nLine 4\n")
        issue = {
            "type": "line_limit_violation",
            "file": str(f),
            "detail": {"lines": 5, "limit": 3},
            "category": "auto_fixable",
        }
        with mock.patch("subprocess.run", side_effect=OSError("no claude")):
            results = fix_line_limit_violation([issue])
        assert len(results) == 1
        assert results[0]["fixed"] is False
        assert issue["category"] == "proposable"

    def test_fix_line_limit_timeout(self, tmp_path):
        """LLM タイムアウト → proposable に降格。"""
        import subprocess
        from remediation import fix_line_limit_violation
        f = tmp_path / "rule.md"
        f.write_text("# Rule\nLine 1\nLine 2\nLine 3\nLine 4\n")
        issue = {
            "type": "line_limit_violation",
            "file": str(f),
            "detail": {"lines": 5, "limit": 3},
            "category": "auto_fixable",
        }
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60)):
            results = fix_line_limit_violation([issue])
        assert len(results) == 1
        assert results[0]["fixed"] is False
        assert results[0]["error"] == "llm_timeout"
        assert issue["category"] == "proposable"


# ========== 3.5: Reference Type Auto-fix テスト ==========

class TestUpdateFrontmatter:
    def test_update_existing_frontmatter(self, tmp_path):
        """既存 frontmatter にキーを追加。"""
        from frontmatter import update_frontmatter
        f = tmp_path / "SKILL.md"
        f.write_text("---\ndescription: test\n---\n# Content\n")
        success, error = update_frontmatter(f, {"type": "reference"})
        assert success is True
        assert error == ""
        content = f.read_text()
        assert "type: reference" in content
        assert "description: test" in content
        assert "# Content" in content

    def test_add_frontmatter_to_file_without(self, tmp_path):
        """frontmatter なしのファイルに追加。"""
        from frontmatter import update_frontmatter
        f = tmp_path / "SKILL.md"
        f.write_text("# Content\nBody text\n")
        success, error = update_frontmatter(f, {"type": "reference"})
        assert success is True
        content = f.read_text()
        assert content.startswith("---\n")
        assert "type: reference" in content
        assert "# Content" in content

    def test_empty_file_returns_false(self, tmp_path):
        """空ファイル → fixed=False。"""
        from frontmatter import update_frontmatter
        f = tmp_path / "SKILL.md"
        f.write_text("")
        success, error = update_frontmatter(f, {"type": "reference"})
        assert success is False
        assert error == "empty_file"

    def test_yaml_parse_error(self, tmp_path):
        """YAML パースエラー → fixed=False。"""
        from frontmatter import update_frontmatter
        f = tmp_path / "SKILL.md"
        f.write_text("---\n: invalid: yaml: [[\n---\n# Content\n")
        success, error = update_frontmatter(f, {"type": "reference"})
        assert success is False
        assert error == "yaml_parse_error"

    def test_unclosed_frontmatter(self, tmp_path):
        """閉じ --- がない → yaml_parse_error。"""
        from frontmatter import update_frontmatter
        f = tmp_path / "SKILL.md"
        f.write_text("---\ntype: skill\n# No closing delimiter\n")
        success, error = update_frontmatter(f, {"type": "reference"})
        assert success is False
        assert error == "yaml_parse_error"


class TestFixUntaggedReference:
    def test_fix_with_existing_frontmatter(self, tmp_path):
        """frontmatter あり → type: reference 追加。"""
        from remediation import fix_untagged_reference
        f = tmp_path / "SKILL.md"
        f.write_text("---\ndescription: my skill\n---\n# Skill\n")
        issues = [{
            "type": "untagged_reference_candidates",
            "file": str(f),
            "detail": {"skill_name": "my-skill"},
        }]
        results = fix_untagged_reference(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is True
        content = f.read_text()
        assert "type: reference" in content

    def test_fix_without_frontmatter(self, tmp_path):
        """frontmatter なし → 先頭に追加。"""
        from remediation import fix_untagged_reference
        f = tmp_path / "SKILL.md"
        f.write_text("# Skill\nContent here\n")
        issues = [{
            "type": "untagged_reference_candidates",
            "file": str(f),
            "detail": {"skill_name": "my-skill"},
        }]
        results = fix_untagged_reference(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is True
        content = f.read_text()
        assert content.startswith("---\n")
        assert "type: reference" in content

    def test_fix_empty_file(self, tmp_path):
        """空ファイル → fixed=False。"""
        from remediation import fix_untagged_reference
        f = tmp_path / "SKILL.md"
        f.write_text("")
        issues = [{
            "type": "untagged_reference_candidates",
            "file": str(f),
            "detail": {"skill_name": "empty-skill"},
        }]
        results = fix_untagged_reference(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is False

    def test_fix_yaml_parse_error(self, tmp_path):
        """YAML パースエラー → fixスキップ。"""
        from remediation import fix_untagged_reference
        f = tmp_path / "SKILL.md"
        f.write_text("---\n: invalid [[\n---\n# Skill\n")
        issues = [{
            "type": "untagged_reference_candidates",
            "file": str(f),
            "detail": {"skill_name": "bad-yaml"},
        }]
        results = fix_untagged_reference(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is False
        assert "yaml_parse_error" in results[0]["error"]


class TestVerifyUntaggedReference:
    def test_verify_resolved(self, tmp_path):
        """type: reference が存在 → resolved。"""
        from remediation import verify_fix
        f = tmp_path / "SKILL.md"
        f.write_text("---\ntype: reference\n---\n# Skill\n")
        issue = {"type": "untagged_reference_candidates", "detail": {"skill_name": "test"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is True

    def test_verify_not_resolved(self, tmp_path):
        """type: reference がない → not resolved。"""
        from remediation import verify_fix
        f = tmp_path / "SKILL.md"
        f.write_text("---\ndescription: test\n---\n# Skill\n")
        issue = {"type": "untagged_reference_candidates", "detail": {"skill_name": "test"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is False


class TestUntaggedReferenceConfidence:
    def test_confidence_score(self):
        """untagged_reference_candidates → confidence 0.90。"""
        from remediation import compute_confidence_score
        issue = {"type": "untagged_reference_candidates", "detail": {"skill_name": "test"}}
        score = compute_confidence_score(issue)
        assert score == 0.90

    def test_dispatch_registered(self):
        """FIX_DISPATCH と VERIFY_DISPATCH に登録されている。"""
        from remediation import FIX_DISPATCH, VERIFY_DISPATCH
        assert "untagged_reference_candidates" in FIX_DISPATCH
        assert "untagged_reference_candidates" in VERIFY_DISPATCH


# ========== 4.5: Fitness Bootstrap モード テスト ==========

class TestFitnessBootstrap:
    def _make_history(self, n, accepted_ratio=0.5):
        """テスト用 history を生成。"""
        records = []
        for i in range(n):
            records.append({
                "best_fitness": 0.5 + i * 0.01,
                "human_accepted": i < int(n * accepted_ratio),
            })
        return records

    def test_below_bootstrap_min_insufficient(self):
        """0-4件 → insufficient_data。"""
        from fitness_evolution import run_fitness_evolution
        history = self._make_history(4)
        result = run_fitness_evolution(history=history)
        assert result["status"] == "insufficient_data"
        assert result["data_count"] == 4

    def test_bootstrap_mode(self):
        """5-29件 → bootstrap。"""
        from fitness_evolution import run_fitness_evolution
        history = self._make_history(10, accepted_ratio=0.6)
        result = run_fitness_evolution(history=history)
        assert result["status"] == "bootstrap"
        assert result["data_count"] == 10
        assert "bootstrap_analysis" in result
        ba = result["bootstrap_analysis"]
        assert "approval_rate" in ba
        assert "mean_score" in ba
        assert "score_distribution" in ba

    def test_full_analysis_at_threshold(self):
        """30件以上 → ready（既存動作維持）。"""
        from fitness_evolution import run_fitness_evolution
        history = self._make_history(30, accepted_ratio=0.7)
        result = run_fitness_evolution(history=history)
        assert result["status"] == "ready"
        assert result["data_count"] == 30

    def test_bootstrap_approval_rate(self):
        """bootstrap の承認率が正しい。"""
        from fitness_evolution import run_fitness_evolution
        # 10件中6件 accepted
        history = self._make_history(10, accepted_ratio=0.6)
        result = run_fitness_evolution(history=history)
        assert result["bootstrap_analysis"]["approval_rate"] == 0.6

    def test_bootstrap_no_correlation(self):
        """bootstrap モードでは相関分析を行わない。"""
        from fitness_evolution import run_fitness_evolution
        history = self._make_history(15)
        result = run_fitness_evolution(history=history)
        assert result["status"] == "bootstrap"
        assert "correlation" not in result


# ========== 5.3: Bash Ratio Threshold 表示テスト ==========

class TestThresholdDisplay:
    def test_threshold_constants_importable(self):
        """閾値定数がインポート可能。"""
        from tool_usage_analyzer import (
            BASH_RATIO_THRESHOLD,
            BUILTIN_THRESHOLD,
            SLEEP_THRESHOLD,
        )
        assert BASH_RATIO_THRESHOLD == 0.40
        assert BUILTIN_THRESHOLD == 10
        assert SLEEP_THRESHOLD == 20

    def test_threshold_display_format_above(self):
        """閾値以上 → 未達表示フォーマット。"""
        from tool_usage_analyzer import BASH_RATIO_THRESHOLD
        ratio = 0.454
        target = BASH_RATIO_THRESHOLD
        status = "未達" if ratio >= target else "達成"
        display = f"Bash 割合: {ratio*100:.1f}% (目標: ≤{target*100:.0f}%) — {status}"
        assert "未達" in display
        assert "45.4%" in display
        assert "≤40%" in display

    def test_threshold_display_format_below(self):
        """閾値未満 → 達成表示フォーマット。"""
        from tool_usage_analyzer import BASH_RATIO_THRESHOLD
        ratio = 0.35
        target = BASH_RATIO_THRESHOLD
        status = "未達" if ratio >= target else "達成"
        display = f"Bash 割合: {ratio*100:.1f}% (目標: ≤{target*100:.0f}%) — {status}"
        assert "達成" in display
        assert "35.0%" in display
