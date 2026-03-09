#!/usr/bin/env python3
"""layer_diagnose.py のユニットテスト。"""
import json
import sys
from pathlib import Path

import pytest

# layer_diagnose.py のパスを通す
_lib_dir = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(_lib_dir))

from layer_diagnose import (
    adapt_coherence_issues,
    diagnose_all_layers,
    diagnose_claudemd,
    diagnose_hooks,
    diagnose_memory,
    diagnose_rules,
)


# ── adapt_coherence_issues ──────────────────────────────


def test_adapt_coherence_orphan_rules_removed():
    """orphan_rule は廃止されたため、coherence 結果から変換されない。"""
    result = {
        "details": {
            "efficiency": {
                "orphan_rules": {"pass": False, "rules": ["/path/to/obsolete.md"]},
            },
            "consistency": {"skill_existence": {"pass": True, "missing": []}},
        }
    }
    issues = adapt_coherence_issues(result)
    orphan_issues = [i for i in issues if i["type"] == "orphan_rule"]
    assert len(orphan_issues) == 0


def test_adapt_coherence_missing_skills():
    """coherence の skill_existence.missing が claudemd_phantom_ref に変換される。"""
    result = {
        "details": {
            "consistency": {
                "skill_existence": {"pass": False, "missing": ["nonexistent-skill"]},
                "memory_paths": {"pass": True, "stale": []},
            },
            "efficiency": {"orphan_rules": {"pass": True, "rules": []}},
        }
    }
    issues = adapt_coherence_issues(result)
    assert len(issues) == 1
    assert issues[0]["type"] == "claudemd_phantom_ref"
    assert issues[0]["detail"]["name"] == "nonexistent-skill"


def test_adapt_coherence_empty():
    """問題がない場合は空リスト。"""
    result = {
        "details": {
            "consistency": {
                "skill_existence": {"pass": True, "missing": []},
                "memory_paths": {"pass": True, "stale": []},
            },
            "efficiency": {"orphan_rules": {"pass": True, "rules": []}},
        }
    }
    issues = adapt_coherence_issues(result)
    assert issues == []


# ── diagnose_rules ──────────────────────────────


def test_rules_no_orphan_detection(tmp_path):
    """orphan_rule は廃止: 参照されていないルールでも検出されない。"""
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "obsolete-rule.md").write_text("# Obsolete\nSome old rule.")
    # CLAUDE.md なし、スキルなし → 以前は孤立検出されたが、今は検出されない
    issues = diagnose_rules(tmp_path)
    orphan_issues = [i for i in issues if i["type"] == "orphan_rule"]
    assert len(orphan_issues) == 0


def test_rules_stale_reference(tmp_path):
    """ルール内のファイルパス参照先が存在しない場合に stale_rule を検出。"""
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "deploy.md").write_text("# Deploy\nscripts/deploy.sh を実行")
    # scripts/deploy.sh は存在しない

    issues = diagnose_rules(tmp_path)
    stale_issues = [i for i in issues if i["type"] == "stale_rule"]
    assert len(stale_issues) == 1
    assert stale_issues[0]["detail"]["path"] == "scripts/deploy.sh"


def test_rules_no_issues(tmp_path):
    """問題がない場合は空リスト。"""
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "my-rule.md").write_text("# My Rule\nSimple rule.")
    (tmp_path / "CLAUDE.md").write_text("# Project\nmy-rule を使う")

    issues = diagnose_rules(tmp_path)
    # orphan_rule はないが stale_rule もない
    assert all(i["type"] != "stale_rule" for i in issues)


def test_rules_coherence_result_ignored(tmp_path):
    """coherence_result は orphan 判定に使われない（orphan_rule 廃止）。"""
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "commit-version.md").write_text("# Commit Version\nbump要否")

    coherence_result = {
        "details": {
            "efficiency": {
                "orphan_rules": {"pass": False, "rules": [str(rules_dir / "commit-version.md")]},
            },
        }
    }
    issues = diagnose_rules(tmp_path, coherence_result=coherence_result)
    orphan_issues = [i for i in issues if i["type"] == "orphan_rule"]
    assert len(orphan_issues) == 0


def test_rules_stale_rule_file_relative_resolution(tmp_path):
    """ルール内のパスが参照元ファイルの親ディレクトリ基準で存在する場合は stale_rule にならない。"""
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    # references/docs-map.md は rules_dir からの相対パスとして存在する
    refs_dir = rules_dir / "references"
    refs_dir.mkdir()
    (refs_dir / "docs-map.md").write_text("# Docs Map")

    (rules_dir / "my-rule.md").write_text("# My Rule\nSee references/docs-map.md for details")

    issues = diagnose_rules(tmp_path)
    stale_issues = [i for i in issues if i["type"] == "stale_rule"]
    assert len(stale_issues) == 0


