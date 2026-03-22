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
    VERIFICATION_SKILL_KEYWORDS,
    _count_external_keywords,
    _score_execution_frequency,
    _score_external_dependency,
    _score_failure_diversity,
    _score_output_evaluability,
    apply_evolve_proposal,
    assess_single_skill,
    classify_suitability,
    detect_anti_patterns,
    evolve_skill_proposal,
    is_self_evolved_skill,
    is_verification_skill,
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


# --- assess_single_skill ---


def test_assess_single_skill_already_evolved(tmp_path):
    """既に自己進化済みのスキルは suitability='already_evolved' を返す。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "pitfalls.md").write_text("# Pitfalls\n")
    (skill_dir / "SKILL.md").write_text(
        "# My Skill\n\n## Failure-triggered Learning\n\nsome content\n"
    )
    result = assess_single_skill("my-skill", skill_dir)
    assert result["suitability"] == "already_evolved"
    assert result["already_evolved"] is True


@mock.patch("skill_evolve.compute_llm_scores")
@mock.patch("skill_evolve.compute_telemetry_scores")
def test_assess_single_skill_high(mock_telemetry, mock_llm, tmp_path):
    """高適性スキルの判定。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill\n")

    mock_telemetry.return_value = {
        "frequency": 3, "diversity": 3, "evaluability": 3,
        "usage_count": 20, "error_count": 8,
        "error_categories": ["a", "b", "c", "d"],
    }
    mock_llm.return_value = {
        "external_dependency": 2, "judgment_complexity": 3, "cached": True,
    }
    result = assess_single_skill("my-skill", skill_dir)
    assert result["suitability"] == "high"
    assert result["total_score"] >= HIGH_SUITABILITY_THRESHOLD


@mock.patch("skill_evolve.compute_llm_scores")
@mock.patch("skill_evolve.compute_telemetry_scores")
def test_assess_single_skill_medium(mock_telemetry, mock_llm, tmp_path):
    """中適性スキルの判定。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill\n")

    mock_telemetry.return_value = {
        "frequency": 2, "diversity": 2, "evaluability": 1,
        "usage_count": 10, "error_count": 0,
        "error_categories": ["a", "b"],
    }
    mock_llm.return_value = {
        "external_dependency": 1, "judgment_complexity": 2, "cached": True,
    }
    result = assess_single_skill("my-skill", skill_dir)
    # total = 2+2+1+1+2+0 = 8 → medium (>= 8, < 12)
    assert result["suitability"] == "medium"


@mock.patch("skill_evolve.compute_llm_scores")
@mock.patch("skill_evolve.compute_telemetry_scores")
def test_assess_single_skill_low(mock_telemetry, mock_llm, tmp_path):
    """低適性スキルの判定。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill\n")

    mock_telemetry.return_value = {
        "frequency": 1, "diversity": 1, "evaluability": 1,
        "usage_count": 2, "error_count": 0,
        "error_categories": [],
    }
    mock_llm.return_value = {
        "external_dependency": 1, "judgment_complexity": 1, "cached": True,
    }
    result = assess_single_skill("my-skill", skill_dir)
    assert result["suitability"] == "low"


