#!/usr/bin/env python3
"""skill_evolve.py のテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

_lib_dir = Path(__file__).resolve().parent.parent.parent / "scripts" / "lib"
sys.path.insert(0, str(_lib_dir))

from skill_evolve import (
    ANTI_PATTERN_REJECTION_COUNT,
    BAND_AID_THRESHOLD,
    HIGH_SUITABILITY_THRESHOLD,
    MEDIUM_SUITABILITY_THRESHOLD,
    _count_external_keywords,
    _score_execution_frequency,
    _score_external_dependency,
    _score_failure_diversity,
    _score_output_evaluability,
    classify_suitability,
    detect_anti_patterns,
    evolve_skill_proposal,
    is_self_evolved_skill,
)
from issue_schema import (
    TOOL_USAGE_RULE_CANDIDATE,
    TOOL_USAGE_HOOK_CANDIDATE,
    SKILL_EVOLVE_CANDIDATE,
    SE_SKILL_NAME,
    SE_SKILL_DIR,
    SE_SUITABILITY,
    SE_TOTAL_SCORE,
    RULE_FILENAME,
    RULE_CONTENT,
    RULE_TARGET_COMMANDS,
    RULE_ALTERNATIVE_TOOLS,
    RULE_TOTAL_COUNT,
    HOOK_SCRIPT_PATH,
    HOOK_SCRIPT_CONTENT,
    HOOK_SETTINGS_DIFF,
    HOOK_TOTAL_COUNT,
    make_rule_candidate_issue,
    make_hook_candidate_issue,
    make_skill_evolve_issue,
)


# --- is_self_evolved_skill ---


def test_self_evolved_with_both(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "pitfalls.md").write_text("# Pitfalls\n")
    (skill_dir / "SKILL.md").write_text(
        "# My Skill\n\n## Failure-triggered Learning\n\nsome content\n"
    )
    assert is_self_evolved_skill(skill_dir) is True


def test_self_evolved_missing_pitfalls(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "# My Skill\n\n## Failure-triggered Learning\n"
    )
    assert is_self_evolved_skill(skill_dir) is False


def test_self_evolved_missing_section(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "pitfalls.md").write_text("# Pitfalls\n")
    (skill_dir / "SKILL.md").write_text("# My Skill\n\nNo special section\n")
    assert is_self_evolved_skill(skill_dir) is False


# --- テレメトリスコアリング ---


def test_frequency_scoring():
    assert _score_execution_frequency(0) == 1
    assert _score_execution_frequency(3) == 1
    assert _score_execution_frequency(4) == 2
    assert _score_execution_frequency(15) == 2
    assert _score_execution_frequency(16) == 3
    assert _score_execution_frequency(100) == 3


def test_diversity_scoring():
    assert _score_failure_diversity(set()) == 1
    assert _score_failure_diversity({"a"}) == 1
    assert _score_failure_diversity({"a", "b"}) == 2
    assert _score_failure_diversity({"a", "b", "c"}) == 2
    assert _score_failure_diversity({"a", "b", "c", "d"}) == 3


def test_evaluability_scoring():
    assert _score_output_evaluability(0, 0) == 1
    assert _score_output_evaluability(10, 0) == 1  # 100% success = hard to eval
    assert _score_output_evaluability(10, 3) == 2  # 70% success
    assert _score_output_evaluability(10, 6) == 3  # 40% success


# --- LLM軸（静的解析部分） ---


def test_external_dependency_scoring():
    assert _score_external_dependency("simple local tool") == 1
    assert _score_external_dependency("uses API and HTTP calls with deploy") == 2
    content_heavy = "AWS CDK deploy Lambda S3 SNS SQS DynamoDB Bedrock API HTTP MCP"
    assert _score_external_dependency(content_heavy) == 3


def test_external_keyword_count():
    assert _count_external_keywords("no keywords here") == 0
    assert _count_external_keywords("deploy to AWS using API") >= 3


# --- 分類 ---


def test_classify_suitability():
    assert classify_suitability(5) == "low"
    assert classify_suitability(7) == "low"
    assert classify_suitability(8) == "medium"
    assert classify_suitability(11) == "medium"
    assert classify_suitability(12) == "high"
    assert classify_suitability(15) == "high"


# --- アンチパターン検出 ---


def test_noise_collector_detection(tmp_path):
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Simple\n")
    # error_count > 0 のときのみ Noise Collector を検出
    patterns = detect_anti_patterns(
        {"diversity": 1, "frequency": 2, "judgment_complexity": 2, "error_count": 3},
        skill_dir,
    )
    assert any(p["pattern"] == "Noise Collector" for p in patterns)


def test_noise_collector_not_triggered_without_errors(tmp_path):
    """エラーデータなし（テレメトリ不在）では Noise Collector は検出しない。"""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Simple\n")
    patterns = detect_anti_patterns(
        {"diversity": 1, "frequency": 2, "judgment_complexity": 2, "error_count": 0},
        skill_dir,
    )
    assert not any(p["pattern"] == "Noise Collector" for p in patterns)


def test_context_bloat_detection(tmp_path):
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Simple\n")
    patterns = detect_anti_patterns(
        {"diversity": 2, "frequency": 3, "judgment_complexity": 1, "error_count": 5},
        skill_dir,
    )
    assert any(p["pattern"] == "Context Bloat" for p in patterns)


def test_band_aid_detection(tmp_path):
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    # Band-Aid は references/ のみカウント（SKILL.md のステップは除外）
    refs = skill_dir / "references"
    refs.mkdir()
    items = "\n".join(f"- item {i}" for i in range(BAND_AID_THRESHOLD + 1))
    (refs / "troubleshoot.md").write_text(f"# Troubleshoot\n\n{items}\n")
    (skill_dir / "SKILL.md").write_text("# Skill\n")
    patterns = detect_anti_patterns(
        {"diversity": 2, "frequency": 2, "judgment_complexity": 2, "error_count": 5},
        skill_dir,
    )
    assert any(p["pattern"] == "Band-Aid" for p in patterns)


def test_band_aid_not_triggered_by_skill_md_steps(tmp_path):
    """SKILL.md の手順リストだけでは Band-Aid は検出されない。"""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    items = "\n".join(f"- step {i}" for i in range(50))
    (skill_dir / "SKILL.md").write_text(f"# Skill\n\n{items}\n")
    patterns = detect_anti_patterns(
        {"diversity": 2, "frequency": 2, "judgment_complexity": 2, "error_count": 5},
        skill_dir,
    )
    assert not any(p["pattern"] == "Band-Aid" for p in patterns)


def test_no_anti_patterns(tmp_path):
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Simple\n- one\n- two\n")
    patterns = detect_anti_patterns(
        {"diversity": 3, "frequency": 2, "judgment_complexity": 2, "error_count": 5},
        skill_dir,
    )
    assert len(patterns) == 0


# --- キャッシュ ---


def test_llm_cache_hit(tmp_path, monkeypatch):
    from skill_evolve import compute_llm_scores, _file_hash, CACHE_FILE

    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Test Skill\n")

    # キャッシュを事前設定
    cache = {
        "my-skill": {
            "hash": _file_hash(skill_md),
            "external_dependency": 2,
            "judgment_complexity": 3,
        }
    }
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps(cache))

    monkeypatch.setattr("skill_evolve.CACHE_FILE", cache_file)
    result = compute_llm_scores("my-skill", skill_dir)
    assert result["cached"] is True
    assert result["external_dependency"] == 2
    assert result["judgment_complexity"] == 3


# --- evolve_skill_proposal ---


def test_proposal_template_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "skill_evolve._plugin_root",
        tmp_path / "nonexistent",
    )
    result = evolve_skill_proposal("test-skill", tmp_path / "test-skill")
    assert result["error"] is not None
    assert "テンプレートファイルが見つかりません" in result["error"]


def test_proposal_with_templates(tmp_path, monkeypatch):
    # テンプレートディレクトリを作成
    templates_dir = tmp_path / "skills" / "evolve" / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "self-evolve-sections.md").write_text(
        "## Pre-flight Check\n\nCheck pitfalls.\n\n"
        "## Failure-triggered Learning\n\n| Trigger | Action |\n"
    )
    (templates_dir / "pitfalls.md").write_text(
        "## Active Pitfalls\n\n## Candidate Pitfalls\n\n## Graduated Pitfalls\n"
    )

    # スキルディレクトリ
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Test Skill\n")

    monkeypatch.setattr("skill_evolve._plugin_root", tmp_path)

    # LLM をモック（テンプレートそのまま返す）
    with mock.patch("skill_evolve._customize_template") as mock_custom:
        mock_custom.return_value = (
            "## Pre-flight Check\n\nCheck pitfalls.\n\n"
            "## Failure-triggered Learning\n\n| Trigger | Action |\n"
        )
        result = evolve_skill_proposal("test-skill", skill_dir)

    assert result["error"] is None
    assert "Pre-flight" in result["sections_to_add"]
    assert "Active Pitfalls" in result["pitfalls_template"]


# --- evolve.py データフロー統合テスト ---


def test_skill_evolve_issues_injected_into_remediation(tmp_path):
    """skill_evolve_assessment の結果が remediation の issues に注入されることを確認。"""
    evolve_scripts = Path(__file__).resolve().parent.parent.parent / "skills" / "evolve" / "scripts"
    sys.path.insert(0, str(evolve_scripts))
    from remediation import classify_issues as real_classify

    fake_assessment = [
        {
            "skill_name": "test-skill",
            "skill_dir": str(tmp_path / "test-skill"),
            "already_evolved": False,
            "suitability": "medium",
            "total_score": 10,
        },
    ]

    # skill_evolve 結果を変換（issue_schema factory 経由）
    issues = []
    for assessment in fake_assessment:
        suitability = assessment.get("suitability", "low")
        if suitability in ("high", "medium"):
            skill_md_path = str(Path(assessment["skill_dir"]) / "SKILL.md")
            issues.append(make_skill_evolve_issue(assessment, skill_md_path))

    assert len(issues) == 1
    assert issues[0]["type"] == SKILL_EVOLVE_CANDIDATE
    assert issues[0]["detail"][SE_SUITABILITY] == "medium"

    # classify_issues に渡せることを確認
    classified = real_classify(issues)
    # medium suitability → confidence 0.60 → proposable
    assert len(classified["proposable"]) == 1
    assert classified["proposable"][0]["confidence_score"] == 0.60


def test_tool_usage_issues_injected_into_remediation():
    """discover の tool_usage 結果が remediation の issues に注入されることを確認。

    tool_usage_analyzer の出力スキーマ → issue_schema factory → remediation classify。
    """
    from remediation import classify_issues as real_classify

    # tool_usage_analyzer が返す実際のスキーマ
    rule_candidates = [
        {
            RULE_FILENAME: "avoid-bash-builtin.md",
            RULE_CONTENT: "# test rule\ngrep は Grep。\nパイプは OK。\n",
            RULE_TARGET_COMMANDS: ["grep", "rg"],
            RULE_ALTERNATIVE_TOOLS: ["Grep"],
            RULE_TOTAL_COUNT: 5,
        }
    ]
    hook_candidate = {
        HOOK_SCRIPT_PATH: str(Path.home() / ".claude" / "hooks" / "check-bash-builtin.py"),
        HOOK_SCRIPT_CONTENT: "#!/usr/bin/env python3\n# hook",
        HOOK_SETTINGS_DIFF: '{"hooks": {}}',
        "target_commands": ["grep", "rg"],
    }

    rules_dir_str = str(Path.home() / ".claude" / "rules")
    issues = []
    for rc in rule_candidates:
        issues.append(make_rule_candidate_issue(rc, rules_dir_str=rules_dir_str))
    total_count = 5
    issues.append(make_hook_candidate_issue(hook_candidate, total_count))

    assert len(issues) == 2
    assert issues[0]["type"] == TOOL_USAGE_RULE_CANDIDATE
    assert issues[1]["type"] == TOOL_USAGE_HOOK_CANDIDATE

    # detail フィールドが正しく設定されていることを確認
    assert issues[0]["detail"][RULE_FILENAME] == "avoid-bash-builtin.md"
    assert issues[0]["detail"][RULE_TOTAL_COUNT] == 5
    assert issues[1]["detail"][HOOK_SCRIPT_PATH] != ""
    assert issues[1]["detail"][HOOK_TOTAL_COUNT] == 5

    # classify_issues に渡せることを確認
    classified = real_classify(issues)
    # global scope → proposable
    assert len(classified["proposable"]) == 2


def test_low_suitability_not_injected():
    """low suitability のスキルは issue に変換されないことを確認。"""
    fake_assessment = [
        {
            "skill_name": "simple-skill",
            "skill_dir": "/tmp/simple-skill",
            "already_evolved": False,
            "suitability": "low",
            "total_score": 6,
        },
    ]

    issues = []
    for assessment in fake_assessment:
        suitability = assessment.get("suitability", "low")
        if suitability in ("high", "medium"):
            skill_md_path = str(Path(assessment["skill_dir"]) / "SKILL.md")
            issues.append(make_skill_evolve_issue(assessment, skill_md_path))

    assert len(issues) == 0
