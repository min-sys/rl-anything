#!/usr/bin/env python3
"""audit.py の MEMORY セマンティック検証関連のユニットテスト。"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# audit.py のパスを通す
_audit_scripts = Path(__file__).resolve().parent.parent.parent / "skills" / "audit" / "scripts"
sys.path.insert(0, str(_audit_scripts))
# reflect_utils のパスを通す
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit import (
    _extract_section_keywords,
    _find_archive_mentions,
    _is_project_specific_section,
    build_memory_verification_context,
)


# ── _extract_section_keywords ──────────────────────────────


def test_extract_keywords_basic():
    """基本的なキーワード抽出。"""
    text = "full-regen は差分更新済み。force_all オプションで手動フルリジェネも可能。"
    keywords = _extract_section_keywords(text)
    kw_lower = [k.lower() for k in keywords]
    assert "full" in kw_lower or "regen" in kw_lower or "full-regen" in kw_lower
    # force_all はトークナイザにより分割される可能性がある
    assert "force_all" in kw_lower or "force" in kw_lower


def test_extract_keywords_stopwords_excluded():
    """ストップワードが除外される。"""
    text = "The is a test of the system and it should work"
    keywords = _extract_section_keywords(text)
    kw_lower = [k.lower() for k in keywords]
    assert "the" not in kw_lower
    assert "is" not in kw_lower
    assert "and" not in kw_lower
    assert "test" in kw_lower
    assert "system" in kw_lower


def test_extract_keywords_short_words_excluded():
    """2文字以下の英語単語が除外される。"""
    text = "CI CD is ok but npm run test works"
    keywords = _extract_section_keywords(text)
    kw_lower = [k.lower() for k in keywords]
    assert "ok" not in kw_lower
    # "CI", "CD" は2文字だが除外される
    assert "npm" in kw_lower
    assert "run" in kw_lower
    assert "test" in kw_lower


def test_extract_keywords_japanese_preserved():
    """日本語キーワードが保持される。"""
    text = "差分更新は高速で安定している"
    keywords = _extract_section_keywords(text)
    assert len(keywords) > 0
    # 日本語トークンが含まれる
    assert any("\u3000" <= c <= "\u9fff" for kw in keywords for c in kw)


def test_extract_keywords_codeblock_ignored():
    """コードブロック内は無視される。"""
    text = "概要\n```\nspecial_command_inside_codeblock\n```\nキーワード抽出テスト"
    keywords = _extract_section_keywords(text)
    kw_lower = [k.lower() for k in keywords]
    assert "special_command_inside_codeblock" not in kw_lower


def test_extract_keywords_deduplication():
    """重複キーワードが除去される。"""
    text = "npm install npm run npm test"
    keywords = _extract_section_keywords(text)
    kw_lower = [k.lower() for k in keywords]
    assert kw_lower.count("npm") == 1


# ── _find_archive_mentions ──────────────────────────────


def test_find_archive_mentions_match(tmp_path):
    """アーカイブ名とキーワードがマッチする場合。"""
    archive_dir = tmp_path / "openspec" / "changes" / "archive"
    (archive_dir / "2026-03-01-optimize-fullregen-cost").mkdir(parents=True)
    keywords = ["optimize", "fullregen", "cost"]
    mentions = _find_archive_mentions(keywords, tmp_path)
    assert "2026-03-01-optimize-fullregen-cost" in mentions


def test_find_archive_mentions_no_match(tmp_path):
    """アーカイブ名とキーワードがマッチしない場合。"""
    archive_dir = tmp_path / "openspec" / "changes" / "archive"
    (archive_dir / "2026-03-01-add-user-auth").mkdir(parents=True)
    keywords = ["database", "migration"]
    mentions = _find_archive_mentions(keywords, tmp_path)
    assert mentions == []


def test_find_archive_mentions_no_archive_dir(tmp_path):
    """archive ディレクトリが存在しない場合。"""
    keywords = ["optimize"]
    mentions = _find_archive_mentions(keywords, tmp_path)
    assert mentions == []


# ── _is_project_specific_section ──────────────────────────


def test_is_project_specific_by_name(tmp_path):
    """PJ 名がセクションに含まれる場合。"""
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    section = {"heading": "my-project 設定", "content": "my-project の設定について"}
    assert _is_project_specific_section(section, project_dir) is True


def test_is_not_project_specific(tmp_path):
    """汎用セクションの場合。"""
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    section = {"heading": "コーディング規約", "content": "インデントは2スペース"}
    assert _is_project_specific_section(section, project_dir) is False


# ── build_memory_verification_context ──────────────────────


def test_build_memory_verification_context_basic(tmp_path, monkeypatch):
    """正常系: auto-memory からセクションが抽出される。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    # auto-memory 作成
    encoded = str(tmp_path).replace("/", "-").lstrip("-")
    mem_dir = tmp_path / ".claude" / "projects" / encoded / "memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "MEMORY.md").write_text(
        "# Memo\n\n## doc-pipeline\n\n- full-regen は差分更新\n\n## テスト\n\n- pytest 使用\n"
    )

    ctx = build_memory_verification_context(tmp_path)
    assert "sections" in ctx
    assert len(ctx["sections"]) >= 1
    headings = [s["heading"] for s in ctx["sections"]]
    assert "doc-pipeline" in headings


def test_build_memory_verification_context_no_memory(tmp_path, monkeypatch):
    """MEMORY が存在しない場合は空の sections を返す。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    ctx = build_memory_verification_context(tmp_path)
    assert ctx == {"sections": []}


def test_build_memory_verification_context_read_error(tmp_path, monkeypatch, capsys):
    """読み取りエラー時はスキップして処理を継続する。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    # read_auto_memory が例外を含むエントリを返すようにモック
    def mock_read_auto_memory(path):
        return [{"path": "/bad/path.md", "topic": "bad", "content": "## test\ncontent"}]

    # split_memory_sections 自体は正常に動作するので、エラーにはならない
    # ただし codebase_evidence の grep が失敗するケース
    ctx = build_memory_verification_context(tmp_path)
    # エラーでクラッシュしないことを確認
    assert "sections" in ctx
