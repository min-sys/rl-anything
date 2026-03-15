"""skill_origin モジュールのユニットテスト。"""
import json
import os
from pathlib import Path
from unittest import mock

import pytest

# テスト対象モジュールのインポートパスを設定
import sys

_lib_dir = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(_lib_dir))

from skill_origin import (
    _load_plugin_skill_map,
    classify_skill_origin,
    is_protected_skill,
    suggest_local_alternative,
    generate_protection_warning,
    format_pitfall_candidate,
    invalidate_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """各テスト前にキャッシュをクリアする。"""
    invalidate_cache()
    yield
    invalidate_cache()


# ---------- origin 判定 ----------

class TestClassifySkillOrigin:
    """classify_skill_origin のテスト。"""

    def test_nonexistent_path_returns_custom(self, tmp_path):
        """存在しないパスは custom を返す。"""
        result = classify_skill_origin(tmp_path / "does" / "not" / "exist")
        assert result == "custom"

    def test_project_custom_skill(self, tmp_path):
        """プロジェクト配下のカスタムスキルは custom を返す。"""
        skill_dir = tmp_path / ".claude" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        result = classify_skill_origin(skill_dir)
        assert result == "custom"

    def test_global_skill(self, tmp_path):
        """~/.claude/skills/ 配下は global を返す。"""
        with mock.patch("skill_origin.Path.home", return_value=tmp_path):
            global_skill = tmp_path / ".claude" / "skills" / "my-global"
            global_skill.mkdir(parents=True)
            result = classify_skill_origin(global_skill)
            assert result == "global"

    def test_plugin_skill_via_installed_plugins(self, tmp_path):
        """installed_plugins.json 経由でプラグインスキルを判定。"""
        # セットアップ: installed_plugins.json
        plugins_dir = tmp_path / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)

        install_path = tmp_path / "plugins" / "rl-anything"
        skill_dir = install_path / ".claude" / "skills" / "openspec-verify"
        skill_dir.mkdir(parents=True)

        data = {
            "plugins": {
                "rl-anything@marketplace": [{
                    "installPath": str(install_path),
                }]
            }
        }
        (plugins_dir / "installed_plugins.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

        # プロジェクト側にインストール済みスキル名と同名のディレクトリ
        proj_skill = tmp_path / "project" / ".claude" / "skills" / "openspec-verify"
        proj_skill.mkdir(parents=True)

        with mock.patch("skill_origin.Path.home", return_value=tmp_path):
            with mock.patch("skill_origin._installed_plugins_path",
                            return_value=plugins_dir / "installed_plugins.json"):
                result = classify_skill_origin(proj_skill)
                assert result == "plugin"


# ---------- 保護チェック ----------

class TestIsProtectedSkill:
    """is_protected_skill のテスト。"""

    def test_custom_skill_not_protected(self, tmp_path):
        """カスタムスキルは保護されない。"""
        skill_dir = tmp_path / ".claude" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        assert is_protected_skill(skill_dir) is False

    def test_nonexistent_not_protected(self, tmp_path):
        """存在しないパスは保護されない。"""
        assert is_protected_skill(tmp_path / "nonexistent") is False


# ---------- 代替先提案 ----------

class TestSuggestLocalAlternative:
    """suggest_local_alternative のテスト。"""

    def test_returns_references_path(self, tmp_path):
        """代替先パスを返す。"""
        path, exists = suggest_local_alternative("openspec-verify", tmp_path)
        assert "openspec-verify/references/pitfalls.md" in path
        assert exists is False

    def test_existing_file(self, tmp_path):
        """既存ファイルがある場合は exists=True。"""
        refs = tmp_path / ".claude" / "skills" / "my-skill" / "references"
        refs.mkdir(parents=True)
        (refs / "pitfalls.md").write_text("# Pitfalls", encoding="utf-8")
        path, exists = suggest_local_alternative("my-skill", tmp_path)
        assert exists is True


# ---------- 警告生成 ----------

class TestGenerateProtectionWarning:
    """generate_protection_warning のテスト。"""

    def test_warning_contains_skill_name(self):
        """警告にスキル名が含まれる。"""
        warning = generate_protection_warning("openspec-verify", "/alt/path")
        assert "openspec-verify" in warning

    def test_warning_contains_reason(self):
        """警告に保護理由が含まれる。"""
        warning = generate_protection_warning("test-skill", "/alt/path")
        assert "プラグイン由来" in warning

    def test_warning_contains_alternative(self):
        """警告に代替先パスが含まれる。"""
        alt = "/project/.claude/skills/test/references/pitfalls.md"
        warning = generate_protection_warning("test-skill", alt)
        assert alt in warning


# ---------- Candidate フォーマット ----------

class TestFormatPitfallCandidate:
    """format_pitfall_candidate のテスト。"""

    def test_format_contains_title(self):
        """フォーマットにタイトルが含まれる。"""
        result = format_pitfall_candidate(
            title="テストの問題",
            context="テストコンテキスト",
            pattern="パターン",
            solution="解決策",
            date="2026-03-15",
        )
        assert "## Candidate: テストの問題" in result
        assert "Candidate" in result
        assert "2026-03-15" in result


# ---------- Graceful Degradation ----------

class TestGracefulDegradation:
    """installed_plugins.json の異常状態に対するフォールバック。"""

    def test_invalid_json(self, tmp_path):
        """不正 JSON → 空 map を返す。"""
        plugins_dir = tmp_path / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)
        (plugins_dir / "installed_plugins.json").write_text(
            "{ invalid json }", encoding="utf-8"
        )
        with mock.patch("skill_origin._installed_plugins_path",
                        return_value=plugins_dir / "installed_plugins.json"):
            result = _load_plugin_skill_map()
            assert result == {}

    def test_unknown_version(self, tmp_path):
        """未知の version → 空 map を返す。"""
        plugins_dir = tmp_path / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)
        data = {"version": "3.0", "plugins": {}}
        (plugins_dir / "installed_plugins.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        with mock.patch("skill_origin._installed_plugins_path",
                        return_value=plugins_dir / "installed_plugins.json"):
            result = _load_plugin_skill_map()
            assert result == {}

    def test_missing_file(self, tmp_path):
        """ファイルなし → 空 map を返す。"""
        with mock.patch("skill_origin._installed_plugins_path",
                        return_value=tmp_path / "nonexistent.json"):
            result = _load_plugin_skill_map()
            assert result == {}
