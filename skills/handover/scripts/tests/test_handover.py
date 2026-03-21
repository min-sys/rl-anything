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
    def test_happy_path(self, project_dir, data_dir):
        """git 情報 + テレメトリが正しく収集される。"""
        # usage.jsonl にダミーデータ
        usage_file = data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"skill_name": "ship", "session_id": "s1", "timestamp": "2026-03-22T00:00:00Z"}) + "\n"
            + json.dumps({"skill_name": "review", "session_id": "s1", "timestamp": "2026-03-22T00:01:00Z"}) + "\n",
            encoding="utf-8",
        )

        with mock.patch("handover._run_git") as mock_git:
            mock_git.side_effect = [
                "M  src/app.py\n M hooks/save_state.py\n",  # status --short
                "abc1234 feat: add handover\ndef5678 fix: typo\n",  # log --oneline
                " 2 files changed, 10 insertions(+)\n",  # diff --stat
            ]
            result = handover.collect_handover_data(str(project_dir))

        assert "uncommitted_files" in result
        assert len(result["uncommitted_files"]) == 2
        assert "recent_commits" in result
        assert len(result["recent_commits"]) == 2
        assert "diff_stat" in result
        assert "skills_used" in result
        assert len(result["skills_used"]) == 2
        assert result["project_dir"] == str(project_dir)

    def test_no_git(self, project_dir, data_dir):
        """git リポジトリ外でも graceful degradation。"""
        with mock.patch("handover._run_git", return_value=""):
            result = handover.collect_handover_data(str(project_dir))

        assert result["uncommitted_files"] == []
        assert result["recent_commits"] == []
        assert result["diff_stat"] == ""

    def test_corrections_included(self, project_dir, data_dir):
        """corrections.jsonl のデータが含まれる。"""
        corrections_file = data_dir / "corrections.jsonl"
        corrections_file.write_text(
            json.dumps({"pattern": "test fix", "session_id": "s1", "timestamp": "2026-03-22T00:00:00Z"}) + "\n",
            encoding="utf-8",
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
