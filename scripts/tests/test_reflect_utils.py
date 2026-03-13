#!/usr/bin/env python3
"""reflect_utils.py のユニットテスト。"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reflect_utils import (
    _parse_rule_frontmatter,
    detect_project_signals,
    detect_side_effect_correction,
    find_claude_files,
    read_auto_memory,
    split_memory_sections,
    suggest_auto_memory_topic,
    suggest_claude_file,
)


# --- _parse_rule_frontmatter ---


def test_parse_frontmatter_with_paths(tmp_path):
    rule = tmp_path / "api.md"
    rule.write_text("---\npaths:\n  - src/api/\n  - lib/api/\n---\n# API rules\n")
    result = _parse_rule_frontmatter(rule)
    assert result["paths"] == ["src/api/", "lib/api/"]


def test_parse_frontmatter_string_paths(tmp_path):
    rule = tmp_path / "single.md"
    rule.write_text("---\npaths: src/\n---\ncontent\n")
    result = _parse_rule_frontmatter(rule)
    assert result["paths"] == "src/"


def test_parse_frontmatter_no_frontmatter(tmp_path):
    rule = tmp_path / "no-fm.md"
    rule.write_text("# Just a rule\nNo frontmatter here.\n")
    result = _parse_rule_frontmatter(rule)
    assert result == {}


def test_parse_frontmatter_empty_yaml(tmp_path):
    rule = tmp_path / "empty.md"
    rule.write_text("---\n---\ncontent\n")
    result = _parse_rule_frontmatter(rule)
    assert result == {}


def test_parse_frontmatter_invalid_yaml(tmp_path):
    rule = tmp_path / "bad.md"
    rule.write_text("---\n: invalid: yaml: [[\n---\ncontent\n")
    result = _parse_rule_frontmatter(rule)
    assert result == {}


def test_parse_frontmatter_missing_end_delimiter(tmp_path):
    rule = tmp_path / "no-end.md"
    rule.write_text("---\npaths: src/\ncontent without end delimiter\n")
    result = _parse_rule_frontmatter(rule)
    assert result == {}


def test_parse_frontmatter_nonexistent_file(tmp_path):
    result = _parse_rule_frontmatter(tmp_path / "nonexistent.md")
    assert result == {}


# --- find_claude_files ---


def test_find_claude_files_root_and_local(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("root")
    (tmp_path / "CLAUDE.local.md").write_text("local")
    result = find_claude_files(tmp_path)
    assert len(result["root"]) == 1
    assert result["root"][0] == tmp_path / "CLAUDE.md"
    assert len(result["local"]) == 1
    assert result["local"][0] == tmp_path / "CLAUDE.local.md"


def test_find_claude_files_subdirectory(tmp_path):
    subdir = tmp_path / "src" / "api"
    subdir.mkdir(parents=True)
    (subdir / "CLAUDE.md").write_text("api rules")
    (tmp_path / "CLAUDE.md").write_text("root")
    result = find_claude_files(tmp_path)
    assert len(result["subdirectory"]) == 1
    assert result["subdirectory"][0] == subdir / "CLAUDE.md"


def test_find_claude_files_excludes_dot_claude_subdir(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("root")
    claude_dir = tmp_path / ".claude" / "subdir"
    claude_dir.mkdir(parents=True)
    (claude_dir / "CLAUDE.md").write_text("internal")
    result = find_claude_files(tmp_path)
    assert len(result["subdirectory"]) == 0


def test_find_claude_files_rules(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "a.md").write_text("rule a")
    (rules_dir / "b.md").write_text("rule b")
    result = find_claude_files(tmp_path)
    assert len(result["rule"]) == 2


def test_find_claude_files_skills(tmp_path):
    cmd_dir = tmp_path / ".claude" / "commands" / "my-skill"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "SKILL.md").write_text("skill")
    result = find_claude_files(tmp_path)
    assert len(result["skill"]) == 1


def test_find_claude_files_auto_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/test/project")
    encoded = "test-project"
    memory_dir = tmp_path / ".claude" / "projects" / encoded / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "workflow.md").write_text("workflow notes")
    # HOME を tmp_path に設定
    monkeypatch.setenv("HOME", str(tmp_path))
    result = find_claude_files(tmp_path)
    assert len(result["auto-memory"]) == 1


def test_find_claude_files_all_8_tiers(tmp_path, monkeypatch):
    """8層全てが検出されることを確認。"""
    # global
    global_dir = tmp_path / ".claude"
    global_dir.mkdir(parents=True)
    (global_dir / "CLAUDE.md").write_text("global")
    monkeypatch.setenv("HOME", str(tmp_path))

    # root
    (tmp_path / "CLAUDE.md").write_text("root")

    # local
    (tmp_path / "CLAUDE.local.md").write_text("local")

    # subdirectory
    subdir = tmp_path / "src"
    subdir.mkdir()
    (subdir / "CLAUDE.md").write_text("sub")

    # rule
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "test.md").write_text("rule")

    # user-rule
    user_rules = tmp_path / ".claude" / "rules"
    # user-rule は global_dir 内に既に作られている

    # auto-memory
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    encoded = str(tmp_path).replace("/", "-").lstrip("-")
    mem_dir = tmp_path / ".claude" / "projects" / encoded / "memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "general.md").write_text("memo")

    # skill
    skill_dir = tmp_path / ".claude" / "commands" / "my-cmd"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("skill content")

    result = find_claude_files(tmp_path)
    assert len(result["global"]) == 1
    assert len(result["root"]) == 1
    assert len(result["local"]) == 1
    assert len(result["subdirectory"]) == 1
    assert len(result["rule"]) >= 1
    assert len(result["auto-memory"]) == 1
    assert len(result["skill"]) == 1


# --- suggest_claude_file ---


def test_suggest_guardrail(tmp_path):
    correction = {"message": "Don't add comments", "correction_type": "guardrail", "guardrail": True, "confidence": 0.90}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "guardrails.md" in result[0]


def test_suggest_guardrail_by_sentiment(tmp_path):
    correction = {"message": "Never do X", "correction_type": "dont-unless-asked", "sentiment": "guardrail", "confidence": 0.90}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "guardrails.md" in result[0]


def test_suggest_model_preference(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    correction = {"message": "Use claude-4 for this", "correction_type": "correction", "confidence": 0.80}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "CLAUDE.md" in result[0]
    assert result[1] == 0.85


def test_suggest_model_preference_with_rule(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    model_rule = tmp_path / ".claude" / "rules" / "model-preferences.md"
    model_rule.parent.mkdir(parents=True, exist_ok=True)
    model_rule.write_text("model prefs")
    correction = {"message": "Use claude-4 for analysis", "correction_type": "correction", "confidence": 0.80}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "model-preferences.md" in result[0]


def test_suggest_always_never(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    correction = {"message": "Always use bun", "correction_type": "explicit", "confidence": 0.90}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "CLAUDE.md" in result[0]
    assert result[1] == 0.80


def test_suggest_paths_frontmatter_match(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    rule = rules_dir / "api.md"
    rule.write_text("---\npaths:\n  - src/api/\n---\n# API rules\n")
    correction = {"message": "In src/api/ validate input", "correction_type": "correction", "confidence": 0.80}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "api.md" in result[0]


def test_suggest_subdirectory_match(tmp_path):
    subdir = tmp_path / "frontend"
    subdir.mkdir()
    (subdir / "CLAUDE.md").write_text("frontend rules")
    correction = {"message": "In the frontend use React", "correction_type": "correction", "confidence": 0.80}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "frontend" in result[0]


def test_suggest_low_confidence_to_auto_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    correction = {"message": "Use docker for testing", "correction_type": "correction", "confidence": 0.60}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "memory" in result[0]
    assert "environment.md" in result[0]
    assert result[1] == 0.60


def test_suggest_no_match_returns_none(tmp_path):
    correction = {"message": "x", "correction_type": "correction", "confidence": 0.80}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is None


# --- suggest_auto_memory_topic ---


def test_topic_model_preferences():
    assert suggest_auto_memory_topic("Use claude-4 model") == "model-preferences"


def test_topic_tool_usage():
    assert suggest_auto_memory_topic("Configure the MCP plugin") == "tool-usage"


def test_topic_coding_style():
    assert suggest_auto_memory_topic("Use 2-space indent formatting") == "coding-style"


def test_topic_environment():
    assert suggest_auto_memory_topic("Set up docker container") == "environment"


def test_topic_workflow():
    assert suggest_auto_memory_topic("Run tests before commit") == "workflow"


def test_topic_debugging():
    assert suggest_auto_memory_topic("Add debug log statements") == "debugging"


def test_topic_general_no_match():
    assert suggest_auto_memory_topic("Use bun") == "general"


def test_topic_highest_score_wins():
    # "commit" -> workflow, "test" -> workflow (2 hits)
    # "docker" -> environment (1 hit)
    assert suggest_auto_memory_topic("commit test docker") == "workflow"


# --- read_auto_memory ---


def test_read_auto_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    project = "/test/proj"
    encoded = "test-proj"
    mem_dir = tmp_path / ".claude" / "projects" / encoded / "memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "workflow.md").write_text("wf notes")
    (mem_dir / "general.md").write_text("general notes")
    entries = read_auto_memory(project)
    assert len(entries) == 2
    topics = {e["topic"] for e in entries}
    assert "workflow" in topics
    assert "general" in topics


def test_read_auto_memory_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    entries = read_auto_memory("/nonexistent/path")
    assert entries == []


# --- split_memory_sections ---


def test_split_memory_sections_basic():
    """基本的なセクション分割。"""
    content = "## Section A\n\nContent A\n\n## Section B\n\nContent B\n"
    sections = split_memory_sections(content, "test.md")
    assert len(sections) == 2
    assert sections[0]["heading"] == "Section A"
    assert "Content A" in sections[0]["content"]
    assert sections[1]["heading"] == "Section B"
    assert "Content B" in sections[1]["content"]


def test_split_memory_sections_header():
    """見出しなし先頭が _header として扱われる。"""
    content = "Preamble text\n\n## Section\n\nContent\n"
    sections = split_memory_sections(content, "test.md")
    assert len(sections) == 2
    assert sections[0]["heading"] == "_header"
    assert "Preamble" in sections[0]["content"]
    assert sections[1]["heading"] == "Section"


def test_split_memory_sections_empty():
    """空コンテンツでは空リストを返す。"""
    sections = split_memory_sections("", "test.md")
    assert sections == []


def test_split_memory_sections_no_headings():
    """見出しがない場合は全体が _header セクションになる。"""
    content = "Just some text\nwith multiple lines\n"
    sections = split_memory_sections(content, "test.md")
    assert len(sections) == 1
    assert sections[0]["heading"] == "_header"


def test_split_memory_sections_line_range():
    """line_range が正しく設定される。"""
    content = "## A\nLine 2\nLine 3\n## B\nLine 5\n"
    sections = split_memory_sections(content, "test.md")
    assert sections[0]["line_range"][0] == 1
    assert sections[1]["line_range"][0] == 4


def test_split_memory_sections_h3_not_split():
    """### は分割境界にならない。"""
    content = "## Main\n\n### Sub\n\nContent\n"
    sections = split_memory_sections(content, "test.md")
    assert len(sections) == 1
    assert "Sub" in sections[0]["content"]


