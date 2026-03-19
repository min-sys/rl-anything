"""Tests for workflow_checkpoint.py — ワークフローチェックポイント検出。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.workflow_checkpoint import (
    BASE_CHECKPOINT_CONFIDENCE,
    CHECKPOINT_CATALOG,
    CHECKPOINT_DETECTION_TIMEOUT_SECONDS,
    EVIDENCE_BONUS_PER_COUNT,
    GATE_BONUS,
    MAX_EVIDENCE_BONUS,
    MIN_CHECKPOINT_EVIDENCE,
    _CHECKPOINT_DETECTION_DISPATCH,
    detect_checkpoint_gaps,
    get_checkpoint_template,
    is_workflow_skill,
)


# ── is_workflow_skill ─────────────────────────────────


class TestIsWorkflowSkill:
    """Workflow skill identification tests."""

    def test_frontmatter_type_workflow(self, tmp_path):
        """frontmatter type: workflow → 即 True。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ntype: workflow\n---\n\n# My Skill\nDoes stuff.\n"
        )
        assert is_workflow_skill(skill_dir) is True

    def test_step_keywords_with_numbered_list(self, tmp_path):
        """基準A+B: Step キーワード + numbered list 3項目以上 → True。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# My Skill\n\n"
            "1. Step 1: Analyze the code\n"
            "2. Step 2: Generate report\n"
            "3. Step 3: Apply changes\n"
        )
        assert is_workflow_skill(skill_dir) is True

    def test_phase_keywords_with_numbered_list(self, tmp_path):
        """Phase キーワード + numbered list → True。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# My Skill\n\n"
            "1. Phase 1: Diagnose\n"
            "2. Phase 2: Compile\n"
            "3. Phase 3: Report\n"
        )
        assert is_workflow_skill(skill_dir) is True

    def test_japanese_step_keywords(self, tmp_path):
        """ステップ/フェーズ キーワード → True。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# マイスキル\n\n"
            "1. ステップ1: 分析\n"
            "2. ステップ2: 生成\n"
            "3. ステップ3: 適用\n"
        )
        assert is_workflow_skill(skill_dir) is True

    def test_step_keyword_with_5_items_no_criteria_b(self, tmp_path):
        """基準A + numbered list 5項目以上（基準B なし）→ True。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        # Step keyword exists, 5+ numbered items
        (skill_dir / "SKILL.md").write_text(
            "# My Skill\n\n"
            "Steps overview:\n"
            "1. First thing\n"
            "2. Second thing\n"
            "3. Third thing\n"
            "4. Fourth thing\n"
            "5. Fifth thing\n"
        )
        assert is_workflow_skill(skill_dir) is True

    def test_simple_utility_skill(self, tmp_path):
        """単一操作のユーティリティスキル → False。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# Version Check\n\nDisplay the installed version.\n"
        )
        assert is_workflow_skill(skill_dir) is False

    def test_no_skill_md(self, tmp_path):
        """SKILL.md が存在しない → False。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        assert is_workflow_skill(skill_dir) is False

    def test_numbered_list_without_step_keywords(self, tmp_path):
        """numbered list あるが Step/Phase キーワードなし → False。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# My Skill\n\n"
            "1. Read the file\n"
            "2. Parse the content\n"
            "3. Output the result\n"
        )
        assert is_workflow_skill(skill_dir) is False

    def test_input_output_keywords_alone_not_sufficient(self, tmp_path):
        """基準C だけでは True にならない。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# My Skill\n\nInput: a file\nOutput: processed file\n"
        )
        assert is_workflow_skill(skill_dir) is False


# ── CHECKPOINT_CATALOG ────────────────────────────────


class TestCheckpointCatalog:
    """Catalog structure and lookup tests."""

    def test_catalog_has_four_categories(self):
        categories = {e["category"] for e in CHECKPOINT_CATALOG}
        assert categories == {
            "infra_deploy",
            "data_migration",
            "external_api",
            "secret_rotation",
        }

    def test_catalog_entry_fields(self):
        required_fields = {"id", "category", "description", "detection_fn", "applicability", "template"}
        for entry in CHECKPOINT_CATALOG:
            assert required_fields.issubset(entry.keys()), f"Missing fields in {entry.get('id')}"

    def test_detection_fn_dispatch_resolves(self):
        """全 detection_fn が dispatch dict で解決可能。"""
        for entry in CHECKPOINT_CATALOG:
            fn_name = entry["detection_fn"]
            assert fn_name in _CHECKPOINT_DETECTION_DISPATCH, f"{fn_name} not in dispatch"

    def test_get_checkpoint_template_found(self):
        result = get_checkpoint_template("infra_deploy")
        assert result is not None
        assert result["category"] == "infra_deploy"
        assert "template" in result

    def test_get_checkpoint_template_not_found(self):
        result = get_checkpoint_template("unknown_category")
        assert result is None


