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
        """checkpoint.json からコンテキストを取得し、work_context 用の git を再呼び出ししない。"""
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

        # usage.jsonl にダミーデータ（project フィールド付き）
        usage_file = data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"skill_name": "ship", "session_id": "s1", "timestamp": "2026-03-22T00:00:00Z", "project": str(project_dir)}) + "\n"
            + json.dumps({"skill_name": "review", "session_id": "s1", "timestamp": "2026-03-22T00:01:00Z", "project": str(project_dir)}) + "\n",
            encoding="utf-8",
        )

        with mock.patch("handover.is_github_repo", return_value=False):
            with mock.patch("handover._run_git") as mock_git:
                result = handover.collect_handover_data(str(project_dir))

        # work_context 用の git は呼ばれない（checkpoint から取得するため）
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
        with mock.patch("handover.is_github_repo", return_value=False):
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

    def test_corrections_filtered_by_project_path(self, project_dir, data_dir):
        """corrections.jsonl からの読み込み時、project_path でフィルタされる。"""
        corrections_file = data_dir / "corrections.jsonl"
        corrections_file.write_text(
            json.dumps({"pattern": "fix A", "project_path": str(project_dir)}) + "\n"
            + json.dumps({"pattern": "fix B", "project_path": "/other/project"}) + "\n"
            + json.dumps({"pattern": "fix C", "project_path": str(project_dir)}) + "\n"
            + json.dumps({"pattern": "fix D"}) + "\n",  # project_path なし
            encoding="utf-8",
        )

        with mock.patch("handover._run_git", return_value=""):
            result = handover.collect_handover_data(str(project_dir))

        # project_dir 一致のみ（project_path なしは除外）
        assert len(result["corrections"]) == 2
        patterns = [c["pattern"] for c in result["corrections"]]
        assert "fix A" in patterns
        assert "fix C" in patterns
        assert "fix B" not in patterns

    def test_corrections_checkpoint_not_filtered(self, project_dir, data_dir):
        """checkpoint の corrections_snapshot はフィルタ不要（同セッションのため）。"""
        checkpoint = {
            "corrections_snapshot": [
                {"pattern": "fix A", "project_path": str(project_dir)},
                {"pattern": "fix B", "project_path": "/other/project"},
            ],
            "work_context": {},
        }
        (data_dir / "checkpoint.json").write_text(
            json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8"
        )

        with mock.patch("handover._run_git", return_value=""):
            result = handover.collect_handover_data(str(project_dir))

        # checkpoint はセッション内データなのでフィルタしない
        assert len(result["corrections"]) == 2


    def test_usage_filtered_by_project(self, project_dir, data_dir):
        """usage.jsonl のスキル使用も project でフィルタされる。"""
        usage_file = data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"skill_name": "ship", "project": str(project_dir), "timestamp": "T1"}) + "\n"
            + json.dumps({"skill_name": "review", "project": "/other/project", "timestamp": "T2"}) + "\n"
            + json.dumps({"skill_name": "commit", "project": str(project_dir), "timestamp": "T3"}) + "\n"
            + json.dumps({"skill_name": "qa", "timestamp": "T4"}) + "\n",  # project なし
            encoding="utf-8",
        )

        with mock.patch("handover._run_git", return_value=""):
            result = handover.collect_handover_data(str(project_dir))

        skills = [s["skill"] for s in result["skills_used"]]
        assert "ship" in skills
        assert "commit" in skills
        assert "review" not in skills
        assert "qa" not in skills


class TestDefaultOutputIsGithub:
    """Bug 2: デフォルト出力に is_github を含む。"""

    def test_default_output_includes_is_github(self, data_dir):
        """--issue なしでも is_github フィールドを含む。"""
        with mock.patch("handover._run_git", return_value=""):
            with mock.patch("handover.is_github_repo", return_value=True):
                result = handover.collect_handover_data("/tmp/proj")

        assert "is_github" in result
        assert result["is_github"] is True

    def test_default_output_is_github_false(self, data_dir):
        """非 GitHub リポでは is_github=False。"""
        with mock.patch("handover._run_git", return_value=""):
            with mock.patch("handover.is_github_repo", return_value=False):
                result = handover.collect_handover_data("/tmp/proj")

        assert result["is_github"] is False


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


class TestRunGitCwd:
    """_run_git() の cwd パラメータテスト。"""

    def test_cwd_passed_to_subprocess(self):
        """cwd が subprocess.run に渡される。"""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "main\n"

        with mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            handover._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd="/some/project")

        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == "/some/project"

    def test_cwd_none_by_default(self):
        """cwd 省略時は None（呼び出し元の CWD を使用）。"""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "main\n"

        with mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            handover._run_git(["rev-parse", "--abbrev-ref", "HEAD"])

        _, kwargs = mock_run.call_args
        assert kwargs.get("cwd") is None


class TestCollectWorkContextCwd:
    """_collect_work_context_from_git() の project_dir 伝播テスト。"""

    def test_project_dir_passed_to_run_git(self):
        """project_dir が _run_git の cwd に伝播する。"""
        with mock.patch("handover._run_git", return_value="") as mock_git:
            handover._collect_work_context_from_git(project_dir="/my/project")

        for call in mock_git.call_args_list:
            _, kwargs = call
            assert kwargs.get("cwd") == "/my/project"

    def test_project_dir_none_default(self):
        """project_dir 省略時は cwd=None。"""
        with mock.patch("handover._run_git", return_value="") as mock_git:
            handover._collect_work_context_from_git()

        for call in mock_git.call_args_list:
            _, kwargs = call
            assert kwargs.get("cwd") is None


