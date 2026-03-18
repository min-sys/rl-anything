#!/usr/bin/env python3
"""pitfall_manager.py のテスト。"""
import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent.parent
_lib_dir = _root / "scripts" / "lib"
sys.path.insert(0, str(_lib_dir))
sys.path.insert(0, str(_root / "skills" / "audit" / "scripts"))

from pitfall_manager import (
    _compute_line_guard,
    detect_archive_candidates,
    detect_integration,
    execute_archive,
    extract_pitfall_candidates,
    extract_root_cause_keywords,
    find_matching_candidate,
    get_cold_tier,
    get_hot_tier,
    get_warm_tier,
    graduate_pitfall,
    parse_pitfalls,
    pitfall_hygiene,
    promote_to_active,
    record_pitfall,
    render_pitfalls,
    suggest_preflight_script,
)


# --- パース ---


SAMPLE_PITFALLS = """\
# Pitfalls

## Active Pitfalls

### CDK deploy failure
- **Status**: Active
- **Last-seen**: 2026-03-10
- **Root-cause**: action — CDK deploy パラメータ不足
- **Pre-flight対応**: Yes
- **Avoidance-count**: 3

### S3 bucket naming
- **Status**: New
- **Last-seen**: 2026-03-08
- **Root-cause**: tool_use — S3 バケット名ミス
- **Pre-flight対応**: No
- **Avoidance-count**: 0

## Candidate Pitfalls

### Lambda timeout
- **Status**: Candidate
- **First-seen**: 2026-03-01
- **Root-cause**: planning — タイムアウト設定不足
- **Occurrence-count**: 1

## Graduated Pitfalls

### Old issue
- **Status**: Graduated
- **Graduated-date**: 2026-01-01
- **Root-cause**: memory — コンテキスト消失
"""


def test_parse_sections():
    sections = parse_pitfalls(SAMPLE_PITFALLS)
    assert len(sections["active"]) == 2
    assert len(sections["candidate"]) == 1
    assert len(sections["graduated"]) == 1
    assert sections["active"][0]["title"] == "CDK deploy failure"
    assert sections["active"][0]["fields"]["Status"] == "Active"
    assert sections["candidate"][0]["fields"]["Root-cause"] == "planning — タイムアウト設定不足"


def test_roundtrip_parse_render():
    sections = parse_pitfalls(SAMPLE_PITFALLS)
    rendered = render_pitfalls(sections)
    re_parsed = parse_pitfalls(rendered)
    assert len(re_parsed["active"]) == 2
    assert len(re_parsed["candidate"]) == 1
    assert len(re_parsed["graduated"]) == 1


# --- 品質ゲート ---


def test_find_matching_candidate():
    candidates = [
        {"title": "Lambda timeout", "fields": {"Root-cause": "planning — timeout config missing value"}},
    ]
    # 類似した根本原因（Jaccard >= 0.5）
    idx = find_matching_candidate(candidates, "planning — timeout config insufficient value")
    assert idx == 0

    # 全く異なる根本原因
    idx = find_matching_candidate(candidates, "action — S3 bucket name error wrong region")
    assert idx is None


def test_record_first_occurrence(tmp_path):
    pitfalls_path = tmp_path / "pitfalls.md"
    result = record_pitfall(
        pitfalls_path, "New Error", "action — コマンドミス"
    )
    assert result["status"] == "Candidate"
    assert result["action"] == "created_candidate"
    content = pitfalls_path.read_text(encoding="utf-8")
    assert "Candidate" in content


def test_record_second_occurrence_promotes(tmp_path):
    pitfalls_path = tmp_path / "pitfalls.md"
    # 1回目
    record_pitfall(pitfalls_path, "Recurring Error", "action — deploy parameter missing value")
    # 2回目（類似根本原因、Jaccard >= 0.5）
    result = record_pitfall(pitfalls_path, "Same Error", "action — deploy parameter insufficient value")
    assert result["status"] == "New"
    assert result["action"] == "promoted_to_new"


