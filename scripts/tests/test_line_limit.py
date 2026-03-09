#!/usr/bin/env python3
"""line_limit.py のユニットテスト。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.line_limit import (
    CLAUDEMD_WARNING_LINES,
    MAX_PROJECT_RULE_LINES,
    MAX_RULE_LINES,
    MAX_SKILL_LINES,
    check_line_limit,
)


def test_constants():
    """定数値が正しいことを確認。"""
    assert MAX_SKILL_LINES == 500
    assert MAX_RULE_LINES == 3
    assert MAX_PROJECT_RULE_LINES == 5
    assert CLAUDEMD_WARNING_LINES == 300


def test_skill_within_limit():
    """スキルファイルが行数制限内で True を返す。"""
    content = "\n".join(["line"] * 100)
    assert check_line_limit("/project/.claude/skills/foo/SKILL.md", content) is True


def test_skill_exceeds_limit(capsys):
    """スキルファイルが行数超過で False + stderr 警告。"""
    content = "\n".join(["line"] * 501)
    assert check_line_limit("/project/.claude/skills/foo/SKILL.md", content) is False
    captured = capsys.readouterr()
    assert "行数超過" in captured.err
    assert "スキル" in captured.err


def test_rule_within_limit():
    """ルールファイルが行数制限内で True を返す。"""
    content = "line1\nline2\nline3"
    assert check_line_limit("/project/.claude/rules/my-rule.md", content) is True


def test_rule_exceeds_limit(capsys):
    """ルールファイルが行数超過で False + stderr 警告。"""
    content = "line1\nline2\nline3\nline4\nline5\nline6"
    assert check_line_limit("/project/.claude/rules/my-rule.md", content) is False
    captured = capsys.readouterr()
    assert "行数超過" in captured.err
    assert "ルール" in captured.err


def test_rule_detection_by_path():
    """パスに .claude/rules/ を含む場合はルール判定。"""
    content = "\n".join(["line"] * 100)
    # ルールパスなら制限（グローバル: 3行、プロジェクト: 5行）
    home = str(Path.home())
    assert check_line_limit(f"{home}/.claude/rules/foo.md", content) is False
    assert check_line_limit("/project/.claude/rules/foo.md", content) is False
    # スキルパスなら 500 行制限
    assert check_line_limit("/home/.claude/skills/foo/SKILL.md", content) is True


def test_project_rule_limit():
    """プロジェクトルール（グローバルでない）は 5 行まで許容される。"""
    content = "line1\nline2\nline3\nline4\nline5"
    # プロジェクトルールは 5 行制限
    assert check_line_limit("/project/.claude/rules/my-rule.md", content) is True
    # グローバルルールは 3 行制限
    home = str(Path.home())
    assert check_line_limit(f"{home}/.claude/rules/my-rule.md", content) is False


def test_global_rule_limit():
    """グローバルルール（~/.claude/rules/）は 3 行制限。"""
    content = "line1\nline2\nline3\nline4"
    home = str(Path.home())
    assert check_line_limit(f"{home}/.claude/rules/my-rule.md", content) is False