@mock.patch("skill_evolve.compute_llm_scores")
@mock.patch("skill_evolve.compute_telemetry_scores")
def test_assess_single_skill_rejected(mock_telemetry, mock_llm, tmp_path):
    """アンチパターン2件以上で rejected。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill\n")
    # Band-Aid 用の references/ を作成
    refs = skill_dir / "references"
    refs.mkdir()
    items = "\n".join(f"- item {i}" for i in range(BAND_AID_THRESHOLD + 1))
    (refs / "troubleshoot.md").write_text(f"# Troubleshoot\n\n{items}\n")

    # Noise Collector (diversity=1, error_count>0) + Band-Aid
    mock_telemetry.return_value = {
        "frequency": 3, "diversity": 1, "evaluability": 3,
        "usage_count": 20, "error_count": 5,
        "error_categories": ["a"],
    }
    mock_llm.return_value = {
        "external_dependency": 1, "judgment_complexity": 1, "cached": True,
    }
    result = assess_single_skill("my-skill", skill_dir)
    assert result["suitability"] == "rejected"


# --- is_verification_skill ---


def test_is_verification_skill_by_name():
    """スキル名にverify/check/validate/lint/test/qa等が含まれる場合にTrueを返す。"""
    for name in ["godot-verify", "pre-check", "validate-schema", "lint-code", "qa", "qa-only"]:
        assert is_verification_skill(name, Path("/dummy")) is True, f"{name} should be verification"


def test_is_verification_skill_not_matched():
    """verify系キーワードを含まないスキル名はFalseを返す。"""
    for name in ["deploy", "commit", "design-review", "office-hours"]:
        assert is_verification_skill(name, Path("/dummy")) is False, f"{name} should NOT be verification"


def test_is_verification_skill_by_content(tmp_path):
    """スキル名はマッチしないが、SKILL.md内容にverify系キーワードがある場合にTrueを返す。"""
    skill_dir = tmp_path / "my-tool"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "# My Tool\n\nThis skill validates and verifies deployment results.\n"
    )
    assert is_verification_skill("my-tool", skill_dir) is True


def test_is_verification_skill_content_no_match(tmp_path):
    """スキル名もSKILL.md内容もマッチしない場合はFalseを返す。"""
    skill_dir = tmp_path / "my-tool"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Tool\n\nThis skill creates documents.\n")
    assert is_verification_skill("my-tool", skill_dir) is False


@mock.patch("skill_evolve.compute_llm_scores")
@mock.patch("skill_evolve.compute_telemetry_scores")
def test_assess_single_skill_verification_bypass(mock_telemetry, mock_llm, tmp_path):
    """verify系スキルはテレメトリが低くてもmediumに昇格する。"""
    skill_dir = tmp_path / "godot-verify"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Godot Verify\n")

    mock_telemetry.return_value = {
        "frequency": 1, "diversity": 1, "evaluability": 1,
        "usage_count": 0, "error_count": 0,
        "error_categories": [],
    }
    mock_llm.return_value = {
        "external_dependency": 1, "judgment_complexity": 1, "cached": True,
    }
    result = assess_single_skill("godot-verify", skill_dir)
    assert result["suitability"] == "medium"
    assert "verification_bypass" in result
    assert result["verification_bypass"] is True
    assert "検証系" in result["recommendation"]


@mock.patch("skill_evolve.compute_llm_scores")
@mock.patch("skill_evolve.compute_telemetry_scores")
def test_assess_single_skill_verification_high_unchanged(mock_telemetry, mock_llm, tmp_path):
    """verify系スキルでもhigh以上なら昇格不要でそのまま。"""
    skill_dir = tmp_path / "godot-verify"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Godot Verify\n")

    mock_telemetry.return_value = {
        "frequency": 3, "diversity": 3, "evaluability": 3,
        "usage_count": 20, "error_count": 8,
        "error_categories": ["a", "b", "c", "d"],
    }
    mock_llm.return_value = {
        "external_dependency": 2, "judgment_complexity": 3, "cached": True,
    }
    result = assess_single_skill("godot-verify", skill_dir)
    assert result["suitability"] == "high"
    # high のまま — verification_bypass は付かない or False
    assert not result.get("verification_bypass", False)


# --- apply_evolve_proposal ---


def test_apply_evolve_proposal_success(tmp_path, monkeypatch):
    """正常適用: SKILL.md にセクション追記、references/pitfalls.md 作成、バックアップ作成。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    original_content = "# My Skill\n\nOriginal content.\n"
    (skill_dir / "SKILL.md").write_text(original_content)

    proposal = {
        "skill_name": "my-skill",
        "sections_to_add": "## Pre-flight Check\n\n## Failure-triggered Learning\n",
        "pitfalls_template": "## Active Pitfalls\n\n## Graduated Pitfalls\n",
        "skill_md_path": str(skill_dir / "SKILL.md"),
        "pitfalls_path": str(skill_dir / "references" / "pitfalls.md"),
        "error": None,
    }

    result = apply_evolve_proposal(proposal)
    assert result["applied"] is True
    assert result["error"] is None

    # SKILL.md にセクション追記されている
    updated = (skill_dir / "SKILL.md").read_text()
    assert "Pre-flight Check" in updated
    assert "Original content" in updated

    # references/pitfalls.md が作成されている
    pitfalls = skill_dir / "references" / "pitfalls.md"
    assert pitfalls.exists()
    assert "Active Pitfalls" in pitfalls.read_text()

    # バックアップが作成されている
    backup = skill_dir / "SKILL.md.pre-evolve-backup"
    assert backup.exists()
    assert backup.read_text() == original_content