def test_user_correction_bypasses_gate(tmp_path):
    pitfalls_path = tmp_path / "pitfalls.md"
    result = record_pitfall(
        pitfalls_path, "User Fix", "action — 手順ミス",
        is_user_correction=True,
    )
    assert result["status"] == "Active"
    assert result["action"] == "created_active"


# --- 3層管理 ---


def test_hot_tier():
    sections = parse_pitfalls(SAMPLE_PITFALLS)
    hot = get_hot_tier(sections)
    assert len(hot) == 1  # CDK deploy failure のみ (Pre-flight対応=Yes)
    assert hot[0]["title"] == "CDK deploy failure"


def test_warm_tier():
    sections = parse_pitfalls(SAMPLE_PITFALLS)
    warm = get_warm_tier(sections)
    assert len(warm) == 1  # S3 bucket naming (Pre-flight=No)


def test_cold_tier():
    sections = parse_pitfalls(SAMPLE_PITFALLS)
    cold = get_cold_tier(sections)
    assert len(cold) == 3  # Graduated + Candidate + New


# --- 状態遷移 ---


def test_promote_to_active(tmp_path):
    pitfalls_path = tmp_path / "pitfalls.md"
    pitfalls_path.write_text(SAMPLE_PITFALLS, encoding="utf-8")
    success = promote_to_active(pitfalls_path, "S3 bucket naming")
    assert success is True
    content = pitfalls_path.read_text(encoding="utf-8")
    assert "**Status**: Active" in content


def test_graduate_pitfall(tmp_path):
    pitfalls_path = tmp_path / "pitfalls.md"
    pitfalls_path.write_text(SAMPLE_PITFALLS, encoding="utf-8")
    success = graduate_pitfall(pitfalls_path, "CDK deploy failure", "SKILL.md Step 3")
    assert success is True
    sections = parse_pitfalls(pitfalls_path.read_text(encoding="utf-8"))
    assert len(sections["graduated"]) == 2  # Old + CDK deploy


# --- 破損ファイル ---


def test_corrupted_pitfalls_backup(tmp_path):
    pitfalls_path = tmp_path / "pitfalls.md"
    pitfalls_path.write_text("broken content without sections", encoding="utf-8")
    result = record_pitfall(pitfalls_path, "Test", "action — test")
    # バックアップが作成され、正常に記録できたこと
    assert result["status"] == "Candidate"
    assert pitfalls_path.with_suffix(".md.bak").exists()


def test_empty_pitfalls_reinit(tmp_path):
    pitfalls_path = tmp_path / "pitfalls.md"
    pitfalls_path.write_text("", encoding="utf-8")
    result = record_pitfall(pitfalls_path, "Test", "action — test")
    assert result["status"] == "Candidate"


# --- pitfall_hygiene ---


def test_hygiene_graduation_candidate(tmp_path):
    # 自己進化済みスキルを作成
    skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Test\n\n## Failure-triggered Learning\n\ncontent\n"
    )
    refs = skill_dir / "references"
    refs.mkdir()
    pitfalls = (
        "# Pitfalls\n\n## Active Pitfalls\n\n"
        "### Old issue\n"
        "- **Status**: Active\n"
        "- **Last-seen**: 2025-01-01\n"
        "- **Root-cause**: action — old\n"
        "- **Pre-flight対応**: Yes\n"
        "- **Avoidance-count**: 15\n\n"
        "## Candidate Pitfalls\n\n## Graduated Pitfalls\n"
    )
    (refs / "pitfalls.md").write_text(pitfalls, encoding="utf-8")

    result = pitfall_hygiene(tmp_path, frequency_scores={"test-skill": 1})
    assert result["skills_checked"] == 1
    assert len(result["graduation_candidates"]) == 1
    assert result["graduation_candidates"][0]["avoidance_count"] == 15
    assert len(result["stale_warnings"]) == 1  # 2025-01-01 は6ヶ月超