class TestCollectHandoverDataCwd:
    """collect_handover_data() → _collect_work_context_from_git() への project_dir 伝播。"""

    def test_project_dir_flows_to_git_fallback(self, project_dir, data_dir):
        """checkpoint なし時、project_dir が git フォールバックに伝播する。"""
        with mock.patch("handover._run_git", return_value="") as mock_git:
            handover.collect_handover_data(str(project_dir))

        for call in mock_git.call_args_list:
            _, kwargs = call
            assert kwargs.get("cwd") == str(project_dir)


class TestIsGithubRepoCwd:
    """is_github_repo() の cwd パラメータテスト。"""

    def test_cwd_passed_to_run_git(self):
        """cwd が _run_git に伝播する。"""
        with mock.patch("handover._run_git", return_value="git@github.com:user/repo.git\n") as mock_git:
            handover.is_github_repo(cwd="/my/project")

        _, kwargs = mock_git.call_args
        assert kwargs.get("cwd") == "/my/project"


class TestIsGithubRepo:
    """is_github_repo() のテスト。"""

    def test_github_ssh_remote(self):
        """GitHub SSH リモートを検出する。"""
        with mock.patch("handover._run_git", return_value="git@github.com:user/repo.git\n"):
            assert handover.is_github_repo() is True

    def test_github_https_remote(self):
        """GitHub HTTPS リモートを検出する。"""
        with mock.patch("handover._run_git", return_value="https://github.com/user/repo.git\n"):
            assert handover.is_github_repo() is True

    def test_non_github_remote(self):
        """GitHub 以外のリモートは False。"""
        with mock.patch("handover._run_git", return_value="git@gitlab.com:user/repo.git\n"):
            assert handover.is_github_repo() is False

    def test_no_remote(self):
        """リモートなしは False。"""
        with mock.patch("handover._run_git", return_value=""):
            assert handover.is_github_repo() is False


class TestFormatIssueTitle:
    """format_issue_title() のテスト。"""

    def test_includes_date_and_branch(self):
        """タイトルにブランチ名と日付を含む。"""
        data = {
            "timestamp": "2026-03-27T10:00:00+00:00",
            "work_context": {"git_branch": "feat/handover-issue"},
        }
        title = handover.format_issue_title(data)
        assert "feat/handover-issue" in title
        assert "2026-03-27" in title

    def test_no_branch(self):
        """ブランチなしでもエラーにならない。"""
        data = {
            "timestamp": "2026-03-27T10:00:00+00:00",
            "work_context": {"git_branch": ""},
        }
        title = handover.format_issue_title(data)
        assert "2026-03-27" in title


class TestFormatIssueBody:
    """format_issue_body() のテスト。"""

    def test_includes_all_sections(self):
        """必須セクション（Decisions 等のプレースホルダ + Context）を含む。"""
        data = {
            "project_dir": "/tmp/proj",
            "timestamp": "2026-03-27T10:00:00+00:00",
            "work_context": {
                "git_branch": "feat/test",
                "recent_commits": ["abc1234 feat: test"],
                "uncommitted_files": ["M  src/app.py"],
            },
            "skills_used": [{"skill": "ship", "timestamp": "2026-03-27T10:00:00+00:00"}],
            "corrections": [],
        }
        body = handover.format_issue_body(data)
        assert "## Decisions" in body
        assert "## Discarded Alternatives" in body
        assert "## Deploy State" in body
        assert "## Next Actions" in body
        assert "## Context (auto)" in body
        assert "feat/test" in body
        assert "abc1234" in body

    def test_empty_data(self):
        """空データでもエラーにならない。"""
        data = {
            "project_dir": "/tmp/proj",
            "timestamp": "2026-03-27T10:00:00+00:00",
            "work_context": {
                "git_branch": "",
                "recent_commits": [],
                "uncommitted_files": [],
            },
            "skills_used": [],
            "corrections": [],
        }
        body = handover.format_issue_body(data)
        assert "## Context (auto)" in body


class TestCreateIssue:
    """create_issue() のテスト。"""

    def test_happy_path(self):
        """gh issue create が成功し URL を返す。"""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/user/repo/issues/42\n"

        with mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            url = handover.create_issue("Test title", "Test body", ["handover"])
            assert url == "https://github.com/user/repo/issues/42"
            args = mock_run.call_args[0][0]
            assert "gh" in args
            assert "issue" in args
            assert "create" in args
            assert "--label" in args

    def test_failure_returns_none(self):
        """gh issue create が失敗したら None。"""
        mock_result = mock.Mock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with mock.patch("subprocess.run", return_value=mock_result):
            url = handover.create_issue("Test title", "Test body")
            assert url is None

    def test_no_labels(self):
        """ラベルなしでも動く。"""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/user/repo/issues/43\n"

        with mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            url = handover.create_issue("Title", "Body")
            assert url is not None
            args = mock_run.call_args[0][0]
            assert "--label" not in args
