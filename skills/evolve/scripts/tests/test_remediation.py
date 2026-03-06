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
    generate_proposals,
    verify_fix,
    check_regression,
    rollback_fix,
    record_outcome,
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

    def test_stale_ref_in_claude_md_is_proposable(self):
        """CLAUDE.md 内の陳腐化参照 → proposable に格上げ。"""
        issue = {
            "type": "stale_ref",
            "file": "/project/CLAUDE.md",
            "detail": {"line": 10, "path": "skills/old/SKILL.md"},
            "source": "build_memory_health_section",
        }
        result = classify_issue(issue)
        assert result["category"] == "proposable"
        assert result["impact_scope"] == "project"

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

    def test_global_scope_is_manual_required(self):
        """グローバルスコープの問題 → manual_required。"""
        home = str(Path.home())
        issue = {
            "type": "stale_ref",
            "file": f"{home}/.claude/rules/old-rule.md",
            "detail": {"line": 1, "path": "nonexistent"},
            "source": "build_memory_health_section",
        }
        result = classify_issue(issue)
        assert result["category"] == "manual_required"
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