def test_hygiene_cap_exceeded(tmp_path):
    skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Test\n\n## Failure-triggered Learning\n\ncontent\n"
    )
    refs = skill_dir / "references"
    refs.mkdir()

    # 11件の Active pitfalls
    entries = []
    for i in range(11):
        entries.append(
            f"### Issue {i}\n"
            f"- **Status**: Active\n"
            f"- **Last-seen**: 2026-03-10\n"
            f"- **Root-cause**: action — issue {i}\n"
            f"- **Pre-flight対応**: No\n"
            f"- **Avoidance-count**: 0"
        )
    pitfalls_content = (
        "# Pitfalls\n\n## Active Pitfalls\n\n"
        + "\n\n".join(entries)
        + "\n\n## Candidate Pitfalls\n\n## Graduated Pitfalls\n"
    )
    (refs / "pitfalls.md").write_text(pitfalls_content, encoding="utf-8")

    result = pitfall_hygiene(tmp_path)
    assert len(result["cap_exceeded"]) == 1
    assert result["cap_exceeded"][0]["active_count"] == 11


# --- Root-cause キーワード抽出 ---


def test_extract_root_cause_keywords():
    keywords = extract_root_cause_keywords("action — CDK deploy パラメータ不足")
    assert "cdk" in keywords
    assert "deploy" in keywords
    assert "パラメータ不足" in keywords or "パラメータ" in keywords


def test_extract_root_cause_keywords_no_dash():
    keywords = extract_root_cause_keywords("simple error message")
    assert len(keywords) > 0


# --- 自動検出 (extract_pitfall_candidates) ---


def test_extract_from_corrections():
    corrections = [
        {"correction_type": "stop", "last_skill": "my-skill", "message": "deploy failed badly"},
        {"correction_type": "iya", "last_skill": "my-skill", "message": "wrong parameter used"},
    ]
    result = extract_pitfall_candidates(corrections)
    assert len(result["candidates"]) == 2
    assert result["skipped"] == 0


def test_extract_skips_empty_last_skill():
    corrections = [
        {"correction_type": "stop", "last_skill": "", "message": "msg"},
        {"correction_type": "stop", "last_skill": None, "message": "msg"},
    ]
    result = extract_pitfall_candidates(corrections)
    assert len(result["candidates"]) == 0


def test_extract_skips_non_stop_iya():
    corrections = [
        {"correction_type": "positive", "last_skill": "s", "message": "good job"},
    ]
    result = extract_pitfall_candidates(corrections)
    assert len(result["candidates"]) == 0


def test_extract_duplicate_increments_occurrence():
    existing = [
        {"title": "Existing", "fields": {"Root-cause": "stop — deploy failed badly", "Occurrence-count": "1"}},
    ]
    corrections = [
        {"correction_type": "stop", "last_skill": "s", "message": "deploy failed badly"},
    ]
    result = extract_pitfall_candidates(corrections, existing_candidates=existing)
    assert len(result["candidates"]) == 0
    assert len(result["occurrence_increments"]) == 1
    assert result["occurrence_increments"][0]["new_count"] == 2


def test_extract_malformed_correction_skipped():
    corrections = [
        "not a dict",  # malformed
        {"correction_type": "stop", "last_skill": "s", "message": "ok"},
    ]
    result = extract_pitfall_candidates(corrections)
    assert result["skipped"] == 1
    assert len(result["candidates"]) == 1


def test_extract_missing_errors_jsonl():
    corrections = [
        {"correction_type": "stop", "last_skill": "s", "message": "msg"},
    ]
    result = extract_pitfall_candidates(corrections, errors=None)
    assert len(result["candidates"]) == 1


def test_extract_errors_frequency():
    errors = [
        {"skill_name": "s", "error_message": "timeout error happened"},
        {"skill_name": "s", "error_message": "timeout error happened"},
        {"skill_name": "s", "error_message": "timeout error happened"},
    ]
    result = extract_pitfall_candidates([], errors=errors)
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["source"] == "errors"