# --- detect_project_signals ---


def test_project_signal_skill_name(tmp_path):
    """プロジェクト固有スキル名がメッセージに含まれる場合 True。"""
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /channel-routing: Bot設定。Trigger: チャンネル\n")
    assert detect_project_signals("/channel-routing スキルを使うべきだった", project_root=tmp_path) is True


def test_project_signal_path_exists(tmp_path):
    """プロジェクト内の実在パスがメッセージに含まれる場合 True。"""
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /test: test\n")
    src_dir = tmp_path / "src" / "api"
    src_dir.mkdir(parents=True)
    assert detect_project_signals("src/api/ のファイルを変更する際は", project_root=tmp_path) is True


def test_project_signal_generic(tmp_path):
    """プロジェクト固有シグナルがない場合 False。"""
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /test: test\n")
    assert detect_project_signals("タスクが変わったらスキルを確認する", project_root=tmp_path) is False


# --- suggest_claude_file with project signals ---


def test_suggest_project_specific_skill(tmp_path, monkeypatch):
    """プロジェクト固有スキル名を含む correction が .claude/rules/ にルーティングされる。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /channel-routing: Bot設定。Trigger: チャンネル\n")
    correction = {"message": "/channel-routing は always 使うべき", "correction_type": "correction", "confidence": 0.90}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    # プロジェクト固有シグナルにより .claude/rules/ にルーティング（always キーワードより優先）
    assert ".claude/rules/" in result[0]


def test_suggest_generic_always_no_project_signal(tmp_path, monkeypatch):
    """プロジェクト固有シグナルなし + always → global にルーティング。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /test: test\n")
    correction = {"message": "タスクが変わったら always スキルを確認する", "correction_type": "explicit", "confidence": 0.90}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "CLAUDE.md" in result[0]
    assert result[1] == 0.80


