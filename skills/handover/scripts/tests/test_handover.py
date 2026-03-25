"""handover.py tests."""
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

# Setup paths
_skill_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_skill_dir))
_plugin_root = _skill_dir.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "hooks"))

import handover


@pytest.fixture
def project_dir(tmp_path):
    """プロジェクトディレクトリを模擬する。"""
    handover_dir = tmp_path / ".claude" / "handovers"
    handover_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def data_dir(tmp_path):
    """DATA_DIR をパッチする。"""
    d = tmp_path / "data"
    d.mkdir()
    with mock.patch("handover.DATA_DIR", d):
        yield d


class TestCollectHandoverData:
    def test_happy_path_uses_checkpoint(self, project_dir, data_dir):
        """checkpoint.json からコンテキストを取得し、git を再呼び出ししない。"""
        # checkpoint.json にデータを用意
        checkpoint = {
            "session_id": "s1",
            "timestamp": "2026-03-22T00:00:00Z",
            "work_context": {
                "git_branch": "feat/handover",
                "recent_commits": ["abc1234 feat: add handover", "def5678 fix: typo"],
                "uncommitted_files": ["M  src/app.py", "M hooks/save_state.py"],
            },
            "corrections_snapshot": [
                {"pattern": "test fix", "session_id": "s1"}
            ],
        }
        (data_dir / "checkpoint.json").write_text(
            json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8"
        )

        # usage.jsonl にダミーデータ
        usage_file = data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"skill_name": "ship", "session_id": "s1", "timestamp": "2026-03-22T00:00:00Z"}) + "\n"
            + json.dumps({"skill_name": "review", "session_id": "s1", "timestamp": "2026-03-22T00:01:00Z"}) + "\n",
            encoding="utf-8",
        )

        with mock.patch("handover._run_git") as mock_git:
            result = handover.collect_handover_data(str(project_dir))

        # git は呼ばれない（checkpoint から取得するため）
        mock_git.assert_not_called()

        # checkpoint の work_context がそのまま使われる
        assert result["work_context"]["git_branch"] == "feat/handover"
        assert len(result["work_context"]["recent_commits"]) == 2
        assert len(result["work_context"]["uncommitted_files"]) == 2
        assert result["skills_used"] == [
            {"skill": "ship", "timestamp": "2026-03-22T00:00:00Z"},
            {"skill": "review", "timestamp": "2026-03-22T00:01:00Z"},
        ]
        assert result["project_dir"] == str(project_dir)

    def test_fallback_to_git_when_no_checkpoint(self, project_dir, data_dir):
        """checkpoint.json がない場合は git にフォールバックする。"""
        with mock.patch("handover._run_git") as mock_git:
            mock_git.side_effect = [
                "feat/handover\n",  # rev-parse --abbrev-ref HEAD
                "abc1234 feat: add handover\n",  # log --oneline
                "M  src/app.py\n",  # status --short
            ]
            result = handover.collect_handover_data(str(project_dir))

        assert mock_git.call_count == 3
        assert result["work_context"]["git_branch"] == "feat/handover"
        assert len(result["work_context"]["recent_commits"]) == 1
        assert len(result["work_context"]["uncommitted_files"]) == 1

    def test_no_git(self, project_dir, data_dir):
        """git リポジトリ外でも graceful degradation。"""
        with mock.patch("handover._run_git", return_value=""):
            result = handover.collect_handover_data(str(project_dir))

        assert result["work_context"]["uncommitted_files"] == []
        assert result["work_context"]["recent_commits"] == []
        assert result["work_context"]["git_branch"] == ""

    def test_corrections_from_checkpoint(self, project_dir, data_dir):
        """checkpoint の corrections_snapshot が使われる。"""
        checkpoint = {
            "corrections_snapshot": [
                {"pattern": "test fix", "session_id": "s1", "timestamp": "2026-03-22T00:00:00Z"}
            ],
            "work_context": {},
        }
        (data_dir / "checkpoint.json").write_text(
            json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8"
        )

        with mock.patch("handover._run_git", return_value=""):
            result = handover.collect_handover_data(str(project_dir))

        assert len(result["corrections"]) == 1


