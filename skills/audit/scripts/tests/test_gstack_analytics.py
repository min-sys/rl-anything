"""gstack Workflow Analytics のテスト。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from audit import (
    _GSTACK_LIFECYCLE,
    _is_gstack_skill,
    _match_gstack_phase,
    build_gstack_analytics_section,
)


class TestIsGstackSkill:
    """_is_gstack_skill のテスト。"""

    def test_ship(self):
        assert _is_gstack_skill("ship") is True

    def test_document_release(self):
        assert _is_gstack_skill("document-release") is True

    def test_spec_keeper(self):
        assert _is_gstack_skill("spec-keeper") is True

    def test_retro(self):
        assert _is_gstack_skill("retro") is True

    def test_gstack_refine(self):
        assert _is_gstack_skill("gstack-refine") is True

    def test_office_hours(self):
        assert _is_gstack_skill("office-hours") is True

    def test_plan_eng_review(self):
        assert _is_gstack_skill("plan-eng-review") is True

    def test_plan_ceo_review(self):
        assert _is_gstack_skill("plan-ceo-review") is True

    def test_plan_design_review(self):
        assert _is_gstack_skill("plan-design-review") is True

    def test_non_gstack_skill(self):
        assert _is_gstack_skill("evolve") is False

    def test_non_gstack_discover(self):
        assert _is_gstack_skill("discover") is False

    def test_empty(self):
        assert _is_gstack_skill("") is False


class TestMatchGstackPhase:
    """_match_gstack_phase のテスト。"""

    def test_plan_phase(self):
        assert _match_gstack_phase("office-hours") == "plan"
        assert _match_gstack_phase("plan-eng-review") == "plan"
        assert _match_gstack_phase("plan-ceo-review") == "plan"
        assert _match_gstack_phase("plan-design-review") == "plan"

    def test_refine_phase(self):
        assert _match_gstack_phase("gstack-refine") == "refine"

    def test_ship_phase(self):
        assert _match_gstack_phase("ship") == "ship"

    def test_document_phase(self):
        assert _match_gstack_phase("document-release") == "document"

    def test_spec_phase(self):
        assert _match_gstack_phase("spec-keeper") == "spec"

    def test_retro_phase(self):
        assert _match_gstack_phase("retro") == "retro"

    def test_unknown(self):
        assert _match_gstack_phase("evolve") is None


class TestGstackLifecycle:
    """ライフサイクル定数のテスト。"""

    def test_order(self):
        assert _GSTACK_LIFECYCLE == ["plan", "refine", "ship", "document", "spec", "retro"]


class TestBuildGstackAnalyticsSection:
    """build_gstack_analytics_section のテスト。"""

    def test_empty_records(self):
        assert build_gstack_analytics_section([]) == []

    def test_no_gstack_records(self):
        records = [
            {"skill_name": "evolve", "session_id": "s1"},
            {"skill_name": "discover", "session_id": "s1"},
        ]
        assert build_gstack_analytics_section(records) == []

    def test_funnel_output(self):
        records = [
            {"skill_name": "office-hours", "session_id": "s1"},
            {"skill_name": "ship", "session_id": "s1"},
            {"skill_name": "document-release", "session_id": "s1"},
            {"skill_name": "spec-keeper", "session_id": "s1"},
            {"skill_name": "retro", "session_id": "s1"},
        ]
        result = build_gstack_analytics_section(records)
        assert any("gstack Workflow Analytics" in line for line in result)
        assert any("Funnel:" in line for line in result)

    def test_completion_rate(self):
        records = [
            {"skill_name": "office-hours", "session_id": "s1"},
            {"skill_name": "ship", "session_id": "s1"},
            {"skill_name": "retro", "session_id": "s1"},
            {"skill_name": "plan-eng-review", "session_id": "s2"},
            # s2 has no retro → incomplete
        ]
        result = build_gstack_analytics_section(records)
        # plan=2, retro=1 → 50%
        text = "\n".join(result)
        assert "Completion rate:" in text or "Plan→Retro ratio:" in text

    def test_phase_efficiency(self):
        records = [
            {"skill_name": "ship", "session_id": "s1"},
            {"skill_name": "ship", "session_id": "s2"},
            {"skill_name": "ship", "session_id": "s3"},
        ]
        result = build_gstack_analytics_section(records)
        text = "\n".join(result)
        assert "ship:" in text

    def test_mixed_gstack_and_non_gstack(self):
        records = [
            {"skill_name": "ship", "session_id": "s1"},
            {"skill_name": "evolve", "session_id": "s1"},
            {"skill_name": "retro", "session_id": "s1"},
        ]
        result = build_gstack_analytics_section(records)
        text = "\n".join(result)
        assert "evolve" not in text
        assert "ship" in text