def test_suggest_guardrail_overrides_project_signal(tmp_path, monkeypatch):
    """guardrail は project signal より優先。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /channel-routing: Bot設定。Trigger: チャンネル\n")
    correction = {"message": "/channel-routing は使わない", "correction_type": "guardrail", "guardrail": True, "confidence": 0.90}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "guardrails.md" in result[0]


# ══════════════════════════════════════════════════════
# detect_side_effect_correction
# ══════════════════════════════════════════════════════


class TestDetectSideEffectCorrection:
    def test_ja_keyword_side_effect(self):
        assert detect_side_effect_correction("副作用を確認していなかった") is True

    def test_ja_keyword_residual(self):
        assert detect_side_effect_correction("データが残留していた") is True

    def test_ja_keyword_unintended(self):
        assert detect_side_effect_correction("意図しない変更が発生") is True

    def test_ja_keyword_recursive(self):
        assert detect_side_effect_correction("再帰的トリガーが発火した") is True

    def test_en_keyword_side_effect(self):
        assert detect_side_effect_correction("unintended side effect found") is True

    def test_en_keyword_leftover(self):
        assert detect_side_effect_correction("leftover data in the database") is True

    def test_compound_pending_table(self):
        assert detect_side_effect_correction("pending テーブルに残留していた") is True

    def test_compound_pending_residual(self):
        assert detect_side_effect_correction("pending 状態のデータが残留") is True

    def test_pending_alone_no_match(self):
        """「pending」単体ではマッチしない。"""
        assert detect_side_effect_correction("pending の状態を確認") is False

    def test_recursive_alone_no_match(self):
        """「再帰」単体ではマッチしない（「再帰的」のみ許可）。"""
        assert detect_side_effect_correction("再帰関数を修正した") is False

    def test_no_keywords(self):
        assert detect_side_effect_correction("テストを追加してください") is False

    def test_empty_message(self):
        assert detect_side_effect_correction("") is False


# ══════════════════════════════════════════════════════
# suggest_claude_file: 副作用ルーティング統合テスト
# ══════════════════════════════════════════════════════


def test_suggest_side_effect_routing(tmp_path, monkeypatch):
    """副作用キーワードを含む correction が verification.md にルーティングされる。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /test: test\n")
    correction = {"message": "副作用を確認していなかった", "correction_type": "correction", "confidence": 0.90}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "verification.md" in result[0]
    assert result[1] == 0.85


def test_suggest_side_effect_after_project_signals(tmp_path, monkeypatch):
    """project signals が True なら副作用チェックはスキップされる。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /channel-routing: Bot設定。Trigger: 副作用\n")
    correction = {"message": "/channel-routing で副作用が発生", "correction_type": "correction", "confidence": 0.90}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    # project signals が優先 → project-specific.md
    assert "project-specific.md" in result[0]


def test_suggest_guardrail_overrides_side_effect(tmp_path, monkeypatch):
    """guardrail は副作用チェックより優先。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    correction = {"message": "副作用を確認しない", "correction_type": "guardrail", "guardrail": True, "confidence": 0.90}
    result = suggest_claude_file(correction, project_root=tmp_path)
    assert result is not None
    assert "guardrails.md" in result[0]
