"""remediation.py のユニットテスト。"""
import json
import sys
from pathlib import Path

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "evolve" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "scripts"))

from remediation import (
    classify_issue,
    classify_issues,
    compute_confidence_score,
    compute_impact_scope,
    generate_rationale,
    fix_stale_references,
    fix_stale_rules,
    fix_claudemd_phantom_refs,
    fix_claudemd_missing_section,
    fix_global_rule,
    fix_hook_scaffold,
    FIX_DISPATCH,
    VERIFY_DISPATCH,
    generate_proposals,
    verify_fix,
    check_regression,
    rollback_fix,
    record_outcome,
)
from issue_schema import (
    TOOL_USAGE_RULE_CANDIDATE,
    TOOL_USAGE_HOOK_CANDIDATE,
    SKILL_EVOLVE_CANDIDATE,
    RULE_FILENAME,
    RULE_CONTENT,
    RULE_TARGET_COMMANDS,
    RULE_ALTERNATIVE_TOOLS,
    RULE_TOTAL_COUNT,
    HOOK_SCRIPT_PATH,
    HOOK_SCRIPT_CONTENT,
    HOOK_SETTINGS_DIFF,
    HOOK_TOTAL_COUNT,
    SE_SKILL_NAME,
    SE_TOTAL_SCORE,
)


# ---------- 分類テスト ----------

class TestClassification:
    def test_stale_ref_in_memory_is_auto_fixable(self):
        """通常の MEMORY ファイル内の陳腐化参照 → auto_fixable。"""
        issue = {
            "type": "stale_ref",
            "file": "/project/.claude/memory/MEMORY.md",
            "detail": {"line": 5, "path": "skills/nonexistent/SKILL.md"},
            "source": "build_memory_health_section",
        }
        result = classify_issue(issue)
        assert result["category"] == "auto_fixable"
        assert result["confidence_score"] >= 0.9
        assert result["impact_scope"] == "file"

    def test_stale_ref_in_claude_md_is_auto_fixable(self):
        """CLAUDE.md 内の陳腐化参照 → auto_fixable（project scope + confidence >= 0.9）。"""
        issue = {
            "type": "stale_ref",
            "file": "/project/CLAUDE.md",
            "detail": {"line": 10, "path": "skills/old/SKILL.md"},
            "source": "build_memory_health_section",
        }
        result = classify_issue(issue)
        assert result["category"] == "auto_fixable"
        assert result["impact_scope"] == "project"

    def test_project_scope_high_confidence_is_auto_fixable(self):
        """project scope + confidence >= 0.9 → auto_fixable。"""
        issue = {
            "type": "claudemd_missing_section",
            "file": "/project/CLAUDE.md",
            "detail": {"section": "skills", "skill_count": 5},
            "source": "diagnose",
        }
        result = classify_issue(issue)
        assert result["category"] == "auto_fixable"
        assert result["impact_scope"] == "project"

    def test_global_scope_high_confidence_is_proposable(self):
        """global scope → confidence 高くても proposable（auto_fixable にはならない）。"""
        home = str(Path.home())
        issue = {
            "type": "stale_rule",
            "file": f"{home}/.claude/rules/test.md",
            "detail": {"line": 1, "path": "nonexistent"},
            "source": "diagnose",
        }
        result = classify_issue(issue)
        assert result["category"] == "proposable"
        assert result["impact_scope"] == "global"

    def test_minor_line_excess_auto_fixable(self):
        """1行超過 → auto_fixable に格下げ。"""
        issue = {
            "type": "line_limit_violation",
            "file": "/project/.claude/memory/topic.md",
            "detail": {"lines": 121, "limit": 120},
            "source": "check_line_limits",
        }
        result = classify_issue(issue)
        assert result["category"] == "auto_fixable"
        assert result["confidence_score"] >= 0.9

    def test_major_line_excess_manual_required(self):
        """大幅超過 (160%+) → manual_required に格上げ。"""
        issue = {
            "type": "line_limit_violation",
            "file": "/project/.claude/skills/big/SKILL.md",
            "detail": {"lines": 800, "limit": 500},
            "source": "check_line_limits",
        }
        result = classify_issue(issue)
        assert result["category"] == "manual_required"
        assert result["confidence_score"] < 0.5

    def test_moderate_line_excess_proposable(self):
        """中程度の超過 → proposable。"""
        issue = {
            "type": "line_limit_violation",
            "file": "/project/.claude/skills/med/SKILL.md",
            "detail": {"lines": 600, "limit": 500},
            "source": "check_line_limits",
        }
        result = classify_issue(issue)
        assert result["category"] == "proposable"

    def test_global_scope_is_proposable(self):
        """グローバルスコープの問題 → proposable（ユーザー承認必須）。"""
        home = str(Path.home())
        issue = {
            "type": "stale_ref",
            "file": f"{home}/.claude/rules/old-rule.md",
            "detail": {"line": 1, "path": "nonexistent"},
            "source": "build_memory_health_section",
        }
        result = classify_issue(issue)
        assert result["category"] == "proposable"
        assert result["impact_scope"] == "global"

    def test_classify_issues_groups_correctly(self):
        """classify_issues が3カテゴリに正しくグルーピングする。"""
        issues = [
            {
                "type": "stale_ref",
                "file": "/project/.claude/memory/MEMORY.md",
                "detail": {"line": 5, "path": "x"},
                "source": "s",
            },
            {
                "type": "line_limit_violation",
                "file": "/project/.claude/skills/big/SKILL.md",
                "detail": {"lines": 800, "limit": 500},
                "source": "s",
            },
        ]
        result = classify_issues(issues)
        assert len(result["auto_fixable"]) == 1
        assert len(result["manual_required"]) == 1
        assert len(result["proposable"]) == 0

    def test_empty_issues(self):
        """空の issues → 全カテゴリ空。"""
        result = classify_issues([])
        assert result == {
            "auto_fixable": [],
            "proposable": [],
            "manual_required": [],
        }