def test_extract_errors_below_threshold():
    errors = [
        {"skill_name": "s", "error_message": "rare error"},
        {"skill_name": "s", "error_message": "rare error"},
    ]
    result = extract_pitfall_candidates([], errors=errors)
    assert len(result["candidates"]) == 0


# --- 統合済み判定 (detect_integration) ---


def test_detect_integration_skill_md(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test\n---\n\n## Deploy手順\n\nCDK deploy 時は必ずパラメータを確認する。\n"
    )
    pitfall = {
        "title": "CDK deploy",
        "fields": {"Root-cause": "action — CDK deploy パラメータ不足", "Status": "Active"},
    }
    result = detect_integration(pitfall, skill_dir)
    assert result["integration_detected"] is True
    assert result["integration_target"] == "SKILL.md"


def test_detect_integration_not_found(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("## Setup\n\nGeneric content.\n")
    pitfall = {
        "title": "S3 issue",
        "fields": {"Root-cause": "tool_use — S3バケット名ミス", "Status": "Active"},
    }
    result = detect_integration(pitfall, skill_dir)
    assert result["integration_detected"] is False


def test_detect_integration_references(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("## Intro\n\nNothing related.\n")
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "pitfalls.md").write_text("## Pitfalls\n\nCDK deploy パラメータ確認。\n")
    (refs / "best-practices.md").write_text("## 手順\n\nCDK deploy 時はパラメータを必ず確認する。\n")
    pitfall = {
        "title": "CDK deploy",
        "fields": {"Root-cause": "action — CDK deploy パラメータ不足", "Status": "Active"},
    }
    result = detect_integration(pitfall, skill_dir)
    assert result["integration_detected"] is True
    assert result["integration_target"] == "references/best-practices.md"  # pitfalls.md excluded


# --- TTL アーカイブ (detect_archive_candidates) ---


def test_archive_graduated_past_ttl():
    sections = {
        "active": [],
        "candidate": [],
        "graduated": [{
            "title": "Old grad",
            "fields": {"Graduated-date": "2025-01-01", "Status": "Graduated"},
            "raw": "",
        }],
    }
    result = detect_archive_candidates(sections)
    assert len(result) == 1
    assert result[0]["category"] == "graduated_ttl"


def test_archive_graduated_within_ttl():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sections = {
        "active": [],
        "candidate": [],
        "graduated": [{
            "title": "Recent grad",
            "fields": {"Graduated-date": today, "Status": "Graduated"},
            "raw": "",
        }],
    }
    result = detect_archive_candidates(sections)
    assert len(result) == 0


def test_archive_stale_escalation():
    sections = {
        "active": [{
            "title": "Very old",
            "fields": {"Status": "Active", "Last-seen": "2025-01-01"},
            "raw": "",
        }],
        "candidate": [],
        "graduated": [],
    }
    result = detect_archive_candidates(sections)
    assert len(result) == 1
    assert result[0]["category"] == "stale_escalation"


def test_archive_recent_active_excluded():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sections = {
        "active": [{
            "title": "Recent",
            "fields": {"Status": "Active", "Last-seen": today},
            "raw": "",
        }],
        "candidate": [],
        "graduated": [],
    }
    result = detect_archive_candidates(sections)
    assert len(result) == 0


# --- execute_archive ---


def test_execute_archive(tmp_path):
    pitfalls_path = tmp_path / "pitfalls.md"
    pitfalls_path.write_text(SAMPLE_PITFALLS, encoding="utf-8")
    result = execute_archive(pitfalls_path, ["Old issue"])
    assert result["removed"] == ["Old issue"]
    sections = parse_pitfalls(pitfalls_path.read_text(encoding="utf-8"))
    assert len(sections["graduated"]) == 0


def test_execute_archive_not_found(tmp_path):
    pitfalls_path = tmp_path / "pitfalls.md"
    pitfalls_path.write_text(SAMPLE_PITFALLS, encoding="utf-8")
    result = execute_archive(pitfalls_path, ["Nonexistent"])
    assert result["not_found"] == ["Nonexistent"]


# --- 行数ガード ---


def test_line_guard_under_limit():
    content = "\n".join(["line"] * 50)
    sections = {"active": [], "candidate": [], "graduated": []}
    result = _compute_line_guard(sections, content)
    assert result["line_count"] == 50
    assert result["line_guard_candidates"] == []
    assert result["warning"] is None


def test_line_guard_over_limit():
    content = "\n".join(["line"] * 120)
    sections = {
        "active": [],
        "candidate": [{
            "title": "c1",
            "fields": {"First-seen": "2025-01-01"},
            "raw": "\n".join(["line"] * 25),
        }],
        "graduated": [{
            "title": "g1",
            "fields": {"Graduated-date": "2025-01-01"},
            "raw": "\n".join(["line"] * 25),
        }],
    }
    result = _compute_line_guard(sections, content)
    assert result["line_count"] == 120
    assert len(result["line_guard_candidates"]) > 0


def test_line_guard_cold_insufficient():
    content = "\n".join(["line"] * 150)
    sections = {
        "active": [],
        "candidate": [{
            "title": "c1",
            "fields": {"First-seen": "2025-01-01"},
            "raw": "one line",
        }],
        "graduated": [],
    }
    result = _compute_line_guard(sections, content)
    assert result["warning"] == "Active/New 項目の手動レビューが必要"


# --- Pre-flight スクリプト提案 ---


def test_suggest_preflight_action(tmp_path):
    tmpl_dir = tmp_path / "templates"
    tmpl_dir.mkdir()
    (tmpl_dir / "action.sh").write_text("#!/bin/bash\n")
    (tmpl_dir / "generic.sh").write_text("#!/bin/bash\n")

    pitfall = {
        "title": "CDK deploy",
        "fields": {
            "Status": "Active",
            "Root-cause": "action — CDK deploy パラメータ不足",
            "Pre-flight対応": "Yes",
        },
    }
    result = suggest_preflight_script(pitfall, templates_dir=tmpl_dir)
    assert result is not None
    assert result["category"] == "action"
    assert "action.sh" in result["template_path"]


def test_suggest_preflight_unknown_category(tmp_path):
    tmpl_dir = tmp_path / "templates"
    tmpl_dir.mkdir()
    (tmpl_dir / "generic.sh").write_text("#!/bin/bash\n")

    pitfall = {
        "title": "Unknown",
        "fields": {
            "Status": "Active",
            "Root-cause": "planning — something unusual",
            "Pre-flight対応": "Yes",
        },
    }
    result = suggest_preflight_script(pitfall, templates_dir=tmpl_dir)
    assert result is not None
    assert result["category"] == "generic"


def test_suggest_preflight_not_preflight():
    pitfall = {
        "title": "No preflight",
        "fields": {
            "Status": "Active",
            "Root-cause": "action — test",
            "Pre-flight対応": "No",
        },
    }
    result = suggest_preflight_script(pitfall)
    assert result is None


# --- hygiene 拡張フィールド ---


def test_hygiene_new_fields(tmp_path):
    """pitfall_hygiene の返却値に新フィールドが含まれること。"""
    skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Test\n\n## Failure-triggered Learning\n\ncontent\n"
    )
    refs = skill_dir / "references"
    refs.mkdir()
    pitfalls = (
        "# Pitfalls\n\n## Active Pitfalls\n\n"
        "### Test item\n"
        "- **Status**: Active\n"
        "- **Last-seen**: 2026-03-10\n"
        "- **Root-cause**: action — test\n"
        "- **Pre-flight対応**: Yes\n"
        "- **Avoidance-count**: 0\n\n"
        "## Candidate Pitfalls\n\n## Graduated Pitfalls\n"
    )
    (refs / "pitfalls.md").write_text(pitfalls, encoding="utf-8")

    result = pitfall_hygiene(tmp_path)
    # 新フィールドの存在確認
    assert "graduation_proposals" in result
    assert "archive_candidates" in result
    assert "codegen_proposals" in result
    assert "line_count" in result
    assert isinstance(result["graduation_proposals"], list)
    assert isinstance(result["archive_candidates"], list)
    assert isinstance(result["codegen_proposals"], list)
    assert isinstance(result["line_count"], int)
    # 新フィールド: issues + preflight_candidates
    assert "issues" in result
    assert "preflight_candidates" in result
    assert isinstance(result["issues"], list)
    assert isinstance(result["preflight_candidates"], list)


