"""discover.py の project フィルタリングテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# discover.py のインポートパス
_scripts_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_scripts_dir))

_plugin_root = _scripts_dir.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

import discover


@pytest.fixture
def usage_with_projects(tmp_path):
    """プロジェクトフィールド付き usage.jsonl。"""
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    usage_file = data_dir / "usage.jsonl"
    records = []
    # atlas プロジェクト: 6回 (閾値以上)
    for i in range(6):
        records.append({"skill_name": "atlas-skill", "project": "atlas"})
    # beta プロジェクト: 3回 (閾値未満)
    for i in range(3):
        records.append({"skill_name": "atlas-skill", "project": "beta"})
    # project null: 2回
    for i in range(2):
        records.append({"skill_name": "atlas-skill", "project": None})
    # エラーレコード
    errors_file = data_dir / "errors.jsonl"
    error_records = []
    for i in range(4):
        error_records.append({"error": "atlas error", "project": "atlas"})
    for i in range(2):
        error_records.append({"error": "atlas error", "project": "beta"})
    for i in range(1):
        error_records.append({"error": "atlas error", "project": None})
    errors_file.write_text("\n".join(json.dumps(r) for r in error_records) + "\n")
    usage_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return data_dir


class TestBehaviorProjectFilter:
    """detect_behavior_patterns の project フィルタテスト。"""

    def test_filter_by_project(self, usage_with_projects):
        with mock.patch.object(discover, "DATA_DIR", usage_with_projects):
            with mock.patch.object(discover, "SUPPRESSION_FILE", usage_with_projects / "suppress.jsonl"):
                patterns = discover.detect_behavior_patterns(
                    threshold=5,
                    project_root=Path("/Users/foo/atlas"),
                )
        # atlas-skill: atlas で6回 → 閾値以上
        skill_patterns = [p for p in patterns if p["type"] == "behavior"]
        assert len(skill_patterns) == 1
        assert skill_patterns[0]["count"] == 6

    def test_filter_excludes_other_project(self, usage_with_projects):
        with mock.patch.object(discover, "DATA_DIR", usage_with_projects):
            with mock.patch.object(discover, "SUPPRESSION_FILE", usage_with_projects / "suppress.jsonl"):
                patterns = discover.detect_behavior_patterns(
                    threshold=5,
                    project_root=Path("/Users/foo/beta"),
                )
        # beta: 3回 → 閾値未満
        skill_patterns = [p for p in patterns if p["type"] == "behavior"]
        assert len(skill_patterns) == 0

    def test_include_unknown(self, usage_with_projects):
        with mock.patch.object(discover, "DATA_DIR", usage_with_projects):
            with mock.patch.object(discover, "SUPPRESSION_FILE", usage_with_projects / "suppress.jsonl"):
                patterns = discover.detect_behavior_patterns(
                    threshold=5,
                    project_root=Path("/Users/foo/atlas"),
                    include_unknown=True,
                )
        # atlas: 6 + null: 2 = 8
        skill_patterns = [p for p in patterns if p["type"] == "behavior"]
        assert len(skill_patterns) == 1
        assert skill_patterns[0]["count"] == 8


class TestErrorProjectFilter:
    """detect_error_patterns の project フィルタテスト。"""

    def test_filter_by_project(self, usage_with_projects):
        with mock.patch.object(discover, "DATA_DIR", usage_with_projects):
            with mock.patch.object(discover, "SUPPRESSION_FILE", usage_with_projects / "suppress.jsonl"):
                patterns = discover.detect_error_patterns(
                    threshold=3,
                    project_root=Path("/Users/foo/atlas"),
                )
        assert len(patterns) == 1
        assert patterns[0]["count"] == 4

    def test_filter_excludes_other_project(self, usage_with_projects):
        with mock.patch.object(discover, "DATA_DIR", usage_with_projects):
            with mock.patch.object(discover, "SUPPRESSION_FILE", usage_with_projects / "suppress.jsonl"):
                patterns = discover.detect_error_patterns(
                    threshold=3,
                    project_root=Path("/Users/foo/beta"),
                )
        # beta: 2回 → 閾値未満
        assert len(patterns) == 0


class TestLoadClaudeReflectData:
    """load_claude_reflect_data の pending フィルタテスト。"""

    def test_pending_only(self, tmp_path):
        """pending のみ返す。applied/skipped は除外。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()
        corrections_file = data_dir / "corrections.jsonl"
        records = [
            {"message": "msg1", "reflect_status": "pending"},
            {"message": "msg2", "reflect_status": "applied"},
            {"message": "msg3", "reflect_status": "skipped"},
            {"message": "msg4", "reflect_status": "pending"},
            {"message": "msg5"},  # reflect_status なし → pending 扱い
        ]
        corrections_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )
        with mock.patch.object(discover, "DATA_DIR", data_dir):
            result = discover.load_claude_reflect_data()
        assert len(result) == 3  # pending x2 + status なし x1

    def test_all_applied(self, tmp_path):
        """全件 applied なら空リスト。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()
        corrections_file = data_dir / "corrections.jsonl"
        records = [
            {"message": "msg1", "reflect_status": "applied"},
            {"message": "msg2", "reflect_status": "applied"},
        ]
        corrections_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )
        with mock.patch.object(discover, "DATA_DIR", data_dir):
            result = discover.load_claude_reflect_data()
        assert len(result) == 0

    def test_empty_file(self, tmp_path):
        """ファイルが空なら空リスト。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()
        (data_dir / "corrections.jsonl").write_text("")
        with mock.patch.object(discover, "DATA_DIR", data_dir):
            result = discover.load_claude_reflect_data()
        assert len(result) == 0

    def test_nonexistent_file(self, tmp_path):
        """ファイルが存在しない場合は空リスト。"""
        data_dir = tmp_path / "rl-anything"
        data_dir.mkdir()
        with mock.patch.object(discover, "DATA_DIR", data_dir):
            result = discover.load_claude_reflect_data()
        assert len(result) == 0


class TestRunDiscoverProjectFilter:
    """run_discover の project_root / include_unknown テスト。"""

    def test_run_discover_with_project(self, usage_with_projects):
        with mock.patch.object(discover, "DATA_DIR", usage_with_projects):
            with mock.patch.object(discover, "SUPPRESSION_FILE", usage_with_projects / "suppress.jsonl"):
                result = discover.run_discover(
                    project_root=Path("/Users/foo/atlas"),
                )
        assert len(result["behavior_patterns"]) >= 1

    def test_run_discover_include_unknown(self, usage_with_projects):
        with mock.patch.object(discover, "DATA_DIR", usage_with_projects):
            with mock.patch.object(discover, "SUPPRESSION_FILE", usage_with_projects / "suppress.jsonl"):
                result = discover.run_discover(
                    project_root=Path("/Users/foo/atlas"),
                    include_unknown=True,
                )
        behavior = [p for p in result["behavior_patterns"] if p["type"] == "behavior"]
        assert behavior[0]["count"] == 8  # atlas(6) + null(2)