# ---------- rationale テスト ----------

class TestRationale:
    def test_stale_ref_rationale(self):
        issue = {
            "type": "stale_ref",
            "detail": {"path": "skills/old/SKILL.md"},
        }
        r = generate_rationale(issue, "auto_fixable")
        assert "skills/old/SKILL.md" in r

    def test_line_limit_rationale_varies_by_category(self):
        issue = {
            "type": "line_limit_violation",
            "detail": {"lines": 510, "limit": 500},
        }
        r_auto = generate_rationale(issue, "auto_fixable")
        r_manual = generate_rationale(issue, "manual_required")
        assert r_auto != r_manual


# ---------- 修正アクションテスト ----------

class TestFixStaleReferences:
    def test_removes_stale_line(self, tmp_path):
        """陳腐化参照の行が削除される。"""
        f = tmp_path / "MEMORY.md"
        f.write_text("# Title\n\nSee skills/old/SKILL.md\n\nGood line\n")
        issues = [{
            "type": "stale_ref",
            "file": str(f),
            "detail": {"line": 3, "path": "skills/old/SKILL.md"},
            "source": "s",
        }]
        results = fix_stale_references(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is True
        assert "skills/old" not in f.read_text()
        assert "Good line" in f.read_text()

    def test_preserves_original_content(self, tmp_path):
        """original_content がロールバック用に保持される。"""
        f = tmp_path / "MEMORY.md"
        original = "# Title\n\nSee skills/old/SKILL.md\n"
        f.write_text(original)
        issues = [{
            "type": "stale_ref",
            "file": str(f),
            "detail": {"line": 3, "path": "skills/old/SKILL.md"},
            "source": "s",
        }]
        results = fix_stale_references(issues)
        assert results[0]["original_content"] == original


# ---------- 検証エンジンテスト ----------

class TestVerification:
    def test_verify_fix_stale_ref_resolved(self, tmp_path):
        """stale ref が解消された場合。"""
        f = tmp_path / "MEMORY.md"
        f.write_text("# Title\n\nGood content\n")
        issue = {
            "type": "stale_ref",
            "detail": {"path": "skills/old/SKILL.md"},
        }
        result = verify_fix(str(f), issue)
        assert result["resolved"] is True

    def test_verify_fix_not_resolved(self, tmp_path):
        """stale ref がまだ存在する場合。"""
        f = tmp_path / "MEMORY.md"
        f.write_text("# Title\n\nSee skills/old/SKILL.md here\n")
        issue = {
            "type": "stale_ref",
            "detail": {"path": "skills/old/SKILL.md"},
        }
        result = verify_fix(str(f), issue)
        assert result["resolved"] is False

    def test_check_regression_heading_removed(self, tmp_path):
        """見出し構造が壊れた場合 → regression 検出。"""
        f = tmp_path / "MEMORY.md"
        original = "# Title\n\n## Section\n\nContent\n"
        f.write_text("# Title\n\nContent\n")  # Section が消えた
        result = check_regression(str(f), original)
        assert result["passed"] is False
        assert any("見出し" in i for i in result["issues"])

    def test_check_regression_ok(self, tmp_path):
        """見出し構造が保持されている場合 → OK。"""
        f = tmp_path / "MEMORY.md"
        original = "# Title\n\n## Section\n\nLine 1\nLine 2\n"
        f.write_text("# Title\n\n## Section\n\nLine 1\n")
        result = check_regression(str(f), original)
        assert result["passed"] is True

    def test_rollback_restores_content(self, tmp_path):
        """ロールバックでファイルが元に戻る。"""
        f = tmp_path / "MEMORY.md"
        original = "original content"
        f.write_text("modified content")
        assert rollback_fix(str(f), original) is True
        assert f.read_text() == original


# ---------- テレメトリテスト ----------

class TestTelemetry:
    def test_record_outcome_writes(self, tmp_path, monkeypatch):
        """正常記録。"""
        monkeypatch.setattr("remediation.DATA_DIR", tmp_path)
        issue = {
            "type": "stale_ref",
            "confidence_score": 0.95,
            "impact_scope": "file",
            "file": "/project/.claude/memory/MEMORY.md",
        }
        result = record_outcome(
            issue, "auto_fixable", "delete_line", "success", "approved",
            "テスト理由",
        )
        assert result is not None
        assert result["result"] == "success"

        outcomes_file = tmp_path / "remediation-outcomes.jsonl"
        assert outcomes_file.exists()
        records = [json.loads(l) for l in outcomes_file.read_text().splitlines()]
        assert len(records) == 1
        assert records[0]["issue_type"] == "stale_ref"

    def test_record_outcome_dry_run_skips(self, tmp_path, monkeypatch):
        """dry-run 時は記録しない。"""
        monkeypatch.setattr("remediation.DATA_DIR", tmp_path)
        issue = {"type": "stale_ref", "file": "x"}
        result = record_outcome(
            issue, "auto_fixable", "delete_line", "success", "approved",
            "理由", dry_run=True,
        )
        assert result is None
        outcomes_file = tmp_path / "remediation-outcomes.jsonl"
        assert not outcomes_file.exists()

    def test_record_outcome_with_extended_metadata(self, tmp_path, monkeypatch):
        """fix_detail, verify_result, duration_ms が記録される。"""
        monkeypatch.setattr("remediation.DATA_DIR", tmp_path)
        issue = {
            "type": "stale_ref",
            "confidence_score": 0.95,
            "impact_scope": "file",
            "file": "/project/.claude/memory/MEMORY.md",
        }
        fix_detail = {"changed_files": ["MEMORY.md"], "lines_removed": 1, "lines_added": 0}
        verify_result = {"resolved": True}
        result = record_outcome(
            issue, "auto_fixable", "delete_line", "success", "approved",
            "テスト理由",
            fix_detail=fix_detail,
            verify_result=verify_result,
            duration_ms=150,
        )
        assert result is not None
        assert result["fix_detail"] == fix_detail
        assert result["verify_result"] == verify_result
        assert result["duration_ms"] == 150

        outcomes_file = tmp_path / "remediation-outcomes.jsonl"
        records = [json.loads(l) for l in outcomes_file.read_text().splitlines()]
        assert records[0]["fix_detail"]["lines_removed"] == 1
        assert records[0]["duration_ms"] == 150

    def test_record_outcome_fix_failed(self, tmp_path, monkeypatch):
        """fix_failed result が正しく記録される。"""
        monkeypatch.setattr("remediation.DATA_DIR", tmp_path)
        issue = {"type": "stale_ref", "confidence_score": 0.95, "impact_scope": "file", "file": "x"}
        result = record_outcome(
            issue, "auto_fixable", "delete_line", "fix_failed", "approved",
            "修正失敗",
            verify_result={"resolved": False, "remaining": "参照がまだ存在"},
        )
        assert result["result"] == "fix_failed"
        assert result["verify_result"]["resolved"] is False

    def test_record_outcome_rejected(self, tmp_path, monkeypatch):
        """rejected result が正しく記録される。"""
        monkeypatch.setattr("remediation.DATA_DIR", tmp_path)
        issue = {"type": "orphan_rule", "confidence_score": 0.5, "impact_scope": "file", "file": "x"}
        result = record_outcome(
            issue, "proposable", "propose_delete", "rejected", "rejected",
            "ユーザーが却下",
        )
        assert result["result"] == "rejected"
        assert result["user_decision"] == "rejected"

    def test_record_outcome_without_optional_fields(self, tmp_path, monkeypatch):
        """optional フィールド未指定時は record に含まれない。"""
        monkeypatch.setattr("remediation.DATA_DIR", tmp_path)
        issue = {"type": "stale_ref", "file": "x"}
        result = record_outcome(
            issue, "auto_fixable", "delete_line", "success", "approved", "理由",
        )
        assert "fix_detail" not in result
        assert "verify_result" not in result
        assert "duration_ms" not in result


# ---------- 6.1: fix_stale_rules / fix_claudemd_phantom_refs / fix_claudemd_missing_section テスト ----------

class TestFixStaleRules:
    def test_removes_stale_path_line(self, tmp_path):
        """ルール内の不存在パス参照行が削除される。"""
        f = tmp_path / "test-rule.md"
        f.write_text("# ルール\nSee scripts/old.py\nValid line\n")
        issues = [{
            "type": "stale_rule",
            "file": str(f),
            "detail": {"line": 2, "path": "scripts/old.py"},
            "source": "diagnose",
        }]
        results = fix_stale_rules(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is True
        content = f.read_text()
        assert "scripts/old.py" not in content
        assert "Valid line" in content

    def test_preserves_original(self, tmp_path):
        """original_content が保持される。"""
        f = tmp_path / "test-rule.md"
        original = "# ルール\nSee scripts/old.py\n"
        f.write_text(original)
        issues = [{
            "type": "stale_rule",
            "file": str(f),
            "detail": {"line": 2, "path": "scripts/old.py"},
            "source": "diagnose",
        }]
        results = fix_stale_rules(issues)
        assert results[0]["original_content"] == original

    def test_ignores_non_stale_rule_type(self, tmp_path):
        """stale_rule 以外の type は無視される。"""
        f = tmp_path / "test.md"
        f.write_text("content\n")
        issues = [{
            "type": "stale_ref",
            "file": str(f),
            "detail": {"line": 1},
            "source": "s",
        }]
        results = fix_stale_rules(issues)
        assert len(results) == 0

    def test_file_not_found(self):
        """存在しないファイル → error。"""
        issues = [{
            "type": "stale_rule",
            "file": "/nonexistent/rule.md",
            "detail": {"line": 1, "path": "x"},
            "source": "diagnose",
        }]
        results = fix_stale_rules(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is False
        assert results[0]["error"] is not None


class TestFixClaudemdPhantomRefs:
    def test_removes_phantom_ref_line(self, tmp_path):
        """phantom_ref の行が削除される。"""
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Project\n\n- old-skill: 説明\n\n- valid: 説明\n")
        issues = [{
            "type": "claudemd_phantom_ref",
            "file": str(f),
            "detail": {"line": 3, "name": "old-skill", "ref_type": "skill"},
            "source": "diagnose",
        }]
        results = fix_claudemd_phantom_refs(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is True
        content = f.read_text()
        assert "old-skill" not in content
        assert "valid" in content

    def test_normalizes_consecutive_blank_lines(self, tmp_path):
        """連続空行が正規化される。"""
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Title\n\n\n\nContent\n")
        issues = [{
            "type": "claudemd_phantom_ref",
            "file": str(f),
            "detail": {"line": 3, "name": "x", "ref_type": "skill"},
            "source": "diagnose",
        }]
        fix_claudemd_phantom_refs(issues)
        content = f.read_text()
        assert "\n\n\n" not in content


class TestFixClaudemdMissingSection:
    def test_adds_skills_section(self, tmp_path):
        """Skills セクションヘッダが追加される。"""
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Project\n\nDescription\n")
        issues = [{
            "type": "claudemd_missing_section",
            "file": str(f),
            "detail": {"section": "skills", "skill_count": 3},
            "source": "diagnose",
        }]
        results = fix_claudemd_missing_section(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is True
        content = f.read_text()
        assert "## Skills" in content

    def test_deduplicates_same_file(self, tmp_path):
        """同一ファイルに対する複数 issue は1回だけ修正。"""
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Project\n")
        issues = [
            {"type": "claudemd_missing_section", "file": str(f),
             "detail": {"section": "skills", "skill_count": 3}, "source": "d"},
            {"type": "claudemd_missing_section", "file": str(f),
             "detail": {"section": "skills", "skill_count": 3}, "source": "d"},
        ]
        results = fix_claudemd_missing_section(issues)
        assert len(results) == 1


# ---------- 6.2: FIX_DISPATCH テスト ----------

class TestFixDispatch:
    def test_stale_ref_dispatch(self):
        assert FIX_DISPATCH["stale_ref"] is fix_stale_references

    def test_stale_rule_dispatch(self):
        assert FIX_DISPATCH["stale_rule"] is fix_stale_rules

    def test_claudemd_phantom_ref_dispatch(self):
        assert FIX_DISPATCH["claudemd_phantom_ref"] is fix_claudemd_phantom_refs

    def test_claudemd_missing_section_dispatch(self):
        assert FIX_DISPATCH["claudemd_missing_section"] is fix_claudemd_missing_section

    def test_unknown_type_raises_key_error(self):
        with pytest.raises(KeyError):
            FIX_DISPATCH["unknown_type"]


# ---------- 6.3: VERIFY_DISPATCH テスト ----------

class TestVerifyDispatch:
    def test_stale_ref_dispatch(self):
        assert VERIFY_DISPATCH["stale_ref"] is not None

    def test_stale_rule_dispatch(self):
        assert VERIFY_DISPATCH["stale_rule"] is not None

    def test_claudemd_phantom_ref_dispatch(self):
        assert VERIFY_DISPATCH["claudemd_phantom_ref"] is not None

    def test_claudemd_missing_section_dispatch(self):
        assert VERIFY_DISPATCH["claudemd_missing_section"] is not None

    def test_stale_memory_dispatch(self):
        assert VERIFY_DISPATCH["stale_memory"] is not None

    def test_unknown_type_not_in_dispatch(self):
        assert "unknown_type" not in VERIFY_DISPATCH


# ---------- 6.4: generate_proposals の全レイヤー対応テスト ----------

class TestGenerateProposalsAllLayers:
    def test_orphan_rule_proposal(self):
        issues = [{
            "type": "orphan_rule",
            "file": "/project/.claude/rules/old.md",
            "detail": {"name": "old-rule"},
            "category": "proposable",
        }]
        proposals = generate_proposals(issues)
        assert len(proposals) == 1
        assert "old-rule" in proposals[0]["proposal"]
        assert "削除" in proposals[0]["proposal"]

    def test_stale_memory_proposal(self):
        issues = [{
            "type": "stale_memory",
            "file": "/project/.claude/memory/MEMORY.md",
            "detail": {"path": "scripts/old_module.py"},
            "category": "proposable",
        }]
        proposals = generate_proposals(issues)
        assert len(proposals) == 1
        assert "scripts/old_module.py" in proposals[0]["proposal"]

    def test_memory_duplicate_proposal(self):
        issues = [{
            "type": "memory_duplicate",
            "file": "/project/.claude/memory/MEMORY.md",
            "detail": {"sections": ["Section A", "Section B"], "similarity": 0.85},
            "category": "proposable",
        }]
        proposals = generate_proposals(issues)
        assert len(proposals) == 1
        assert "Section A" in proposals[0]["proposal"]
        assert "Section B" in proposals[0]["proposal"]
        assert "統合" in proposals[0]["proposal"]

    def test_line_limit_violation_still_works(self):
        """既存の line_limit_violation もそのまま動作する。"""
        issues = [{
            "type": "line_limit_violation",
            "file": "/project/.claude/skills/big/SKILL.md",
            "detail": {"lines": 600, "limit": 500},
            "category": "proposable",
        }]
        proposals = generate_proposals(issues)
        assert len(proposals) == 1
        assert "600" in proposals[0]["proposal"]


# ---------- 6.5: verify_fix の全レイヤー対応テスト ----------

class TestVerifyFixAllLayers:
    def test_stale_rule_resolved(self, tmp_path):
        f = tmp_path / "rule.md"
        f.write_text("# Rule\nValid content\n")
        issue = {"type": "stale_rule", "detail": {"path": "scripts/old.py"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is True

    def test_stale_rule_not_resolved(self, tmp_path):
        f = tmp_path / "rule.md"
        f.write_text("# Rule\nSee scripts/old.py\n")
        issue = {"type": "stale_rule", "detail": {"path": "scripts/old.py"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is False

    def test_claudemd_phantom_ref_resolved(self, tmp_path):
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Project\n\nValid content\n")
        issue = {"type": "claudemd_phantom_ref", "detail": {"name": "old-skill", "ref_type": "skill"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is True

    def test_claudemd_phantom_ref_not_resolved(self, tmp_path):
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Project\n\n- old-skill: desc\n")
        issue = {"type": "claudemd_phantom_ref", "detail": {"name": "old-skill", "ref_type": "skill"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is False

    def test_claudemd_missing_section_resolved(self, tmp_path):
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Project\n\n## Skills\n\n- skill1\n")
        issue = {"type": "claudemd_missing_section", "detail": {"section": "skills"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is True

    def test_claudemd_missing_section_not_resolved(self, tmp_path):
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Project\n\nNo skills section\n")
        issue = {"type": "claudemd_missing_section", "detail": {"section": "skills"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is False

    def test_stale_memory_resolved(self, tmp_path):
        f = tmp_path / "MEMORY.md"
        f.write_text("# Memory\n\nValid content\n")
        issue = {"type": "stale_memory", "detail": {"path": "old/module.py"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is True

    def test_stale_memory_not_resolved(self, tmp_path):
        f = tmp_path / "MEMORY.md"
        f.write_text("# Memory\n\nSee old/module.py here\n")
        issue = {"type": "stale_memory", "detail": {"path": "old/module.py"}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is False

    def test_unknown_type_skips(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("content\n")
        issue = {"type": "unknown_new_type", "detail": {}}
        result = verify_fix(str(f), issue)
        assert result["resolved"] is True


# ---------- 6.6: check_regression の Rules 行数チェックテスト ----------

class TestCheckRegressionRulesLineLimit:
    def test_rules_within_limit(self, tmp_path):
        """Rules ファイルが行数制限内 → pass。"""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        f = rules_dir / "test.md"
        f.write_text("# Rule\nLine 1\nLine 2\n")
        original = "# Rule\nOriginal\n"
        result = check_regression(str(f), original)
        assert result["passed"] is True

    def test_rules_exceeds_limit(self, tmp_path):
        """Rules ファイルが行数制限超過 → fail。"""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        f = rules_dir / "test.md"
        # MAX_RULE_LINES=3 なので 4行以上で超過
        f.write_text("# Rule\nLine 1\nLine 2\nLine 3\nLine 4\n")
        original = "# Rule\nLine 1\nLine 2\nLine 3\nLine 4\n"
        result = check_regression(str(f), original)
        assert result["passed"] is False
        assert any("行数制限" in i for i in result["issues"])

    def test_non_rules_file_no_line_check(self, tmp_path):
        """Rules 以外のファイルは行数チェックしない。"""
        f = tmp_path / "MEMORY.md"
        content = "\n".join([f"Line {i}" for i in range(100)]) + "\n"
        f.write_text(content)
        result = check_regression(str(f), content)
        assert result["passed"] is True


# ---------- tool_usage 関連: confidence_score テスト ----------

class TestToolUsageConfidenceScore:
    def test_tool_usage_rule_candidate_score(self):
        """tool_usage_rule_candidate → 0.85。"""
        issue = {"type": TOOL_USAGE_RULE_CANDIDATE, "detail": {}}
        score = compute_confidence_score(issue)
        assert score == 0.85

    def test_tool_usage_hook_candidate_score(self):
        """tool_usage_hook_candidate → 0.75。"""
        issue = {"type": TOOL_USAGE_HOOK_CANDIDATE, "detail": {}}
        score = compute_confidence_score(issue)
        assert score == 0.75


# ---------- tool_usage 関連: classify_issue テスト ----------

class TestToolUsageClassification:
    def test_tool_usage_rule_candidate_global_scope_is_proposable(self):
        """global scope の tool_usage_rule_candidate → proposable。"""
        home = str(Path.home())
        issue = {
            "type": TOOL_USAGE_RULE_CANDIDATE,
            "file": f"{home}/.claude/rules/avoid-bash-builtin.md",
            "detail": {
                RULE_FILENAME: "avoid-bash-builtin.md",
                RULE_CONTENT: "# Rule\nContent\n",
                RULE_TARGET_COMMANDS: ["grep", "cat"],
                RULE_TOTAL_COUNT: 15,
            },
            "source": "tool_usage_analyzer",
        }
        result = classify_issue(issue)
        assert result["category"] == "proposable"
        assert result["impact_scope"] == "global"
        assert result["confidence_score"] == 0.85

    def test_tool_usage_hook_candidate_global_scope_is_proposable(self):
        """global scope の tool_usage_hook_candidate → proposable。"""
        home = str(Path.home())
        issue = {
            "type": TOOL_USAGE_HOOK_CANDIDATE,
            "file": f"{home}/.claude/hooks/check-bash-builtin.py",
            "detail": {
                HOOK_SCRIPT_PATH: f"{home}/.claude/hooks/check-bash-builtin.py",
                HOOK_SCRIPT_CONTENT: "#!/usr/bin/env python3\n",
                HOOK_TOTAL_COUNT: 20,
            },
            "source": "tool_usage_analyzer",
        }
        result = classify_issue(issue)
        assert result["category"] == "proposable"
        assert result["impact_scope"] == "global"
        assert result["confidence_score"] == 0.75


# ---------- tool_usage 関連: rationale テスト ----------

class TestToolUsageRationale:
    def test_tool_usage_rule_candidate_rationale(self):
        issue = {
            "type": TOOL_USAGE_RULE_CANDIDATE,
            "detail": {
                RULE_TARGET_COMMANDS: ["grep", "cat"],
                RULE_TOTAL_COUNT: 15,
                RULE_ALTERNATIVE_TOOLS: ["Grep", "Read"],
            },
        }
        r = generate_rationale(issue, "proposable")
        assert "grep" in r
        assert "cat" in r
        assert "15" in r
        assert "Grep" in r or "Read" in r

    def test_tool_usage_hook_candidate_rationale(self):
        issue = {
            "type": TOOL_USAGE_HOOK_CANDIDATE,
            "detail": {HOOK_TOTAL_COUNT: 20},
        }
        r = generate_rationale(issue, "proposable")
        assert "20" in r
        assert "hook" in r.lower() or "Hook" in r


# ---------- tool_usage 関連: fix_global_rule テスト ----------

class TestFixGlobalRule:
    def test_writes_rule_file(self, tmp_path, monkeypatch):
        """rule ファイルが正しく書き込まれる。"""
        monkeypatch.setattr("remediation.Path.home", lambda: tmp_path)
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)

        issues = [{
            "type": TOOL_USAGE_RULE_CANDIDATE,
            "file": str(rules_dir / "avoid-bash-builtin.md"),
            "detail": {
                RULE_FILENAME: "avoid-bash-builtin.md",
                RULE_CONTENT: "# Bash Built-in 代替コマンド禁止\ngrep は Grep を使用する。\nパイプは Bash で OK。\n",
            },
        }]
        results = fix_global_rule(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is True
        written = (rules_dir / "avoid-bash-builtin.md").read_text()
        assert "Bash Built-in" in written
        assert "grep" in written

    def test_skips_non_matching_type(self, tmp_path, monkeypatch):
        """type が tool_usage_rule_candidate でない場合は無視。"""
        monkeypatch.setattr("remediation.Path.home", lambda: tmp_path)
        issues = [{
            "type": "stale_ref",
            "file": "/tmp/test.md",
            "detail": {"filename": "test.md", "content": "content"},
        }]
        results = fix_global_rule(issues)
        assert len(results) == 0

    def test_error_on_missing_content(self, tmp_path, monkeypatch):
        """filename or content 未指定 → error。"""
        monkeypatch.setattr("remediation.Path.home", lambda: tmp_path)
        issues = [{
            "type": TOOL_USAGE_RULE_CANDIDATE,
            "file": "/tmp/test.md",
            "detail": {RULE_FILENAME: "", RULE_CONTENT: ""},
        }]
        results = fix_global_rule(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is False
        assert "missing" in results[0]["error"]


# ---------- tool_usage 関連: fix_hook_scaffold テスト ----------

class TestFixHookScaffold:
    def test_writes_hook_script(self, tmp_path):
        """hook スクリプトが正しく書き込まれる。"""
        script_path = tmp_path / "hooks" / "check-bash-builtin.py"
        issues = [{
            "type": TOOL_USAGE_HOOK_CANDIDATE,
            "file": str(script_path),
            "detail": {
                HOOK_SCRIPT_PATH: str(script_path),
                HOOK_SCRIPT_CONTENT: "#!/usr/bin/env python3\n# hook script\nprint('hello')\n",
                HOOK_SETTINGS_DIFF: '{"hooks": {}}',
            },
        }]
        results = fix_hook_scaffold(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is True
        assert script_path.exists()
        content = script_path.read_text()
        assert "#!/usr/bin/env python3" in content
        assert results[0]["settings_diff"] == '{"hooks": {}}'

    def test_skips_non_matching_type(self):
        """type が tool_usage_hook_candidate でない場合は無視。"""
        issues = [{
            "type": "stale_ref",
            "file": "/tmp/test.py",
            "detail": {"script_path": "/tmp/test.py", "script_content": "x"},
        }]
        results = fix_hook_scaffold(issues)
        assert len(results) == 0

    def test_error_on_missing_script_content(self, tmp_path):
        """script_path or script_content 未指定 → error。"""
        issues = [{
            "type": TOOL_USAGE_HOOK_CANDIDATE,
            "file": "/tmp/test.py",
            "detail": {HOOK_SCRIPT_PATH: "", HOOK_SCRIPT_CONTENT: ""},
        }]
        results = fix_hook_scaffold(issues)
        assert len(results) == 1
        assert results[0]["fixed"] is False
        assert "missing" in results[0]["error"]


# ---------- tool_usage 関連: FIX_DISPATCH / VERIFY_DISPATCH テスト ----------

class TestToolUsageDispatch:
    def test_fix_dispatch_rule_candidate(self):
        assert FIX_DISPATCH[TOOL_USAGE_RULE_CANDIDATE] is fix_global_rule

    def test_fix_dispatch_hook_candidate(self):
        assert FIX_DISPATCH[TOOL_USAGE_HOOK_CANDIDATE] is fix_hook_scaffold

    def test_verify_dispatch_rule_candidate(self):
        assert VERIFY_DISPATCH[TOOL_USAGE_RULE_CANDIDATE] is not None

    def test_verify_dispatch_hook_candidate(self):
        assert VERIFY_DISPATCH[TOOL_USAGE_HOOK_CANDIDATE] is not None


# ---------- tool_usage 関連: generate_proposals テスト ----------

class TestToolUsageProposals:
    def test_rule_candidate_proposal(self):
        issues = [{
            "type": TOOL_USAGE_RULE_CANDIDATE,
            "file": "~/.claude/rules/avoid-bash-builtin.md",
            "detail": {
                RULE_FILENAME: "avoid-bash-builtin.md",
                RULE_TARGET_COMMANDS: ["grep", "cat"],
                RULE_TOTAL_COUNT: 15,
            },
            "category": "proposable",
        }]
        proposals = generate_proposals(issues)
        assert len(proposals) == 1
        assert "grep" in proposals[0]["proposal"]
        assert "cat" in proposals[0]["proposal"]
        assert "avoid-bash-builtin.md" in proposals[0]["proposal"]

    def test_hook_candidate_proposal(self):
        issues = [{
            "type": TOOL_USAGE_HOOK_CANDIDATE,
            "file": "~/.claude/hooks/check-bash-builtin.py",
            "detail": {
                HOOK_SCRIPT_PATH: "~/.claude/hooks/check-bash-builtin.py",
                HOOK_TOTAL_COUNT: 20,
            },
            "category": "proposable",
        }]
        proposals = generate_proposals(issues)
        assert len(proposals) == 1
        assert "hook" in proposals[0]["proposal"].lower() or "Hook" in proposals[0]["proposal"]
        assert "check-bash-builtin.py" in proposals[0]["proposal"]
