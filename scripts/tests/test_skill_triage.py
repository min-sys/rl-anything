"""skill_triage.py のユニットテスト。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from skill_triage import (
    BASE_CONFIDENCE,
    CLUSTER_DISTANCE_THRESHOLD,
    MERGE_OVERLAP_THRESHOLD,
    MISSED_SKILL_THRESHOLD,
    SESSION_BONUS_RATE,
    MAX_SESSION_BONUS,
    EVIDENCE_BONUS_RATE,
    MAX_EVIDENCE_BONUS,
    compute_confidence,
    triage_skill,
    triage_all_skills,
    detect_split_candidates,
    detect_merge_candidates,
    generate_skill_creator_suggestion,
)


@pytest.fixture
def skill_triggers_list():
    return [
        {"skill": "aws-cdk-deploy", "triggers": ["CDK", "デプロイ", "deploy"]},
        {"skill": "channel-routing", "triggers": ["チャンネル", "channel"]},
        {"skill": "commit", "triggers": ["commit", "コミット"]},
    ]


@pytest.fixture
def sessions():
    return [
        {"session_id": "s1", "user_prompts": ["CDKでLambdaをデプロイしたい"]},
        {"session_id": "s2", "user_prompts": ["CDKのデプロイでエラーが出た"]},
        {"session_id": "s3", "user_prompts": ["デプロイの設定を確認したい"]},
        {"session_id": "s4", "user_prompts": ["チャンネルの動画をダウンロードしたい"]},
        {"session_id": "s5", "user_prompts": ["CDK synth を実行して"]},
        {"session_id": "s6", "user_prompts": ["デプロイ前のチェック"]},
        {"session_id": "s7", "user_prompts": ["コミットして"]},
    ]


@pytest.fixture
def usage():
    return [
        {"session_id": "s1", "skill_name": "aws-cdk-deploy"},
        {"session_id": "s2", "skill_name": "aws-cdk-deploy"},
        {"session_id": "s5", "skill_name": "aws-cdk-deploy"},
        {"session_id": "s7", "skill_name": "commit"},
    ]


class TestComputeConfidence:
    def test_create_base(self):
        c = compute_confidence("CREATE", session_count=MISSED_SKILL_THRESHOLD)
        assert c == BASE_CONFIDENCE["CREATE"]

    def test_create_with_session_bonus(self):
        c = compute_confidence("CREATE", session_count=5)
        expected = BASE_CONFIDENCE["CREATE"] + min(
            MAX_SESSION_BONUS,
            (5 - MISSED_SKILL_THRESHOLD) * SESSION_BONUS_RATE,
        )
        assert abs(c - expected) < 0.001

    def test_update_with_evidence_bonus(self):
        c = compute_confidence("UPDATE", session_count=3, near_miss_count=3)
        expected = (
            BASE_CONFIDENCE["UPDATE"]
            + min(MAX_SESSION_BONUS, (3 - MISSED_SKILL_THRESHOLD) * SESSION_BONUS_RATE)
            + min(MAX_EVIDENCE_BONUS, 3 * EVIDENCE_BONUS_RATE)
        )
        assert abs(c - expected) < 0.001

    def test_confidence_capped_at_1(self):
        c = compute_confidence("CREATE", session_count=100)
        assert c <= 1.0

    def test_no_negative_bonus(self):
        c = compute_confidence("CREATE", session_count=0)
        assert c == BASE_CONFIDENCE["CREATE"]


class TestTriageSkill:
    def test_create_judgment(self, sessions, usage, skill_triggers_list):
        missed = [{"skill": "deploy-check", "triggers_matched": ["deploy"], "session_count": 4}]
        result = triage_skill(
            "deploy-check",
            sessions=sessions,
            usage=usage,
            missed_skills=missed,
            existing_skills={"aws-cdk-deploy", "channel-routing", "commit"},
            skill_triggers_list=skill_triggers_list,
        )
        assert result["action"] == "CREATE"
        assert result["confidence"] >= BASE_CONFIDENCE["CREATE"]
        assert result["evidence"]["missed_sessions"] == 4

    def test_update_judgment(self, sessions, usage, skill_triggers_list):
        missed = [{"skill": "aws-cdk-deploy", "triggers_matched": ["CDK"], "session_count": 3}]
        result = triage_skill(
            "aws-cdk-deploy",
            sessions=sessions,
            usage=usage,
            missed_skills=missed,
            existing_skills={"aws-cdk-deploy"},
            skill_triggers_list=skill_triggers_list,
        )
        assert result["action"] == "UPDATE"
        assert "suggestion" in result

    def test_ok_judgment(self, sessions, usage, skill_triggers_list):
        result = triage_skill(
            "commit",
            sessions=sessions,
            usage=usage,
            missed_skills=[],
            existing_skills={"commit"},
            skill_triggers_list=skill_triggers_list,
        )
        assert result["action"] == "OK"

    def test_missed_below_threshold(self, sessions, usage, skill_triggers_list):
        missed = [{"skill": "rare-skill", "triggers_matched": ["rare"], "session_count": 1}]
        result = triage_skill(
            "rare-skill",
            sessions=sessions,
            usage=usage,
            missed_skills=missed,
            existing_skills=set(),
            skill_triggers_list=skill_triggers_list,
        )
        assert result["action"] == "OK"


class TestDetectSplitCandidates:
    def test_split_detected(self):
        eval_set = [
            {"query": "CDK deploy Lambda", "should_trigger": True},
            {"query": "Docker compose up", "should_trigger": True},
            {"query": "Terraform apply", "should_trigger": True},
            {"query": "設定を確認", "should_trigger": False},
        ]
        triggers_list = [
            {"skill": "infra-deploy", "triggers": ["CDK", "Docker", "Terraform", "deploy"]},
        ]
        result = detect_split_candidates("infra-deploy", eval_set, triggers_list)
        assert result is not None
        assert result["action"] == "SPLIT"
        assert len(result["evidence"]["categories"]) >= 3

    def test_no_split_too_few_queries(self):
        eval_set = [
            {"query": "CDK deploy", "should_trigger": True},
            {"query": "CDK synth", "should_trigger": True},
        ]
        triggers_list = [{"skill": "cdk", "triggers": ["CDK"]}]
        result = detect_split_candidates("cdk", eval_set, triggers_list)
        assert result is None


class TestDetectMergeCandidates:
    def test_merge_detected(self):
        eval_sets = {
            "cdk-deploy": {
                "skipped": False,
                "eval_set": [
                    {"query": "cdk deploy lambda", "should_trigger": True},
                    {"query": "cdk synth", "should_trigger": True},
                    {"query": "deploy cdk stack", "should_trigger": True},
                ],
            },
            "cdk-setup": {
                "skipped": False,
                "eval_set": [
                    {"query": "cdk deploy lambda", "should_trigger": True},
                    {"query": "cdk synth", "should_trigger": True},
                    {"query": "setup cdk project", "should_trigger": True},
                ],
            },
        }
        result = detect_merge_candidates(eval_sets)
        assert len(result) > 0
        assert result[0]["action"] == "MERGE"
        assert result[0]["evidence"]["source"] == "triage"

    def test_no_merge_low_overlap(self):
        eval_sets = {
            "skill-a": {
                "skipped": False,
                "eval_set": [
                    {"query": "aaa bbb ccc", "should_trigger": True},
                ],
            },
            "skill-b": {
                "skipped": False,
                "eval_set": [
                    {"query": "xxx yyy zzz", "should_trigger": True},
                ],
            },
        }
        result = detect_merge_candidates(eval_sets)
        assert len(result) == 0


class TestTriageAllSkills:
    def test_empty_skills(self, sessions, usage, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# No skills\n")
        result = triage_all_skills(
            sessions=sessions,
            usage=usage,
            missed_skills=[],
            project_root=tmp_path,
        )
        assert result["skipped"]
        assert result["reason"] == "no_skills_found"

    def test_mixed_results(self, sessions, usage, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "## Skills\n"
            "- /aws-cdk-deploy: CDK deploy. Trigger: CDK, デプロイ, deploy\n"
            "- /commit: コミット. Trigger: commit, コミット\n"
        )
        result = triage_all_skills(
            sessions=sessions,
            usage=usage,
            missed_skills=[],
            project_root=tmp_path,
        )
        assert not result["skipped"]
        all_actions = result["CREATE"] + result["UPDATE"] + result["SPLIT"] + result["MERGE"] + result["OK"]
        assert len(all_actions) > 0


class TestSkillCreatorSuggestion:
    def test_suggestion_content(self):
        triage_result = {
            "action": "UPDATE",
            "skill": "aws-cdk-deploy",
            "confidence": 0.80,
            "eval_set_path": "/path/to/eval.json",
            "evidence": {"missed_sessions": 3, "near_miss_count": 2},
        }
        suggestion = generate_skill_creator_suggestion(triage_result)
        assert suggestion["skill"] == "aws-cdk-deploy"
        assert suggestion["eval_set_path"] == "/path/to/eval.json"
        assert "skill-creator" in suggestion["command_example"]
