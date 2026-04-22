"""load_user_config() のユニットテスト。"""
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common


class TestLoadUserConfig:
    """load_user_config() のテスト。"""

    def test_defaults_when_no_env_vars(self):
        """環境変数なしでデフォルト値を返す。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = common.load_user_config()
        assert config["auto_trigger"] is True
        assert config["evolve_interval_days"] == 7
        assert config["audit_interval_days"] == 30
        assert config["min_sessions"] == 10
        assert config["cooldown_hours"] == 24
        assert config["language"] == "ja"

    def test_valid_overrides(self):
        """全項目を環境変数でオーバーライド。"""
        env = {
            "CLAUDE_PLUGIN_OPTION_auto_trigger": "false",
            "CLAUDE_PLUGIN_OPTION_evolve_interval_days": "14",
            "CLAUDE_PLUGIN_OPTION_audit_interval_days": "60",
            "CLAUDE_PLUGIN_OPTION_min_sessions": "5",
            "CLAUDE_PLUGIN_OPTION_cooldown_hours": "12",
            "CLAUDE_PLUGIN_OPTION_language": "en",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            config = common.load_user_config()
        assert config["auto_trigger"] is False
        assert config["evolve_interval_days"] == 14
        assert config["audit_interval_days"] == 60
        assert config["min_sessions"] == 5
        assert config["cooldown_hours"] == 12
        assert config["language"] == "en"

    def test_invalid_number_falls_back_to_default(self):
        """非数値が渡された場合はデフォルトにフォールバック。"""
        env = {
            "CLAUDE_PLUGIN_OPTION_evolve_interval_days": "not_a_number",
            "CLAUDE_PLUGIN_OPTION_min_sessions": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            config = common.load_user_config()
        assert config["evolve_interval_days"] == 7  # default
        assert config["min_sessions"] == 10  # default

    def test_boolean_parsing(self):
        """文字列の true/false が正しく bool にパースされる。"""
        for true_val in ("true", "True", "TRUE", "1", "yes"):
            with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_OPTION_auto_trigger": true_val}):
                config = common.load_user_config()
                assert config["auto_trigger"] is True, f"Expected True for '{true_val}'"

        for false_val in ("false", "False", "FALSE", "0", "no"):
            with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_OPTION_auto_trigger": false_val}):
                config = common.load_user_config()
                assert config["auto_trigger"] is False, f"Expected False for '{false_val}'"

    def test_partial_override(self):
        """一部の項目のみオーバーライドし、残りはデフォルト。"""
        env = {"CLAUDE_PLUGIN_OPTION_cooldown_hours": "48"}
        with mock.patch.dict(os.environ, env, clear=False):
            config = common.load_user_config()
        assert config["cooldown_hours"] == 48
        assert config["auto_trigger"] is True  # default
        assert config["language"] == "ja"  # default

    def test_cleanup_tmp_prefixes_default(self):
        """cleanup_tmp_prefixes はデフォルトで "rl-anything-" 単独（安全側）。

        PR #70 dogfood で検出した Claude Code runtime (`/tmp/claude-<uid>`) や
        MCP bridge (`/tmp/claude-mcp-*`) を削除候補化する wide prefix バグの
        再発防止として、デフォルトは rl-anything 名前空間のみに絞る。
        """
        with mock.patch.dict(os.environ, {}, clear=True):
            config = common.load_user_config()
        assert config["cleanup_tmp_prefixes"] == "rl-anything-"

    def test_cleanup_tmp_prefixes_override(self):
        """cleanup_tmp_prefixes は環境変数で上書き可能（カンマ区切りで複数指定）。"""
        env = {
            "CLAUDE_PLUGIN_OPTION_cleanup_tmp_prefixes": "rl-anything-,claude-sandbox-,gstack-scratch-",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            config = common.load_user_config()
        assert config["cleanup_tmp_prefixes"] == "rl-anything-,claude-sandbox-,gstack-scratch-"
