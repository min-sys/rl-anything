#!/usr/bin/env python3
"""detect_behavior_patterns の組み込み Agent フィルタリング統合テスト。"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

PLUGIN_ROOT = SCRIPTS_DIR.parent.parent.parent
HOOKS_DIR = PLUGIN_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import discover


def _make_usage_jsonl(tmp_path: Path, records: list[dict]) -> Path:
    """テスト用 usage.jsonl を作成。"""
    filepath = tmp_path / "usage.jsonl"
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def _usage_record(skill: str, count: int = 1, parent_skill=None, project=None) -> list[dict]:
    """指定スキルの usage レコードを count 個生成。"""
    return [
        {"skill_name": skill, "parent_skill": parent_skill, "prompt": f"do {skill} #{i}", "project": project}
        for i in range(count)
    ]


class TestBuiltinAgentFiltering:
    """組み込み Agent が agent_usage_summary に分離されるテスト。"""

    def test_builtin_agent_in_summary_not_main(self, tmp_path):
        """Agent:Explore は agent_usage_summary に含まれ、メインランキングに含まれない。"""
        records = _usage_record("Agent:Explore", 10)
        _make_usage_jsonl(tmp_path, records)

        with patch.object(discover, "DATA_DIR", tmp_path), \
             patch.object(discover, "_load_classify_usage_skill", return_value=(lambda s: False, lambda s: None)), \
             patch.object(discover, "load_suppression_list", return_value=set()):
            patterns = discover.detect_behavior_patterns(threshold=3)

        main_patterns = [p for p in patterns if p["type"] == "behavior"]
        summary = [p for p in patterns if p["type"] == "agent_usage_summary"]

        assert not any(p["pattern"] == "Agent:Explore" for p in main_patterns)
        assert len(summary) == 1
        assert summary[0]["suggestion"] == "info_only"
        assert "Agent:Explore" in summary[0]["agent_breakdown"]
        assert summary[0]["agent_breakdown"]["Agent:Explore"]["count"] == 10

    def test_multiple_builtin_agents_aggregated(self, tmp_path):
        """複数の組み込み Agent が1つの agent_usage_summary に集約される。"""
        records = _usage_record("Agent:Explore", 8) + _usage_record("Agent:Plan", 6)
        _make_usage_jsonl(tmp_path, records)

        with patch.object(discover, "DATA_DIR", tmp_path), \
             patch.object(discover, "_load_classify_usage_skill", return_value=(lambda s: False, lambda s: None)), \
             patch.object(discover, "load_suppression_list", return_value=set()):
            patterns = discover.detect_behavior_patterns(threshold=3)

        summary = [p for p in patterns if p["type"] == "agent_usage_summary"]
        assert len(summary) == 1
        assert summary[0]["count"] == 14
        assert "Agent:Explore" in summary[0]["agent_breakdown"]
        assert "Agent:Plan" in summary[0]["agent_breakdown"]


class TestCustomAgentInMainRanking:
    """カスタム Agent がメインランキングに残るテスト。"""

    def test_custom_project_agent_in_main(self, tmp_path):
        """カスタム project Agent はメインランキングに skill_candidate として含まれる。"""
        records = _usage_record("Agent:my-custom", 7, project="project")
        _make_usage_jsonl(tmp_path, records)

        # カスタム Agent ディレクトリをセットアップ
        project_root = tmp_path / "project"
        agents_dir = project_root / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "my-custom.md").write_text("# my-custom")

        with patch.object(discover, "DATA_DIR", tmp_path), \
             patch.object(discover, "_load_classify_usage_skill", return_value=(lambda s: False, lambda s: None)), \
             patch.object(discover, "load_suppression_list", return_value=set()):
            patterns = discover.detect_behavior_patterns(threshold=3, project_root=project_root)

        main_patterns = [p for p in patterns if p["type"] == "behavior"]
        assert any(p["pattern"] == "Agent:my-custom" and p["suggestion"] == "skill_candidate" for p in main_patterns)

    def test_custom_agent_has_agent_type_field(self, tmp_path):
        """カスタム Agent の pattern に agent_type フィールドが付与される。"""
        records = _usage_record("Agent:my-custom", 7, project="project")
        _make_usage_jsonl(tmp_path, records)

        project_root = tmp_path / "project"
        agents_dir = project_root / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "my-custom.md").write_text("# my-custom")

        with patch.object(discover, "DATA_DIR", tmp_path), \
             patch.object(discover, "_load_classify_usage_skill", return_value=(lambda s: False, lambda s: None)), \
             patch.object(discover, "load_suppression_list", return_value=set()):
            patterns = discover.detect_behavior_patterns(threshold=3, project_root=project_root)

        custom = [p for p in patterns if p.get("pattern") == "Agent:my-custom"]
        assert len(custom) == 1
        assert custom[0]["agent_type"] == "custom_project"


class TestDetermineScope:
    """determine_scope のカスタム Agent スコープ判定テスト。"""

    def test_custom_global_scope(self):
        pattern = {"pattern": "Agent:my-agent", "agent_type": "custom_global"}
        assert discover.determine_scope(pattern) == "global"

    def test_custom_project_scope(self):
        pattern = {"pattern": "Agent:my-agent", "agent_type": "custom_project"}
        assert discover.determine_scope(pattern) == "project"

    def test_no_agent_type_falls_through(self):
        """agent_type なしの場合は既存のキーワードベース判定。"""
        pattern = {"pattern": "git-helper"}
        assert discover.determine_scope(pattern) == "global"

    def test_non_agent_pattern_unchanged(self):
        pattern = {"pattern": "react-component-gen"}
        assert discover.determine_scope(pattern) == "project"