def test_apply_evolve_proposal_creates_references_dir(tmp_path):
    """references/ ディレクトリがなくても自動作成される。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill\n")

    proposal = {
        "skill_name": "my-skill",
        "sections_to_add": "## Failure-triggered Learning\n",
        "pitfalls_template": "## Active Pitfalls\n",
        "skill_md_path": str(skill_dir / "SKILL.md"),
        "pitfalls_path": str(skill_dir / "references" / "pitfalls.md"),
        "error": None,
    }

    result = apply_evolve_proposal(proposal)
    assert result["applied"] is True
    assert (skill_dir / "references").is_dir()
    assert (skill_dir / "references" / "pitfalls.md").exists()


def test_apply_evolve_proposal_with_error():
    """proposal にエラーがある場合は適用しない。"""
    proposal = {
        "skill_name": "my-skill",
        "error": "テンプレートが見つかりません",
    }

    result = apply_evolve_proposal(proposal)
    assert result["applied"] is False
    assert result["error"] == "テンプレートが見つかりません"


def test_apply_evolve_proposal_backup_path_in_result(tmp_path):
    """結果に backup_path が含まれる。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# My Skill\n")

    proposal = {
        "skill_name": "my-skill",
        "sections_to_add": "## Failure-triggered Learning\n",
        "pitfalls_template": "## Active Pitfalls\n",
        "skill_md_path": str(skill_dir / "SKILL.md"),
        "pitfalls_path": str(skill_dir / "references" / "pitfalls.md"),
        "error": None,
    }

    result = apply_evolve_proposal(proposal)
    assert "backup_path" in result
    assert result["backup_path"].endswith(".pre-evolve-backup")


# --- workflow_checkpoints in assess_single_skill ---


@mock.patch("skill_evolve.compute_llm_scores")
@mock.patch("skill_evolve.compute_telemetry_scores")
def test_assess_workflow_skill_has_checkpoints(mock_telemetry, mock_llm, tmp_path):
    """ワークフロースキルの assessment に workflow_checkpoints が含まれる。"""
    # .claude/skills/my-skill/ 構造を作成
    project_dir = tmp_path / "project"
    claude_dir = project_dir / ".claude" / "skills" / "my-skill"
    claude_dir.mkdir(parents=True)
    (claude_dir / "SKILL.md").write_text(
        "---\ntype: workflow\n---\n\n# My Skill\n\n1. Step 1: Check\n2. Step 2: Do\n3. Step 3: Report\n"
    )

    mock_telemetry.return_value = {
        "frequency": 2, "diversity": 2, "evaluability": 2,
        "usage_count": 10, "error_count": 3,
        "error_categories": ["a", "b"],
    }
    mock_llm.return_value = {
        "external_dependency": 1, "judgment_complexity": 1, "cached": True,
    }
    result = assess_single_skill("my-skill", claude_dir)
    assert "workflow_checkpoints" in result
    # workflow_checkpoints はリスト（空でも可）
    assert isinstance(result["workflow_checkpoints"], list)


@mock.patch("skill_evolve.compute_llm_scores")
@mock.patch("skill_evolve.compute_telemetry_scores")
def test_assess_non_workflow_skill_has_none_checkpoints(mock_telemetry, mock_llm, tmp_path):
    """非ワークフロースキルでは workflow_checkpoints が None。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Simple Utility\n\nDoes one thing.\n")

    mock_telemetry.return_value = {
        "frequency": 2, "diversity": 2, "evaluability": 2,
        "usage_count": 10, "error_count": 3,
        "error_categories": ["a", "b"],
    }
    mock_llm.return_value = {
        "external_dependency": 1, "judgment_complexity": 1, "cached": True,
    }
    result = assess_single_skill("my-skill", skill_dir)
    assert result["workflow_checkpoints"] is None


def test_assess_already_evolved_has_none_checkpoints(tmp_path):
    """already_evolved のスキルでは workflow_checkpoints が None。"""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "pitfalls.md").write_text("# Pitfalls\n")
    (skill_dir / "SKILL.md").write_text(
        "# My Skill\n\n## Failure-triggered Learning\n\nsome content\n"
    )
    result = assess_single_skill("my-skill", skill_dir)
    assert result["workflow_checkpoints"] is None