class TestListHandovers:
    def test_list_sorted_descending(self, project_dir):
        """ファイル一覧が日付降順。"""
        hdir = project_dir / ".claude" / "handovers"
        (hdir / "2026-03-20_1400.md").write_text("# Older", encoding="utf-8")
        time.sleep(0.01)
        (hdir / "2026-03-22_0900.md").write_text("# Newer", encoding="utf-8")

        result = handover.list_handovers(str(project_dir))
        assert len(result) == 2
        assert result[0]["name"] == "2026-03-22_0900.md"
        assert result[1]["name"] == "2026-03-20_1400.md"

    def test_empty_dir(self, project_dir):
        """空ディレクトリで空リスト。"""
        result = handover.list_handovers(str(project_dir))
        assert result == []

    def test_no_handover_dir(self, tmp_path):
        """handovers/ が存在しない場合は空リスト。"""
        result = handover.list_handovers(str(tmp_path))
        assert result == []


class TestLatestHandover:
    def test_returns_content(self, project_dir):
        """最新 handover の内容を返す。"""
        hdir = project_dir / ".claude" / "handovers"
        (hdir / "2026-03-22_0900.md").write_text("# Session notes\nDid stuff", encoding="utf-8")

        result = handover.latest_handover(str(project_dir))
        assert result is not None
        assert "Session notes" in result

    def test_empty_dir_returns_none(self, project_dir):
        """空ディレクトリで None。"""
        result = handover.latest_handover(str(project_dir))
        assert result is None

    def test_stale_returns_none(self, project_dir):
        """STALE_HOURS 超のファイルは None。"""
        hdir = project_dir / ".claude" / "handovers"
        f = hdir / "2026-03-18_0900.md"
        f.write_text("# Old notes", encoding="utf-8")

        result = handover.latest_handover(str(project_dir), stale_hours=0.0001)
        # stale_hours を極小にすれば即 stale
        time.sleep(0.001)
        result = handover.latest_handover(str(project_dir), stale_hours=0.0000001)
        assert result is None


class TestExtractSection:
    """extract_section() のテスト。"""

    def test_extracts_deploy_state(self):
        """## Deploy State セクションを正しく抽出する。"""
        content = (
            "# Handover: 2026-03-25 10:00\n\n"
            "## Decisions\n- Used new API\n\n"
            "## Deploy State\n- dev: deployed (commit abc1234)\n- prod: deployed (commit abc1234)\n\n"
            "## Next Actions\n- Merge PR\n"
        )
        result = handover.extract_section(content, "Deploy State")
        assert "dev: deployed" in result
        assert "prod: deployed" in result
        # 他のセクションは含まない
        assert "Decisions" not in result
        assert "Next Actions" not in result

    def test_returns_empty_for_missing_section(self):
        """存在しないセクションは空文字列。"""
        content = "# Handover\n\n## Decisions\n- Something\n"
        result = handover.extract_section(content, "Deploy State")
        assert result == ""

    def test_extracts_next_actions(self):
        """## Next Actions セクションも抽出可能。"""
        content = (
            "# Handover\n\n"
            "## Decisions\n- A\n\n"
            "## Next Actions\n1. Fix bug\n2. Deploy\n"
        )
        result = handover.extract_section(content, "Next Actions")
        assert "Fix bug" in result
        assert "Deploy" in result

    def test_last_section_no_trailing_header(self):
        """最後のセクション（後続 ## なし）を正しく抽出する。"""
        content = (
            "# Handover\n\n"
            "## Deploy State\nAll deployed\n"
        )
        result = handover.extract_section(content, "Deploy State")
        assert "All deployed" in result


class TestExtractDeployState:
    """extract_deploy_state() のテスト。"""

    def test_extracts_from_handover(self, project_dir):
        """最新 handover から Deploy State を抽出する。"""
        hdir = project_dir / ".claude" / "handovers"
        content = (
            "# Handover: 2026-03-25\n\n"
            "## Deploy State\n- dev: deployed\n- prod: not deployed\n\n"
            "## Next Actions\n- Deploy to prod\n"
        )
        (hdir / "2026-03-25_1000.md").write_text(content, encoding="utf-8")

        result = handover.extract_deploy_state(str(project_dir))
        assert result is not None
        assert "dev: deployed" in result
        assert "prod: not deployed" in result

    def test_returns_none_when_no_handover(self, project_dir):
        """handover がない場合は None。"""
        result = handover.extract_deploy_state(str(project_dir))
        assert result is None

    def test_returns_none_when_no_deploy_section(self, project_dir):
        """Deploy State セクションがない handover の場合は None。"""
        hdir = project_dir / ".claude" / "handovers"
        content = "# Handover\n\n## Decisions\n- Something\n"
        (hdir / "2026-03-25_1000.md").write_text(content, encoding="utf-8")

        result = handover.extract_deploy_state(str(project_dir))
        assert result is None