def test_rules_no_rules_dir(tmp_path):
    """rules ディレクトリがない場合は空リスト。"""
    issues = diagnose_rules(tmp_path)
    assert issues == []


# ── diagnose_memory ──────────────────────────────


def test_memory_duplicate_sections(tmp_path):
    """類似セクション名が memory_duplicate として検出される。"""
    memory_dir = tmp_path / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text(
        "## OpenSpec Changes History\n\nSome content.\n\n## OpenSpec Changes Log\n\nMore content.\n"
    )
    issues = diagnose_memory(tmp_path)
    dup_issues = [i for i in issues if i["type"] == "memory_duplicate"]
    assert len(dup_issues) == 1
    assert "OpenSpec" in dup_issues[0]["detail"]["sections"][0]


def test_memory_no_duplicate_different_sections(tmp_path):
    """異なるセクション名では重複検出されない。"""
    memory_dir = tmp_path / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text(
        "## ユーザー指示\n\n内容1\n\n## リポジトリ情報\n\n内容2\n"
    )
    issues = diagnose_memory(tmp_path)
    dup_issues = [i for i in issues if i["type"] == "memory_duplicate"]
    assert len(dup_issues) == 0


def test_memory_stale_ref_dedup(tmp_path):
    """既存 stale_ref でカバー済みのパスは stale_memory として重複検出しない。"""
    memory_dir = tmp_path / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text(
        "## Info\nscripts.lib.obsolete_module is referenced.\n"
    )

    existing_stale_refs = [
        {"detail": {"path": "scripts/lib/obsolete_module.py"}},
    ]
    issues = diagnose_memory(tmp_path, existing_stale_refs=existing_stale_refs)
    stale_issues = [i for i in issues if i["type"] == "stale_memory"]
    # stale_ref_paths にある参照は除外される
    assert len(stale_issues) == 0


def test_memory_normal(tmp_path):
    """問題がない場合は空リスト。"""
    memory_dir = tmp_path / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text("## Info\nAll good here.\n")
    issues = diagnose_memory(tmp_path)
    assert issues == []


def test_memory_no_dir(tmp_path):
    """memory ディレクトリがない場合は空リスト。"""
    issues = diagnose_memory(tmp_path)
    assert issues == []


# ── diagnose_hooks ──────────────────────────────


def test_hooks_configured(tmp_path):
    """hooks 設定がある場合は空リスト。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]}}
    (claude_dir / "settings.json").write_text(json.dumps(settings))

    issues = diagnose_hooks(tmp_path)
    assert issues == []


def test_hooks_unconfigured(tmp_path):
    """hooks 設定がない場合に hooks_unconfigured を検出。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(json.dumps({"permissions": {}}))

    issues = diagnose_hooks(tmp_path)
    assert len(issues) == 1
    assert issues[0]["type"] == "hooks_unconfigured"
    assert issues[0]["detail"]["reason"] == "no hooks configured"


def test_hooks_no_settings_file(tmp_path):
    """settings.json が存在しない場合は空リスト。"""
    issues = diagnose_hooks(tmp_path)
    assert issues == []


# ── diagnose_claudemd ──────────────────────────────


def test_claudemd_phantom_ref(tmp_path):
    """存在しないスキルが CLAUDE.md で言及されている場合に検出。"""
    skills_dir = tmp_path / ".claude" / "skills" / "real-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# Real Skill")

    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n## Skills\n\n- real-skill: exists\n- deprecated-skill: gone\n"
    )
    issues = diagnose_claudemd(tmp_path)
    phantom_issues = [i for i in issues if i["type"] == "claudemd_phantom_ref"]
    assert len(phantom_issues) == 1
    assert phantom_issues[0]["detail"]["name"] == "deprecated-skill"


def test_claudemd_plugin_skill_excluded(tmp_path):
    """プラグインスキルは phantom_ref として検出されない。"""
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n## Skills\n\n- openspec-propose: plugin skill\n"
    )
    # _get_plugin_skill_names をモックして openspec-propose を返す
    import layer_diagnose

    original = layer_diagnose._get_plugin_skill_names

    def mock_get_plugins(project_dir):
        return {"openspec-propose"}

    layer_diagnose._get_plugin_skill_names = mock_get_plugins
    try:
        issues = diagnose_claudemd(tmp_path)
        phantom_issues = [i for i in issues if i["type"] == "claudemd_phantom_ref"]
        assert len(phantom_issues) == 0
    finally:
        layer_diagnose._get_plugin_skill_names = original