# ── detect_checkpoint_gaps ─────────────────────────────


class TestDetectCheckpointGaps:
    """Checkpoint gap detection tests."""

    def _make_corrections_file(self, data_dir, records):
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(data_dir / "corrections.jsonl", "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def _make_errors_file(self, data_dir, records):
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(data_dir / "errors.jsonl", "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def _make_skill(self, skill_dir, content="# Verify\n\n1. Step 1: Check\n2. Step 2: Validate\n3. Step 3: Report\n"):
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content)

    def test_infra_deploy_gap_detected(self, tmp_path):
        """IaC PJ + deploy 関連 corrections 3件 → infra_deploy ギャップ検出。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "cdk.json").write_text("{}")

        skill_dir = tmp_path / "skill"
        self._make_skill(skill_dir)

        data_dir = tmp_path / "data"
        corrections = [
            {"last_skill": "verify", "correction": "prodデプロイ忘れた", "timestamp": "2026-03-01T00:00:00"},
            {"last_skill": "verify", "correction": "deploy確認漏れ", "timestamp": "2026-03-02T00:00:00"},
            {"last_skill": "verify", "correction": "本番にデプロイしてなかった", "timestamp": "2026-03-03T00:00:00"},
        ]
        self._make_corrections_file(data_dir, corrections)

        with mock.patch("lib.workflow_checkpoint.DATA_DIR", data_dir):
            gaps = detect_checkpoint_gaps("verify", skill_dir, project_dir)

        infra_gaps = [g for g in gaps if g["category"] == "infra_deploy"]
        assert len(infra_gaps) == 1
        assert infra_gaps[0]["evidence_count"] >= 3
        assert infra_gaps[0]["confidence"] >= 0.75

    def test_no_gaps_found(self, tmp_path):
        """テレメトリにマッチなし → 空リスト。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        skill_dir = tmp_path / "skill"
        self._make_skill(skill_dir)

        data_dir = tmp_path / "data"
        corrections = [
            {"last_skill": "verify", "correction": "typo修正", "timestamp": "2026-03-01T00:00:00"},
        ]
        self._make_corrections_file(data_dir, corrections)

        with mock.patch("lib.workflow_checkpoint.DATA_DIR", data_dir):
            gaps = detect_checkpoint_gaps("verify", skill_dir, project_dir)

        assert gaps == []

    def test_gap_already_covered(self, tmp_path):
        """SKILL.md に既存デプロイ確認ステップあり → ギャップなし。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "cdk.json").write_text("{}")

        skill_dir = tmp_path / "skill"
        self._make_skill(
            skill_dir,
            "# Verify\n\n1. Step 1: Check\n2. Step 2: デプロイ確認\n3. Step 3: Report\n",
        )

        data_dir = tmp_path / "data"
        corrections = [
            {"last_skill": "verify", "correction": "deploy漏れ", "timestamp": "2026-03-01T00:00:00"},
            {"last_skill": "verify", "correction": "デプロイ忘れ", "timestamp": "2026-03-02T00:00:00"},
            {"last_skill": "verify", "correction": "prod deploy", "timestamp": "2026-03-03T00:00:00"},
        ]
        self._make_corrections_file(data_dir, corrections)

        with mock.patch("lib.workflow_checkpoint.DATA_DIR", data_dir):
            gaps = detect_checkpoint_gaps("verify", skill_dir, project_dir)

        infra_gaps = [g for g in gaps if g["category"] == "infra_deploy"]
        assert len(infra_gaps) == 0

    def test_evidence_below_threshold(self, tmp_path):
        """evidence 1件 → 検出されない。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "cdk.json").write_text("{}")

        skill_dir = tmp_path / "skill"
        self._make_skill(skill_dir)

        data_dir = tmp_path / "data"
        corrections = [
            {"last_skill": "verify", "correction": "deploy忘れ", "timestamp": "2026-03-01T00:00:00"},
        ]
        self._make_corrections_file(data_dir, corrections)

        with mock.patch("lib.workflow_checkpoint.DATA_DIR", data_dir):
            gaps = detect_checkpoint_gaps("verify", skill_dir, project_dir)

        assert gaps == []

    def test_telemetry_missing(self, tmp_path):
        """テレメトリファイル不在 → 空リスト（エラーなし）。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        skill_dir = tmp_path / "skill"
        self._make_skill(skill_dir)

        data_dir = tmp_path / "nonexistent"
        with mock.patch("lib.workflow_checkpoint.DATA_DIR", data_dir):
            gaps = detect_checkpoint_gaps("verify", skill_dir, project_dir)

        assert gaps == []

    def test_non_iac_project_skips_infra_deploy(self, tmp_path):
        """非 IaC PJ → infra_deploy は適用対象外。"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        # No cdk.json

        skill_dir = tmp_path / "skill"
        self._make_skill(skill_dir)

        data_dir = tmp_path / "data"
        corrections = [
            {"last_skill": "verify", "correction": "deploy漏れ", "timestamp": "2026-03-01T00:00:00"},
            {"last_skill": "verify", "correction": "デプロイ忘れ", "timestamp": "2026-03-02T00:00:00"},
            {"last_skill": "verify", "correction": "prod deploy", "timestamp": "2026-03-03T00:00:00"},
        ]
        self._make_corrections_file(data_dir, corrections)

        with mock.patch("lib.workflow_checkpoint.DATA_DIR", data_dir):
            gaps = detect_checkpoint_gaps("verify", skill_dir, project_dir)

        infra_gaps = [g for g in gaps if g["category"] == "infra_deploy"]
        assert len(infra_gaps) == 0


