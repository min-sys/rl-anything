"""trigger_eval_generator.py のユニットテスト。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from trigger_eval_generator import (
    MIN_EVAL_QUERIES,
    TARGET_EVAL_QUERIES,
    generate_eval_set,
    _select_best_prompt,
    _extract_should_trigger,
    _extract_should_not_trigger,
    _build_used_skills_map,
)


@pytest.fixture
def skill_triggers_list():
    return [
        {"skill": "aws-cdk-deploy", "triggers": ["CDK", "デプロイ", "deploy"]},
        {"skill": "channel-routing", "triggers": ["チャンネル", "channel"]},
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
        {"session_id": "s7", "user_prompts": ["全く関係ない質問"]},
        {"session_id": "s8", "user_prompts": ["deployの状態を見たい"]},
        {"session_id": "s9", "user_prompts": ["CDKのスタックを削除して"]},
    ]


@pytest.fixture
def usage():
    return [
        {"session_id": "s1", "skill_name": "aws-cdk-deploy"},
        {"session_id": "s2", "skill_name": "aws-cdk-deploy"},
        {"session_id": "s3", "skill_name": "config-review"},
        {"session_id": "s5", "skill_name": "aws-cdk-deploy"},
        {"session_id": "s6", "skill_name": "config-review"},
        {"session_id": "s8", "skill_name": "monitoring"},
        {"session_id": "s9", "skill_name": "aws-cdk-deploy"},
    ]


class TestSelectBestPrompt:
    def test_single_prompt(self):
        result = _select_best_prompt(["hello"], ["hello"])
        assert result == "hello"

    def test_multi_prompt_trigger_match(self):
        prompts = ["こんにちは", "CDKのデプロイでエラーが出た", "ログを見せて"]
        result = _select_best_prompt(prompts, ["CDK", "デプロイ"])
        assert result == "CDKのデプロイでエラーが出た"

    def test_fallback_to_first(self):
        prompts = ["インフラの問題を調べて", "詳細を教えて"]
        result = _select_best_prompt(prompts, ["CDK", "deploy"])
        assert result == "インフラの問題を調べて"

    def test_empty_prompts(self):
        assert _select_best_prompt([], ["CDK"]) == ""


class TestGenerateEvalSet:
    def test_normal_generation(self, sessions, usage, skill_triggers_list):
        result = generate_eval_set(
            "aws-cdk-deploy",
            sessions=sessions,
            usage=usage,
            skill_triggers_list=skill_triggers_list,
            save=False,
        )
        assert not result["skipped"]
        assert result["skill"] == "aws-cdk-deploy"
        assert result["stats"]["should_trigger"] > 0
        assert result["stats"]["should_not_trigger"] > 0

        # skill-creator 互換フォーマット
        for entry in result["eval_set"]:
            assert "query" in entry
            assert "should_trigger" in entry

    def test_insufficient_data(self, skill_triggers_list):
        result = generate_eval_set(
            "aws-cdk-deploy",
            sessions=[{"session_id": "s1", "user_prompts": ["CDK deploy"]}],
            usage=[{"session_id": "s1", "skill_name": "aws-cdk-deploy"}],
            skill_triggers_list=skill_triggers_list,
            save=False,
        )
        assert result["skipped"]
        assert result["reason"] == "insufficient_data"

    def test_no_triggers(self, sessions, usage):
        result = generate_eval_set(
            "unknown-skill",
            sessions=sessions,
            usage=usage,
            skill_triggers_list=[],
            save=False,
        )
        assert result["skipped"]
        assert result["reason"] == "no_triggers"

    def test_file_output(self, tmp_path, sessions, usage, skill_triggers_list, monkeypatch):
        monkeypatch.setattr(
            "trigger_eval_generator.EVAL_SETS_DIR",
            tmp_path / "eval-sets",
        )
        result = generate_eval_set(
            "aws-cdk-deploy",
            sessions=sessions,
            usage=usage,
            skill_triggers_list=skill_triggers_list,
            save=True,
        )
        assert result["eval_set_path"] is not None
        path = Path(result["eval_set_path"])
        assert path.exists()
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        for entry in data:
            assert set(entry.keys()) == {"query", "should_trigger"}


class TestShouldNotTrigger:
    def test_near_miss_prioritized(self, sessions, usage, skill_triggers_list):
        used_map = _build_used_skills_map(usage)
        result = _extract_should_not_trigger(
            "aws-cdk-deploy",
            ["CDK", "デプロイ", "deploy"],
            sessions,
            used_map,
        )
        near_miss = [e for e in result if e["source"] == "near_miss"]
        unrelated = [e for e in result if e["source"] == "unrelated"]
        assert len(near_miss) > 0
        assert all(e["confidence_weight"] == 1.0 for e in near_miss)
        assert all(e["confidence_weight"] == 0.6 for e in unrelated)
