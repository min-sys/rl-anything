"""issue_schema.py の skill_triage 関連テスト。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from issue_schema import (
    SKILL_TRIAGE_CREATE,
    SKILL_TRIAGE_UPDATE,
    SKILL_TRIAGE_SPLIT,
    SKILL_TRIAGE_MERGE,
    ST_ACTION,
    ST_SKILL,
    ST_CONFIDENCE,
    ST_EVIDENCE,
    make_skill_triage_issue,
)


class TestMakeSkillTriageIssue:
    def test_create_issue(self):
        result = make_skill_triage_issue({
            "action": "CREATE",
            "skill": "deploy-check",
            "confidence": 0.85,
            "evidence": {"missed_sessions": 4},
        })
        assert result["type"] == SKILL_TRIAGE_CREATE
        assert result["file"] == ".claude/skills/deploy-check/SKILL.md"
        assert result["detail"][ST_ACTION] == "CREATE"
        assert result["detail"][ST_CONFIDENCE] == 0.85
        assert result["source"] == "skill_triage"

    def test_update_issue(self):
        result = make_skill_triage_issue({
            "action": "UPDATE",
            "skill": "aws-cdk-deploy",
            "confidence": 0.80,
            "evidence": {"missed_sessions": 3, "near_miss_count": 2},
            "suggestion": "description の trigger 精度を改善",
        })
        assert result["type"] == SKILL_TRIAGE_UPDATE
        assert result["detail"][ST_SKILL] == "aws-cdk-deploy"

    def test_split_issue(self):
        result = make_skill_triage_issue({
            "action": "SPLIT",
            "skill": "infra-deploy",
            "confidence": 0.75,
            "evidence": {"categories": ["cdk", "docker", "terraform"]},
        })
        assert result["type"] == SKILL_TRIAGE_SPLIT

    def test_merge_issue(self):
        result = make_skill_triage_issue({
            "action": "MERGE",
            "skills": ["cdk-deploy", "cdk-setup"],
            "confidence": 0.70,
            "evidence": {"overlap_ratio": 0.55},
        })
        assert result["type"] == SKILL_TRIAGE_MERGE
        assert result["detail"]["skills"] == ["cdk-deploy", "cdk-setup"]

    def test_ok_returns_empty(self):
        result = make_skill_triage_issue({"action": "OK", "skill": "commit"})
        assert result == {}

    def test_unknown_action_returns_empty(self):
        result = make_skill_triage_issue({"action": "UNKNOWN"})
        assert result == {}