def test_claudemd_missing_section(tmp_path):
    """Skills セクションがないがスキルが存在する場合に検出。"""
    skills_dir = tmp_path / ".claude" / "skills" / "my-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# My Skill")

    (tmp_path / "CLAUDE.md").write_text("# Project\n\nNo skills section here.\n")
    issues = diagnose_claudemd(tmp_path)
    missing_issues = [i for i in issues if i["type"] == "claudemd_missing_section"]
    assert len(missing_issues) == 1
    assert missing_issues[0]["detail"]["section"] == "skills"
    assert missing_issues[0]["detail"]["skill_count"] == 1


def test_claudemd_with_skills_section(tmp_path):
    """Skills セクションがあればセクション欠落は検出されない。"""
    skills_dir = tmp_path / ".claude" / "skills" / "my-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# My Skill")

    (tmp_path / "CLAUDE.md").write_text("# Project\n\n## Skills\n\n- my-skill: desc\n")
    issues = diagnose_claudemd(tmp_path)
    missing_issues = [i for i in issues if i["type"] == "claudemd_missing_section"]
    assert len(missing_issues) == 0


@pytest.mark.parametrize(
    "section_heading",
    [
        pytest.param("## Key Skills", id="key-skills"),
        pytest.param("## Available Skills", id="available-skills"),
        pytest.param("## Project Skills", id="project-skills"),
        pytest.param("## 主要スキル", id="japanese-skills"),
    ],
)
def test_claudemd_prefix_skills_section(tmp_path, section_heading):
    """prefix 付きセクション名でも Skills セクションとして認識される。"""
    skills_dir = tmp_path / ".claude" / "skills" / "my-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# My Skill")

    (tmp_path / "CLAUDE.md").write_text(
        f"# Project\n\n{section_heading}\n\n- my-skill: desc\n"
    )
    issues = diagnose_claudemd(tmp_path)
    missing_issues = [i for i in issues if i["type"] == "claudemd_missing_section"]
    assert len(missing_issues) == 0


def test_claudemd_not_exist(tmp_path):
    """CLAUDE.md が存在しない場合は空リスト。"""
    issues = diagnose_claudemd(tmp_path)
    assert issues == []


def test_claudemd_normal(tmp_path):
    """問題がない場合は空リスト。"""
    skills_dir = tmp_path / ".claude" / "skills" / "evolve"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# Evolve Skill")

    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n## Skills\n\n- evolve: desc\n"
    )

    import layer_diagnose
    original = layer_diagnose._get_plugin_skill_names
    layer_diagnose._get_plugin_skill_names = lambda pd: set()
    try:
        issues = diagnose_claudemd(tmp_path)
        assert issues == []
    finally:
        layer_diagnose._get_plugin_skill_names = original


# ── diagnose_all_layers ──────────────────────────────


def test_all_layers_integration(tmp_path):
    """全レイヤー統合テスト：各レイヤーが独立して結果を返す。"""
    # Rules: 孤立ルール
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "orphan.md").write_text("# Orphan\nSome rule.")

    # Memory: 正常
    memory_dir = tmp_path / ".claude" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text("## Info\nAll good.\n")

    # Hooks: 未設定
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({}))

    # CLAUDE.md なし
    result = diagnose_all_layers(tmp_path)

    assert "rules" in result
    assert "memory" in result
    assert "hooks" in result
    assert "claudemd" in result
    assert "coherence_adapter" in result

    # Rules は orphan_rule 廃止のため検出されない
    orphan_issues = [i for i in result["rules"] if i["type"] == "orphan_rule"]
    assert len(orphan_issues) == 0

    # Hooks は unconfigured
    assert len(result["hooks"]) == 1
    assert result["hooks"][0]["type"] == "hooks_unconfigured"

    # CLAUDE.md は存在しないので空
    assert result["claudemd"] == []

    # coherence_adapter は結果なしなので空
    assert result["coherence_adapter"] == []


def test_all_layers_individual_error_isolation(tmp_path):
    """1つのレイヤーがエラーでも他レイヤーは実行される。"""
    # 最低限の構造のみ
    (tmp_path / ".claude").mkdir(parents=True)

    result = diagnose_all_layers(tmp_path)
    # エラーなく全キーが存在
    assert "rules" in result
    assert "memory" in result
    assert "hooks" in result
    assert "claudemd" in result


# ── issue フォーマット検証 ──────────────────────────────


def test_issue_format_consistency(tmp_path):
    """全 issue が統一フォーマットに従っている。"""
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "orphan.md").write_text("# Orphan\nSome old rule.")

    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({}))

    result = diagnose_all_layers(tmp_path)
    for layer_name, issues in result.items():
        for issue in issues:
            assert "type" in issue, f"Missing 'type' in {layer_name} issue"
            assert "file" in issue, f"Missing 'file' in {layer_name} issue"
            assert "detail" in issue, f"Missing 'detail' in {layer_name} issue"
            assert "source" in issue, f"Missing 'source' in {layer_name} issue"
            assert isinstance(issue["detail"], dict), f"'detail' should be dict in {layer_name}"
