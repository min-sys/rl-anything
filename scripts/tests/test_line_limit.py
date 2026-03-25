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
    MEMORY_MAX_BYTES,
    MEMORY_NEAR_LIMIT_BYTES,
    SeparationProposal,
    check_line_limit,
    check_memory_byte_limit,
    suggest_separation,
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


# --- suggest_separation tests ---


def test_suggest_separation_global_rule_exceeds():
    """グローバル rule が3行超過で SeparationProposal を返す。"""
    home = str(Path.home())
    target = f"{home}/.claude/rules/foo.md"
    content = "line1\nline2\nline3\nline4"  # 4 lines > 3
    result = suggest_separation(target, content)
    assert result is not None
    assert isinstance(result, SeparationProposal)
    assert result.target_path == target
    assert "references/foo.md" in result.reference_path
    assert result.excess_lines == 1
    assert "references/" in result.summary_template


def test_suggest_separation_project_rule_exceeds():
    """PJ rule が5行超過で SeparationProposal を返す。"""
    target = "/project/.claude/rules/bar.md"
    content = "\n".join([f"line{i}" for i in range(6)])  # 6 lines > 5
    result = suggest_separation(target, content)
    assert result is not None
    assert "references/bar.md" in result.reference_path
    assert result.excess_lines == 1


def test_suggest_separation_within_limit():
    """行数制限内では None を返す。"""
    target = "/project/.claude/rules/ok.md"
    content = "line1\nline2\nline3"  # 3 lines <= 5
    assert suggest_separation(target, content) is None


def test_suggest_separation_skill_file():
    """skill ファイルでは None を返す。"""
    target = "/project/.claude/skills/my-skill/SKILL.md"
    content = "\n".join(["line"] * 600)
    assert suggest_separation(target, content) is None


def test_rule_with_frontmatter_within_limit():
    """frontmatter 付きルールが frontmatter 除外でカウントされ制限内となる。"""
    # 5行の frontmatter + 3行のコンテンツ = 全体8行だが、コンテンツは3行
    content = '---\npaths:\n  - "**/*.py"\nname: test\n---\n# Rule\nLine 1\nLine 2'
    home = str(Path.home())
    assert check_line_limit(f"{home}/.claude/rules/my-rule.md", content) is True


def test_rule_with_frontmatter_exceeds_limit(capsys):
    """frontmatter 付きルールが frontmatter 除外でもコンテンツ超過なら False。"""
    # 5行の frontmatter + 4行のコンテンツ = 全体9行、コンテンツ4行 > 3
    content = '---\npaths:\n  - "**/*.py"\nname: test\n---\n# Rule\nLine 1\nLine 2\nLine 3'
    home = str(Path.home())
    assert check_line_limit(f"{home}/.claude/rules/my-rule.md", content) is False
    captured = capsys.readouterr()
    assert "行数超過" in captured.err


def test_project_rule_with_frontmatter_within_limit():
    """プロジェクトルール + frontmatter で制限内。"""
    # 4行 frontmatter + 5行コンテンツ = 全体9行、コンテンツ5行 <= 5
    content = '---\npaths:\n  - "src/**"\n---\nLine 1\nLine 2\nLine 3\nLine 4\nLine 5'
    assert check_line_limit("/project/.claude/rules/my-rule.md", content) is True


def test_separation_with_frontmatter_within_limit():
    """frontmatter のおかげでコンテンツが制限内なら None。"""
    home = str(Path.home())
    # 4行 frontmatter + 3行コンテンツ = 全体7行、コンテンツ3行 <= 3
    content = '---\npaths:\n  - "**/*.py"\n---\n# Rule\nLine 1\nLine 2'
    assert suggest_separation(f"{home}/.claude/rules/foo.md", content) is None


def test_separation_with_frontmatter_exceeds():
    """frontmatter 除外でもコンテンツ超過なら SeparationProposal を返す。"""
    home = str(Path.home())
    # 5行 frontmatter + 5行コンテンツ = 全体10行、コンテンツ5行、超過2行
    content = '---\npaths:\n  - "**/*.py"\nname: test\n---\n# Rule\nLine 1\nLine 2\nLine 3\nLine 4'
    result = suggest_separation(f"{home}/.claude/rules/foo.md", content)
    assert result is not None
    assert result.excess_lines == 2


def test_suggest_separation_deduplication(tmp_path):
    """分離先パスが既存ファイルと衝突する場合サフィックスを付与する。"""
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    refs_dir = tmp_path / ".claude" / "references"
    refs_dir.mkdir(parents=True)
    # 衝突するファイルを作成
    (refs_dir / "foo.md").write_text("existing", encoding="utf-8")

    target = str(rules_dir / "foo.md")
    content = "\n".join([f"line{i}" for i in range(6)])  # 超過
    result = suggest_separation(target, content)
    assert result is not None
    assert result.reference_path.endswith("foo_2.md")


# --- check_memory_byte_limit tests ---


def test_check_memory_byte_limit_under():
    """25KB 未満のコンテンツは (True, size) を返す。"""
    content = "a" * 24_000  # 24KB
    within, size = check_memory_byte_limit(content)
    assert within is True
    assert size == 24_000


def test_check_memory_byte_limit_over():
    """25KB 超のコンテンツは (False, size) を返す。"""
    content = "a" * 26_000  # 26KB
    within, size = check_memory_byte_limit(content)
    assert within is False
    assert size == 26_000


def test_check_memory_byte_limit_exact():
    """ちょうど 25KB は (True, 25000) を返す。"""
    content = "a" * 25_000
    within, size = check_memory_byte_limit(content)
    assert within is True
    assert size == 25_000


def test_check_memory_byte_limit_multibyte():
    """日本語テキスト（UTF-8 マルチバイト）で正しいバイト数を返す。"""
    # 「あ」は UTF-8 で 3 bytes
    content = "あ" * 8_334  # 8334 * 3 = 25002 bytes > 25000
    within, size = check_memory_byte_limit(content)
    assert within is False
    assert size == 8_334 * 3


def test_check_memory_byte_limit_near_limit():
    """80% (20KB) 超は within=True だが near-limit 判定用に size を返す。"""
    content = "a" * 21_000  # 21KB > 20KB near-limit
    within, size = check_memory_byte_limit(content)
    assert within is True  # まだ上限内
    assert size == 21_000
    # near-limit 判定は呼び出し側が MEMORY_NEAR_LIMIT_BYTES と比較
    assert size > MEMORY_NEAR_LIMIT_BYTES


def test_memory_byte_constants():
    """バイト制限定数が正しいことを確認。"""
    assert MEMORY_MAX_BYTES == 25_000
    assert MEMORY_NEAR_LIMIT_BYTES == 20_000
