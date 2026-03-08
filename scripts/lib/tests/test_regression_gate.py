"""regression_gate モジュールのユニットテスト。"""

import sys
from pathlib import Path

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

from regression_gate import GateResult, check_gates


class TestCheckGates:
    """check_gates() の6シナリオテスト。"""

    def test_空コンテンツ(self):
        result = check_gates("", max_lines=500)
        assert result == GateResult(passed=False, reason="empty_content")

    def test_空白のみ(self):
        result = check_gates("   \n  ", max_lines=500)
        assert result == GateResult(passed=False, reason="empty_content")

    def test_行数制限超過(self):
        content = "\n".join(f"line {i}" for i in range(501))
        result = check_gates(content, max_lines=500)
        assert result.passed is False
        assert "line_limit_exceeded" in result.reason

    def test_禁止パターン検出(self):
        result = check_gates("# Skill\n\nTODO: fix this", max_lines=500)
        assert result == GateResult(passed=False, reason="forbidden_pattern(TODO)")

    def test_frontmatter_消失(self):
        result = check_gates(
            "# No frontmatter",
            original="---\nname: test\n---\n# Original",
            max_lines=500,
        )
        assert result == GateResult(passed=False, reason="frontmatter_lost")

    def test_pitfall_パターン検出(self, tmp_path):
        pitfalls = tmp_path / "pitfalls.md"
        pitfalls.write_text(
            "| Source | Pattern | Score |\n"
            "|--------|---------|-------|\n"
            "| gate | forbidden_pattern(BAD_WORD) | 0.0 |\n"
        )
        result = check_gates(
            "# Skill\n\nBAD_WORD here",
            max_lines=500,
            pitfall_patterns_path=str(pitfalls),
        )
        assert result.passed is False
        assert "pitfall_pattern(BAD_WORD)" in result.reason

    def test_全ゲート通過(self):
        result = check_gates(
            "---\nname: test\n---\n# Good Skill\n\nThis is fine.",
            original="---\nname: test\n---\n# Original",
            max_lines=500,
        )
        assert result == GateResult(passed=True, reason=None)

    def test_pitfall_ファイル不在時スキップ(self):
        result = check_gates(
            "# Good Skill",
            max_lines=500,
            pitfall_patterns_path="/nonexistent/pitfalls.md",
        )
        assert result.passed is True

    def test_frontmatter_なし_スキップ(self):
        result = check_gates(
            "# Updated",
            original="# No frontmatter",
            max_lines=500,
        )
        assert result.passed is True

    def test_original_None_時_frontmatter_チェックスキップ(self):
        result = check_gates("# Content", max_lines=500)
        assert result.passed is True


class TestGateResult:
    """GateResult dataclass の構造テスト。"""

    def test_2フィールドのみ(self):
        r = GateResult(passed=True, reason=None)
        assert hasattr(r, "passed")
        assert hasattr(r, "reason")
        assert not hasattr(r, "score")
