"""implement backfill のテスト."""

import json
from pathlib import Path

import pytest


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    return tmp_path


@pytest.fixture()
def git_repo(tmp_path):
    """テスト用の git リポジトリを作成."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test.com"}

    def run(*args):
        subprocess.run(args, cwd=repo, env={**dict(__import__("os").environ), **env},
                       capture_output=True, check=True)

    run("git", "init", "-b", "main")
    (repo / "README.md").write_text("# test")
    run("git", "add", ".")
    run("git", "commit", "-m", "chore(release): v1.0.0")

    # feat コミット群（1つ目の実装セッション）
    (repo / "src").mkdir()
    (repo / "src" / "auth.py").write_text("def login(): pass")
    run("git", "add", ".")
    run("git", "commit", "-m", "feat(auth): ログイン機能を追加")

    (repo / "src" / "auth_test.py").write_text("def test_login(): pass")
    run("git", "add", ".")
    run("git", "commit", "-m", "test(auth): ログインテストを追加")

    (repo / "src" / "api.py").write_text("def endpoint(): pass")
    run("git", "add", ".")
    run("git", "commit", "-m", "feat(api): API エンドポイントを追加")

    run("git", "commit", "--allow-empty", "-m", "chore(release): v1.1.0")

    # 2つ目の実装セッション（fix のみ）
    (repo / "src" / "auth.py").write_text("def login(): return True")
    run("git", "add", ".")
    run("git", "commit", "-m", "fix(auth): ログイン戻り値を修正")

    run("git", "commit", "--allow-empty", "-m", "chore(release): v1.1.1")

    return repo


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class TestParseGitSessions:
    def test_detects_sessions_between_releases(self, git_repo):
        from implement_backfill import parse_git_sessions

        sessions = parse_git_sessions(str(git_repo))
        # v1.0.0..v1.1.0 と v1.1.0..v1.1.1 の 2 セッション
        assert len(sessions) == 2

    def test_session_has_correct_fields(self, git_repo):
        from implement_backfill import parse_git_sessions

        sessions = parse_git_sessions(str(git_repo))
        s = sessions[0]  # v1.0.0..v1.1.0
        assert "commits" in s
        assert "files_changed" in s
        assert "ts" in s
        assert "version_from" in s
        assert "version_to" in s

    def test_first_session_has_3_commits(self, git_repo):
        from implement_backfill import parse_git_sessions

        sessions = parse_git_sessions(str(git_repo))
        s = sessions[0]
        # feat(auth) + test(auth) + feat(api) = 3 (release コミット自体は除外)
        assert s["commits"] == 3

    def test_second_session_has_1_commit(self, git_repo):
        from implement_backfill import parse_git_sessions

        sessions = parse_git_sessions(str(git_repo))
        s = sessions[1]
        assert s["commits"] == 1

    def test_files_changed_count(self, git_repo):
        from implement_backfill import parse_git_sessions

        sessions = parse_git_sessions(str(git_repo))
        # 1st session: auth.py, auth_test.py, api.py = 3
        assert sessions[0]["files_changed"] >= 3


class TestEstimateMode:
    def test_standard_for_small(self):
        from implement_backfill import estimate_mode

        assert estimate_mode(commits=3, files=2) == "standard"

    def test_parallel_for_large(self):
        from implement_backfill import estimate_mode

        assert estimate_mode(commits=8, files=6) == "parallel"


class TestBackfillImplement:
    def test_writes_usage_records(self, data_dir, git_repo):
        from implement_backfill import backfill_implement

        result = backfill_implement(str(git_repo))
        assert result["sessions_found"] >= 1
        assert result["records_written"] >= 1

        records = _load_jsonl(data_dir / "usage.jsonl")
        assert len(records) >= 1
        assert all(r["skill"] == "implement" for r in records)
        assert all(r.get("backfill") is True for r in records)

    def test_writes_growth_journal(self, data_dir, git_repo):
        from implement_backfill import backfill_implement

        backfill_implement(str(git_repo))

        records = _load_jsonl(data_dir / "growth-journal.jsonl")
        assert len(records) >= 1
        assert all(r["type"] == "implementation" for r in records)

    def test_idempotent(self, data_dir, git_repo):
        from implement_backfill import backfill_implement

        r1 = backfill_implement(str(git_repo))
        r2 = backfill_implement(str(git_repo))
        assert r2["records_written"] == 0  # 2回目は重複スキップ
