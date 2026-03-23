#!/usr/bin/env python3
"""remediation.py の _independent_verify / FP_EXCLUSIONS テスト。"""
import sys
from pathlib import Path

import pytest

# remediation.py のパスを通す
_evolve_scripts = Path(__file__).resolve().parent.parent.parent / "skills" / "evolve" / "scripts"
sys.path.insert(0, str(_evolve_scripts))

from remediation import _independent_verify, FP_EXCLUSIONS, _should_exclude_fp


# ── _independent_verify ──────────────────────────────


def test_independent_verify_pass():
    """正常な修正が pass する。"""
    before = "# Title\n\nSome content.\n\n## Sub\n\nMore text.\n"
    after = "# Title\n\nUpdated content.\n\n## Sub\n\nMore text.\n"
    result = _independent_verify(
        {"type": "stale_ref", "file": "CLAUDE.md", "detail": {}},
        before,
        after,
    )
    assert result["passed"] is True
    assert result["confidence"] > 0.0


def test_independent_verify_heading_loss():
    """見出し削除を検出する。"""
    before = "# Title\n\n## Section A\n\nText\n\n## Section B\n\nText\n"
    after = "# Title\n\nText\n\nText\n"
    result = _independent_verify(
        {"type": "stale_ref", "file": "CLAUDE.md", "detail": {}},
        before,
        after,
    )
    assert result["passed"] is False
    assert "heading" in result["reason"].lower() or "見出し" in result["reason"]


def test_independent_verify_empty_file():
    """空ファイルを検出する。"""
    before = "# Title\n\nContent here.\n"
    after = ""
    result = _independent_verify(
        {"type": "stale_ref", "file": "CLAUDE.md", "detail": {}},
        before,
        after,
    )
    assert result["passed"] is False
    assert "empty" in result["reason"].lower() or "空" in result["reason"]


def test_independent_verify_codeblock_mismatch():
    """コードブロックの対応崩れを検出する。"""
    before = "# Title\n\n```python\nprint('hi')\n```\n"
    after = "# Title\n\n```python\nprint('hi')\n"
    result = _independent_verify(
        {"type": "stale_ref", "file": "CLAUDE.md", "detail": {}},
        before,
        after,
    )
    assert result["passed"] is False
    assert "code" in result["reason"].lower() or "コードブロック" in result["reason"]


def test_independent_verify_rules_line_limit():
    """Rules ファイルの行数制限超過を検出する。"""
    _scripts_dir = Path(__file__).resolve().parent.parent
    _lib_dir = _scripts_dir / "lib"
    sys.path.insert(0, str(_scripts_dir))
    sys.path.insert(0, str(_lib_dir))
    from line_limit import MAX_RULE_LINES

    before = "# Rule\nShort rule.\n"
    # MAX_RULE_LINES を超える after を生成
    after = "\n".join([f"Line {i}" for i in range(MAX_RULE_LINES + 5)])
    result = _independent_verify(
        {"type": "stale_rule", "file": ".claude/rules/my-rule.md", "detail": {}},
        before,
        after,
    )
    assert result["passed"] is False
    assert "line" in result["reason"].lower() or "行数" in result["reason"]


# ── FP_EXCLUSIONS / _should_exclude_fp ──────────────────────────────


def test_fp_exclusions_test_file():
    """テストファイル内の参照は FP として除外される。"""
    issue = {
        "type": "stale_ref",
        "file": "scripts/tests/test_something.py",
        "detail": {"path": "some/missing/path.py"},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "test_file"


def test_fp_exclusions_external_url():
    """http(s):// で始まる参照は FP として除外される。"""
    issue = {
        "type": "stale_ref",
        "file": "CLAUDE.md",
        "detail": {"path": "https://example.com/doc"},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "external_url"


def test_fp_exclusions_archive_path():
    """archive パス配下の参照は FP として除外される。"""
    issue = {
        "type": "stale_ref",
        "file": "CLAUDE.md",
        "detail": {"path": "openspec/changes/archive/2026-01-01-old/tasks.md"},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "archive_path"


def test_fp_exclusions_no_match():
    """除外条件に該当しない issue は None を返す。"""
    issue = {
        "type": "stale_ref",
        "file": "CLAUDE.md",
        "detail": {"path": "scripts/lib/missing_module.py"},
    }
    reason = _should_exclude_fp(issue)
    assert reason is None


def test_fp_exclusions_numeric_only():
    """数値のみパターンは除外される。"""
    issue = {
        "type": "hardcoded_value",
        "file": "rules.md",
        "detail": {"matched": "429", "path": ""},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "numeric_only"


def test_fp_exclusions_code_block_ref():
    """コードブロック内の参照は除外される。"""
    issue = {
        "type": "stale_ref",
        "file": "CLAUDE.md",
        "detail": {"path": "some/path.py", "in_code_block": True},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "code_block_ref"


def test_fp_exclusions_commented_out():
    """コメント内の参照は除外される。"""
    issue = {
        "type": "stale_ref",
        "file": "CLAUDE.md",
        "detail": {"path": "old/path.py", "commented_out": True},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "commented_out"


def test_fp_exclusions_changelog_entry():
    """CHANGELOG.md 内の参照は除外される。"""
    issue = {
        "type": "stale_ref",
        "file": "CHANGELOG.md",
        "detail": {"path": "old/removed/module.py"},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "changelog_entry"


def test_fp_exclusions_short_field_name():
    """短いフィールド名は除外される。"""
    issue = {
        "type": "stale_ref",
        "file": "CLAUDE.md",
        "detail": {"path": "foo/bar"},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "short_field_name"


def test_fp_exclusions_plugin_managed():
    """plugin origin のスキル参照は除外される。"""
    issue = {
        "type": "claudemd_phantom_ref",
        "file": "CLAUDE.md",
        "detail": {"name": "my-plugin-skill", "plugin_managed": True},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "plugin_managed"


def test_fp_exclusions_frontmatter_path():
    """frontmatter の paths/globs 内の参照は除外される。"""
    issue = {
        "type": "stale_ref",
        "file": ".claude/rules/my-rule.md",
        "detail": {"path": "scripts/**/*.py", "in_frontmatter": True},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "frontmatter_path"


def test_fp_exclusions_example_snippet():
    """例示コード内の参照は除外される。"""
    issue = {
        "type": "stale_ref",
        "file": "CLAUDE.md",
        "detail": {"path": "example/path.py", "in_example": True},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "example_snippet"


def test_fp_exclusions_memory_index_only():
    """MEMORY.md のインデックス行は除外される。"""
    issue = {
        "type": "stale_memory",
        "file": "MEMORY.md",
        "detail": {"path": "some_topic", "memory_index_only": True},
    }
    reason = _should_exclude_fp(issue)
    assert reason == "memory_index_only"


def test_fp_exclusions_list_completeness():
    """FP_EXCLUSIONS に全12パターンが含まれている。"""
    assert len(FP_EXCLUSIONS) == 12
    expected = {
        "test_file", "archive_path", "external_url", "numeric_only",
        "code_block_ref", "frontmatter_path", "example_snippet",
        "commented_out", "changelog_entry", "memory_index_only",
        "plugin_managed", "short_field_name",
    }
    assert set(FP_EXCLUSIONS) == expected
