"""skill_triggers.py のユニットテスト。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from skill_triggers import extract_skill_triggers, normalize_skill_name


@pytest.fixture
def claude_md_with_triggers(tmp_path):
    """トリガーワード付きの CLAUDE.md。"""
    content = """\
# My Project

## Skills

- /channel-routing: チャンネルごとのBot設定を管理。トリガー: channel routing, チャンネルマッピング, bot追加
- /deploy-check: デプロイ前の確認チェック。Trigger: deploy check, デプロイ確認
- /my-skill: 説明文のみ

## Other Section

Something else.
"""
    path = tmp_path / "CLAUDE.md"
    path.write_text(content)
    return path


@pytest.fixture
def claude_md_trigger_variations(tmp_path):
    """トリガーワード記法バリエーション。"""
    content = """\
# Project

## Skills

- /skill-a: 説明。トリガー: word1, word2
- /skill-b: 説明。トリガーワード: word3, word4
- /skill-c: 説明。Trigger: word5, word6
- /skill-d: 説明。triggers: word7, word8
"""
    path = tmp_path / "CLAUDE.md"
    path.write_text(content)
    return path


def test_extract_with_triggers(claude_md_with_triggers):
    result = extract_skill_triggers(claude_md_with_triggers)
    assert len(result) == 3

    by_skill = {r["skill"]: r for r in result}
    assert set(by_skill["channel-routing"]["triggers"]) == {"channel routing", "チャンネルマッピング", "bot追加"}
    assert set(by_skill["deploy-check"]["triggers"]) == {"deploy check", "デプロイ確認"}


def test_fallback_when_no_triggers(claude_md_with_triggers):
    result = extract_skill_triggers(claude_md_with_triggers)
    by_skill = {r["skill"]: r for r in result}
    assert by_skill["my-skill"]["triggers"] == ["my-skill"]


def test_trigger_format_variations(claude_md_trigger_variations):
    result = extract_skill_triggers(claude_md_trigger_variations)
    assert len(result) == 4

    by_skill = {r["skill"]: r for r in result}
    assert by_skill["skill-a"]["triggers"] == ["word1", "word2"]
    assert by_skill["skill-b"]["triggers"] == ["word3", "word4"]
    assert by_skill["skill-c"]["triggers"] == ["word5", "word6"]
    assert by_skill["skill-d"]["triggers"] == ["word7", "word8"]


def test_claude_md_not_found(tmp_path):
    result = extract_skill_triggers(tmp_path / "nonexistent.md")
    assert result == []


def test_extract_from_project_root(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /test-skill: test. Trigger: testing\n")
    result = extract_skill_triggers(project_root=tmp_path)
    assert len(result) == 1
    assert result[0]["skill"] == "test-skill"
    assert result[0]["triggers"] == ["testing"]


def test_normalize_skill_name():
    assert normalize_skill_name("/channel-routing") == "channel-routing"
    assert normalize_skill_name("rl-anything:channel-routing") == "channel-routing"
    assert normalize_skill_name("channel-routing") == "channel-routing"
    assert normalize_skill_name("/plugin:skill") == "skill"


def test_no_skills_section(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Project\n\nNo skills here.\n")
    result = extract_skill_triggers(tmp_path / "CLAUDE.md")
    assert result == []
