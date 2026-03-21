#!/usr/bin/env python3
"""usage-scope-classification のテスト。

_load_plugin_skill_map, aggregate_usage, aggregate_plugin_usage,
build_gstack_analytics_section, detect_behavior_patterns のプラグインフィルタをテストする。
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "discover" / "scripts"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

import audit
import discover


# ---------- fixtures ----------

@pytest.fixture(autouse=True)
def reset_cache():
    """各テスト前にキャッシュをリセット。"""
    audit._plugin_skill_map_cache = None
    yield
    audit._plugin_skill_map_cache = None


def _setup_fake_plugins(tmp_path):
    """tmp_path にフェイクプラグイン構造を作成し、Path.home をモックする context manager を返す。"""
    home_dir = tmp_path / "home"

    # openspec プラグイン: .claude/skills/ レイアウト
    openspec_dir = tmp_path / "openspec"
    for skill in ["openspec-propose", "openspec-refine", "openspec-apply", "openspec-verify", "openspec-archive"]:
        (openspec_dir / ".claude" / "skills" / skill).mkdir(parents=True)

    # rl-anything プラグイン: skills/ レイアウト
    rl_dir = tmp_path / "rl-anything"
    for skill in ["audit", "discover", "evolve"]:
        (rl_dir / "skills" / skill).mkdir(parents=True)

    plugins_data = {
        "plugins": {
            "openspec@openspec": [{"installPath": str(openspec_dir)}],
            "rl-anything@rl-anything": [{"installPath": str(rl_dir)}],
        }
    }

    (home_dir / ".claude" / "plugins").mkdir(parents=True)
    (home_dir / ".claude" / "plugins" / "installed_plugins.json").write_text(
        json.dumps(plugins_data), encoding="utf-8"
    )
    return patch("pathlib.Path.home", return_value=home_dir)


# ---------- _load_plugin_skill_map tests ----------

class TestLoadPluginSkillMap:
    def test_returns_dict_with_plugin_names(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            result = audit._load_plugin_skill_map()
        assert isinstance(result, dict)
        assert result.get("openspec-propose") == "openspec"
        assert result.get("openspec-refine") == "openspec"
        assert result.get("audit") == "rl-anything"
        assert result.get("discover") == "rl-anything"

    def test_scans_both_layouts(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            result = audit._load_plugin_skill_map()
        # openspec は .claude/skills/ レイアウト
        assert "openspec-propose" in result
        # rl-anything は skills/ レイアウト
        assert "evolve" in result

    def test_backward_compat_wrapper(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            names = audit._load_plugin_skill_names()
        assert isinstance(names, frozenset)
        assert "openspec-propose" in names
        assert "audit" in names

    def test_empty_on_missing_file(self, tmp_path):
        home_dir = tmp_path / "empty_home"
        home_dir.mkdir()
        with patch("pathlib.Path.home", return_value=home_dir):
            result = audit._load_plugin_skill_map()
        assert result == {}

    def test_caching(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            result1 = audit._load_plugin_skill_map()
            result2 = audit._load_plugin_skill_map()
        assert result1 is result2


# ---------- classify_usage_skill tests ----------

class TestClassifyUsageSkill:
    def test_exact_match(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            # openspec-propose は openspec@openspec プラグイン → "openspec"
            assert audit.classify_usage_skill("openspec-propose") == "openspec"
            # audit は rl-anything@rl-anything プラグイン → "rl-anything"
            assert audit.classify_usage_skill("audit") == "rl-anything"

    def test_prefix_match(self, tmp_path):
        """旧スキル名が prefix マッチで検出される。"""
        with _setup_fake_plugins(tmp_path):
            result = audit.classify_usage_skill("openspec-unknown-new")
        # openspec- prefix が openspec プラグインから自動推定される
        assert result == "openspec"

    def test_agent_prefix(self, tmp_path):
        """Agent:openspec-uiux-reviewer のようなパターンが検出される。"""
        with _setup_fake_plugins(tmp_path):
            result = audit.classify_usage_skill("Agent:openspec-propose")
        assert result == "openspec"

    def test_no_match(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            assert audit.classify_usage_skill("my-custom-skill") is None
            assert audit.classify_usage_skill("building-ui") is None


# ---------- aggregate_usage tests ----------

class TestAggregateUsage:
    def _make_records(self):
        return [
            {"skill_name": "openspec-propose"},
            {"skill_name": "openspec-propose"},
            {"skill_name": "openspec-refine"},
            {"skill_name": "building-ui"},
            {"skill_name": "building-ui"},
            {"skill_name": "building-ui"},
            {"skill_name": "Agent:Explore"},  # builtin
        ]

    def test_without_plugin_filter(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            result = audit.aggregate_usage(self._make_records(), exclude_plugins=False)
        assert "building-ui" in result
        assert "openspec-propose" in result
        assert "Agent:Explore" not in result

    def test_with_plugin_filter(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            result = audit.aggregate_usage(self._make_records(), exclude_plugins=True)
        assert "building-ui" in result
        assert result["building-ui"] == 3
        assert "openspec-propose" not in result
        assert "openspec-refine" not in result

    def test_aggregate_plugin_usage(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            result = audit.aggregate_plugin_usage(self._make_records())
        assert result.get("openspec") == 3
        assert "rl-anything" not in result


# ---------- build_gstack_analytics_section tests ----------

class TestBuildGstackAnalytics:
    def _make_gstack_records(self):
        records = []
        for i in range(3):
            records.append({
                "skill_name": "office-hours",
                "session_id": f"session-{i}",
            })
        for i in range(10):
            records.append({
                "skill_name": "ship",
                "session_id": f"session-{i % 3}",
            })
        records.append({
            "skill_name": "retro",
            "session_id": "session-0",
        })
        return records

    def test_returns_lines_with_funnel(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            result = audit.build_gstack_analytics_section(self._make_gstack_records())
        assert any("gstack Workflow Analytics" in line for line in result)
        assert any("Funnel:" in line for line in result)
        assert any("plan(3)" in line for line in result)

    def test_completion_rate(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            result = audit.build_gstack_analytics_section(self._make_gstack_records())
        assert any("33%" in line for line in result)

    def test_empty_when_no_gstack(self, tmp_path):
        home_dir = tmp_path / "empty_home"
        home_dir.mkdir()
        with patch("pathlib.Path.home", return_value=home_dir):
            result = audit.build_gstack_analytics_section([])
        assert result == []

    def test_phase_efficiency(self, tmp_path):
        with _setup_fake_plugins(tmp_path):
            result = audit.build_gstack_analytics_section(self._make_gstack_records())
        assert any("ship:" in line for line in result)


# ---------- discover plugin filtering tests ----------

class TestDiscoverPluginFilter:
    def test_plugin_skills_excluded(self, tmp_path):
        """プラグインスキルがメインランキングから除外されることを確認。"""
        usage_records = []
        for _ in range(20):
            usage_records.append({"skill_name": "openspec-propose"})
        for _ in range(10):
            usage_records.append({"skill_name": "my-custom-skill"})

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "usage.jsonl").write_text(
            "\n".join(json.dumps(r) for r in usage_records),
            encoding="utf-8"
        )

        # モック: openspec-propose → plugin
        def mock_is_plugin(skill_name):
            return skill_name == "openspec-propose"

        def mock_classify(skill_name):
            if skill_name == "openspec-propose":
                return "openspec"
            return None

        with patch.object(discover, "DATA_DIR", data_dir), \
             patch.object(discover, "_load_classify_usage_skill", return_value=(mock_is_plugin, mock_classify)), \
             patch.object(discover, "load_suppression_list", return_value=set()):
            patterns = discover.detect_behavior_patterns(threshold=5)

        behavior_patterns = [p for p in patterns if p["type"] == "behavior"]
        behavior_names = {p["pattern"] for p in behavior_patterns}
        assert "openspec-propose" not in behavior_names
        assert "my-custom-skill" in behavior_names

        summaries = [p for p in patterns if p["type"] == "plugin_summary"]
        assert len(summaries) == 1
        assert summaries[0]["plugin_breakdown"]["openspec"] == 20