# ── confidence scoring ────────────────────────────────


class TestConfidenceScoring:
    """Confidence score calculation tests."""

    def test_constants(self):
        assert BASE_CHECKPOINT_CONFIDENCE == 0.5
        assert EVIDENCE_BONUS_PER_COUNT == 0.05
        assert MAX_EVIDENCE_BONUS == 0.25
        assert GATE_BONUS == 0.1

    def test_high_evidence_with_gate(self):
        """6件 + gate → 0.85。"""
        score = BASE_CHECKPOINT_CONFIDENCE + min(6 * EVIDENCE_BONUS_PER_COUNT, MAX_EVIDENCE_BONUS) + GATE_BONUS
        assert score == pytest.approx(0.85)

    def test_low_evidence_no_gate(self):
        """2件 + no gate → 0.60。"""
        score = BASE_CHECKPOINT_CONFIDENCE + min(2 * EVIDENCE_BONUS_PER_COUNT, MAX_EVIDENCE_BONUS)
        assert score == pytest.approx(0.60)

    def test_timeout(self):
        assert CHECKPOINT_DETECTION_TIMEOUT_SECONDS == 5

    def test_min_evidence(self):
        assert MIN_CHECKPOINT_EVIDENCE == 2


# ── issue_schema integration ──────────────────────────


class TestIssueSchema:
    """issue_schema の workflow_checkpoint 対応テスト。"""

    def test_make_workflow_checkpoint_issue(self):
        from lib.issue_schema import (
            WORKFLOW_CHECKPOINT_CANDIDATE,
            WCC_CATEGORY,
            WCC_CONFIDENCE,
            WCC_EVIDENCE_COUNT,
            WCC_SKILL_NAME,
            WCC_TEMPLATE,
            make_workflow_checkpoint_issue,
        )

        gap = {
            "category": "infra_deploy",
            "evidence_count": 3,
            "confidence": 0.75,
            "template": "Deploy check step",
            "description": "インフラデプロイ確認",
        }
        issue = make_workflow_checkpoint_issue(
            gap, skill_name="verify", skill_dir="/path/to/skill",
        )
        assert issue["type"] == WORKFLOW_CHECKPOINT_CANDIDATE
        assert issue["file"] == ".claude/skills/verify/SKILL.md"
        assert issue["detail"][WCC_SKILL_NAME] == "verify"
        assert issue["detail"][WCC_CATEGORY] == "infra_deploy"
        assert issue["detail"][WCC_EVIDENCE_COUNT] == 3
        assert issue["detail"][WCC_CONFIDENCE] == 0.75
        assert issue["detail"][WCC_TEMPLATE] == "Deploy check step"
        assert issue["source"] == "workflow_checkpoint"