# --- 合理化防止テーブル (rationalization patterns) ---


from pitfall_manager import (
    detect_rationalization_patterns,
    generate_rationalization_table,
)
from skill_evolve import (
    RATIONALIZATION_MIN_CORRECTIONS,
    RATIONALIZATION_SKIP_KEYWORDS,
)


class TestDetectRationalizationPatterns:
    def test_skip_keywords_detected(self):
        """skip キーワードを含む corrections → パターンが返る。"""
        corrections = [
            {"message": "テスト省略して進めて"},
            {"message": "テストはスキップで"},
            {"message": "bypass the validation step"},
        ]
        patterns = detect_rationalization_patterns(corrections)
        assert len(patterns) >= 1
        # 各パターンに必須キーが含まれる
        for p in patterns:
            assert "excuse" in p
            assert "corrections" in p
            assert "sample_count" in p
            assert p["sample_count"] >= 1

    def test_no_skip_keywords_returns_empty(self):
        """skip キーワードを含まない corrections → 空リスト。"""
        corrections = [
            {"message": "テストを追加して"},
            {"message": "デプロイ完了しました"},
        ]
        patterns = detect_rationalization_patterns(corrections)
        assert patterns == []

    def test_non_dict_corrections_skipped(self):
        """dict でないレコードは無視される。"""
        corrections = [
            "not a dict",
            {"message": "後でやる"},
        ]
        patterns = detect_rationalization_patterns(corrections)
        assert len(patterns) == 1

    def test_empty_message_skipped(self):
        """message が空のレコードは無視される。"""
        corrections = [
            {"message": ""},
            {"message": "スキップして"},
        ]
        patterns = detect_rationalization_patterns(corrections)
        assert len(patterns) == 1

    def test_multiple_keywords_in_single_message(self):
        """1メッセージに複数キーワードが含まれる場合も1パターンとして検出。"""
        corrections = [
            {"message": "テストは不要、スキップして後でやる"},
        ]
        patterns = detect_rationalization_patterns(corrections)
        assert len(patterns) == 1

    def test_case_insensitive_matching(self):
        """英語キーワードは大文字小文字を区別しない。"""
        corrections = [
            {"message": "SKIP this step"},
            {"message": "Bypass validation"},
        ]
        patterns = detect_rationalization_patterns(corrections)
        assert len(patterns) >= 1


