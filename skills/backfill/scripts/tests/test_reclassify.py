"""reclassify スクリプトのテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# reclassify.py をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "hooks"))

import common
import reclassify


@pytest.fixture
def tmp_data_dir(tmp_path):
    """テスト用の一時データディレクトリ。"""
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def patch_data_dir(tmp_data_dir):
    """common.DATA_DIR を一時ディレクトリに差し替える。"""
    with mock.patch.object(common, "DATA_DIR", tmp_data_dir):
        yield tmp_data_dir


class TestExtractOtherIntents:
    """extract_other_intents() のテスト。"""

    def test_extracts_other_prompts(self, patch_data_dir):
        """'other' intent のプロンプトが抽出される。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        record = {
            "session_id": "sess-001",
            "project_name": "my-project",
            "user_intents": ["implementation", "other", "debug"],
            "user_prompts": ["implement X", "何かやって", "fix the bug"],
        }
        sessions_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        results = reclassify.extract_other_intents()
        assert len(results) == 1
        assert results[0]["session_id"] == "sess-001"
        assert results[0]["intent_index"] == 1
        assert results[0]["prompt"] == "何かやって"

    def test_skips_reclassified_sessions(self, patch_data_dir):
        """reclassified_intents がある場合はスキップ。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        record = {
            "session_id": "sess-002",
            "user_intents": ["other"],
            "user_prompts": ["test prompt"],
            "reclassified_intents": ["conversation"],
        }
        sessions_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        results = reclassify.extract_other_intents()
        assert len(results) == 0

    def test_filters_by_project(self, patch_data_dir):
        """project_name でフィルタされる。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        records = [
            {"session_id": "s1", "project_name": "proj-a", "user_intents": ["other"], "user_prompts": ["p1"]},
            {"session_id": "s2", "project_name": "proj-b", "user_intents": ["other"], "user_prompts": ["p2"]},
        ]
        sessions_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n",
            encoding="utf-8",
        )

        results = reclassify.extract_other_intents(project_name="proj-a")
        assert len(results) == 1
        assert results[0]["session_id"] == "s1"

    def test_empty_when_no_sessions_file(self, patch_data_dir):
        """sessions.jsonl がない場合は空リスト。"""
        results = reclassify.extract_other_intents()
        assert results == []

    def test_include_reclassified_extracts_remaining_other(self, patch_data_dir):
        """--include-reclassified で reclassified_intents の残 other が抽出される。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        record = {
            "session_id": "sess-reclass",
            "user_intents": ["other", "other", "other"],
            "user_prompts": ["p1", "p2", "p3"],
            "reclassified_intents": ["debug", "other", "implementation"],
        }
        sessions_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        results = reclassify.extract_other_intents(include_reclassified=True)
        assert len(results) == 1
        assert results[0]["session_id"] == "sess-reclass"
        assert results[0]["intent_index"] == 1
        assert results[0]["prompt"] == "p2"

    def test_include_reclassified_falls_back_to_user_intents(self, patch_data_dir):
        """--include-reclassified で reclassified_intents がない場合は user_intents を参照。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        record = {
            "session_id": "sess-no-reclass",
            "user_intents": ["implementation", "other"],
            "user_prompts": ["impl X", "何か"],
        }
        sessions_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        results = reclassify.extract_other_intents(include_reclassified=True)
        assert len(results) == 1
        assert results[0]["intent_index"] == 1

    def test_without_flag_skips_reclassified(self, patch_data_dir):
        """フラグなしでは reclassified_intents があるセッションをスキップ。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        record = {
            "session_id": "sess-skip",
            "user_intents": ["other"],
            "user_prompts": ["test"],
            "reclassified_intents": ["other"],
        }
        sessions_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        results = reclassify.extract_other_intents(include_reclassified=False)
        assert len(results) == 0


class TestCorrectionPriority:
    """corrections.jsonl を使った優先抽出のテスト。"""

    def test_correction_sessions_first(self, patch_data_dir):
        """correction 紐付きセッションが結果の先頭に含まれる。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        records = [
            {"session_id": "s1", "user_intents": ["other"], "user_prompts": ["p1"]},
            {"session_id": "s2", "user_intents": ["other"], "user_prompts": ["p2"]},
        ]
        sessions_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n",
            encoding="utf-8",
        )

        # s2 のみ corrections がある
        corrections_file = patch_data_dir / "corrections.jsonl"
        corrections_file.write_text(
            json.dumps({"session_id": "s2", "correction_type": "iya", "last_skill": "evolve"}) + "\n",
            encoding="utf-8",
        )

        results = reclassify.extract_other_intents()
        assert len(results) == 2
        assert results[0]["session_id"] == "s2"  # correction 紐付きが先頭
        assert results[1]["session_id"] == "s1"

    def test_no_corrections_file(self, patch_data_dir):
        """corrections.jsonl がない場合は通常の順序。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        records = [
            {"session_id": "s1", "user_intents": ["other"], "user_prompts": ["p1"]},
            {"session_id": "s2", "user_intents": ["other"], "user_prompts": ["p2"]},
        ]
        sessions_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n",
            encoding="utf-8",
        )

        results = reclassify.extract_other_intents()
        assert len(results) == 2


class TestBuildCorrectionContext:
    """build_correction_context() のテスト。"""

    def test_builds_context(self, patch_data_dir):
        corrections_file = patch_data_dir / "corrections.jsonl"
        corrections_file.write_text(
            json.dumps({"session_id": "s1", "correction_type": "iya", "last_skill": "evolve"}) + "\n",
            encoding="utf-8",
        )

        ctx = reclassify.build_correction_context("s1")
        assert ctx is not None
        assert "evolve" in ctx

    def test_no_corrections(self, patch_data_dir):
        ctx = reclassify.build_correction_context("nonexistent")
        assert ctx is None


class TestApplyReclassification:
    """apply_reclassification() のテスト。"""

    def test_applies_reclassification(self, patch_data_dir):
        """再分類結果が sessions.jsonl に書き戻される。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        record = {
            "session_id": "sess-001",
            "user_intents": ["implementation", "other", "debug"],
        }
        sessions_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        reclassified = [
            {"session_id": "sess-001", "intent_index": 1, "category": "conversation"},
        ]
        result = reclassify.apply_reclassification(reclassified)
        assert result["updated_sessions"] == 1
        assert result["updated_intents"] == 1

        updated = json.loads(sessions_file.read_text(encoding="utf-8").strip())
        assert updated["reclassified_intents"] == ["implementation", "conversation", "debug"]

    def test_invalid_category_counted(self, patch_data_dir):
        """無効なカテゴリが invalid_categories としてカウントされる。"""
        sessions_file = patch_data_dir / "sessions.jsonl"
        record = {"session_id": "s1", "user_intents": ["other"]}
        sessions_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        reclassified = [
            {"session_id": "s1", "intent_index": 0, "category": "invalid-cat"},
        ]
        result = reclassify.apply_reclassification(reclassified)
        assert result["invalid_categories"] == 1
        assert result["updated_intents"] == 0


class TestValidCategories:
    """VALID_CATEGORIES のテスト。"""

    def test_includes_skill_invocation(self):
        """skill-invocation が VALID_CATEGORIES に含まれる。"""
        assert "skill-invocation" in reclassify.VALID_CATEGORIES

    def test_includes_other(self):
        """other が VALID_CATEGORIES に含まれる。"""
        assert "other" in reclassify.VALID_CATEGORIES

    def test_includes_all_prompt_categories(self):
        """PROMPT_CATEGORIES の全キーが含まれる。"""
        for cat in common.PROMPT_CATEGORIES:
            assert cat in reclassify.VALID_CATEGORIES

    def test_includes_conversation_subcategories(self):
        """conversation サブカテゴリが VALID_CATEGORIES に含まれる。"""
        for sub in [
            "conversation:approval",
            "conversation:confirmation",
            "conversation:question",
            "conversation:direction",
            "conversation:thanks",
        ]:
            assert sub in reclassify.VALID_CATEGORIES

    def test_includes_bare_conversation(self):
        """後方互換のため bare conversation が VALID_CATEGORIES に含まれる。"""
        assert "conversation" in reclassify.VALID_CATEGORIES