class TestGenerateRationalizationTable:
    def test_data_insufficient_below_threshold(self):
        """skip パターン corrections が閾値未満 → data_insufficient=True。"""
        # 通常のメッセージのみ → skip 検出は 0 件
        corrections = [
            {"message": "テストを追加して"},
            {"message": "デプロイ完了"},
        ]
        result = generate_rationalization_table(corrections)
        assert result["data_insufficient"] is True
        assert result["table"] == []
        assert result["enriched_pitfalls"] == []

    def test_table_generated_with_sufficient_corrections(self):
        """skip corrections が閾値以上 → テーブル生成。"""
        corrections = [
            {"message": f"テスト省略して ({i})", "timestamp": "2026-03-10T00:00:00Z"}
            for i in range(RATIONALIZATION_MIN_CORRECTIONS)
        ]
        errors = [
            {"timestamp": "2026-03-15T00:00:00Z", "error_message": "test fail"},
        ]
        result = generate_rationalization_table(corrections, errors=errors)
        assert result["data_insufficient"] is False
        assert len(result["table"]) >= 1
        # テーブルエントリの必須キー
        entry = result["table"][0]
        assert "excuse" in entry
        assert "outcome_error_rate" in entry
        assert "sample_count" in entry
        assert "telemetry_source" in entry

    def test_table_sorted_by_sample_count_desc(self):
        """テーブルは sample_count の降順でソートされる。"""
        corrections = [
            {"message": "スキップして", "timestamp": "2026-03-10T00:00:00Z"},
            {"message": "スキップして", "timestamp": "2026-03-11T00:00:00Z"},
            {"message": "スキップして", "timestamp": "2026-03-12T00:00:00Z"},
            {"message": "後でやる", "timestamp": "2026-03-10T00:00:00Z"},
        ]
        result = generate_rationalization_table(corrections)
        if not result["data_insufficient"] and len(result["table"]) >= 2:
            for i in range(len(result["table"]) - 1):
                assert result["table"][i]["sample_count"] >= result["table"][i + 1]["sample_count"]

    def test_telemetry_source_corrections_only_without_errors(self):
        """errors が空の場合 telemetry_source は corrections_only。"""
        corrections = [
            {"message": f"スキップして ({i})"}
            for i in range(RATIONALIZATION_MIN_CORRECTIONS)
        ]
        result = generate_rationalization_table(corrections, errors=[])
        assert result["data_insufficient"] is False
        for entry in result["table"]:
            assert entry["telemetry_source"] == "corrections_only"

    def test_enriched_pitfall_on_overlap(self):
        """既存 pitfall と Jaccard 重複 → enriched_pitfalls に追加、duplicate でない。"""
        corrections = [
            {"message": f"テスト省略して deploy failed ({i})", "timestamp": "2026-03-10T00:00:00Z"}
            for i in range(RATIONALIZATION_MIN_CORRECTIONS)
        ]
        existing_pitfalls = {
            "active": [
                {
                    "title": "Deploy Error",
                    "fields": {
                        "Root-cause": "テスト省略して deploy failed",
                        "Status": "Active",
                    },
                }
            ],
            "candidate": [],
            "graduated": [],
        }
        result = generate_rationalization_table(
            corrections,
            existing_pitfalls=existing_pitfalls,
        )
        assert result["data_insufficient"] is False
        # 既存 pitfall とエンリッチされる（新規 pitfall ではなく enrichment）
        assert len(result["enriched_pitfalls"]) >= 1
        enriched = result["enriched_pitfalls"][0]
        assert "pitfall_title" in enriched
        assert "matched_excuse" in enriched
        assert "jaccard_score" in enriched
        assert "telemetry_data" in enriched

    def test_no_enrichment_without_existing_pitfalls(self):
        """existing_pitfalls が None → enriched_pitfalls は空。"""
        corrections = [
            {"message": f"スキップして ({i})"}
            for i in range(RATIONALIZATION_MIN_CORRECTIONS)
        ]
        result = generate_rationalization_table(corrections, existing_pitfalls=None)
        assert result["enriched_pitfalls"] == []

    def test_outcome_error_rate_with_post_errors(self):
        """errors にタイムスタンプ付きレコード → outcome_error_rate が数値。"""
        corrections = [
            {"message": f"省略して ({i})", "timestamp": "2026-03-10T00:00:00Z"}
            for i in range(RATIONALIZATION_MIN_CORRECTIONS)
        ]
        errors = [
            {"timestamp": "2026-03-15T00:00:00Z", "error_message": "fail"},
            {"timestamp": "2026-03-20T00:00:00Z", "error_message": "fail"},
        ]
        result = generate_rationalization_table(corrections, errors=errors)
        assert result["data_insufficient"] is False
        for entry in result["table"]:
            if entry["telemetry_source"] == "usage+errors":
                assert isinstance(entry["outcome_error_rate"], float)
