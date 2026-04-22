"""cleanup_scanner.py のテスト。

Issue #69: 後片付けスキル用のスキャナ関数群をテスト駆動で定義する。
外部コマンド（git / fs）は `git_cmd` や `tmp_root` 引数でモック可能な設計にする。
"""
import sys
from pathlib import Path

_lib = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(_lib))

from cleanup_scanner import (
    extract_issue_numbers_from_branch,
    extract_unchecked_testplan,
    scan_merged_branches,
    scan_prunable_remote_refs,
    scan_removable_worktrees,
    scan_tmp_dirs,
)


# ---------- scan_merged_branches ----------

def test_scan_merged_branches_excludes_current_and_protected():
    """マージ済みでも、現在ブランチ・main/master/develop は除外する。"""
    def fake_git(args):
        assert args == ["branch", "--merged", "main", "--format=%(refname:short)"]
        return "* feat/current\n  feat/done-1\n  main\n  master\n  feat/done-2\n  develop\n"

    result = scan_merged_branches(
        base_branches=["main"],
        current_branch="feat/current",
        protected=["main", "master", "develop"],
        git_cmd=fake_git,
    )
    assert result == ["feat/done-1", "feat/done-2"]


def test_scan_merged_branches_empty_when_no_merged():
    def fake_git(args):
        return "* main\n"

    result = scan_merged_branches(
        base_branches=["main"],
        current_branch="main",
        protected=["main"],
        git_cmd=fake_git,
    )
    assert result == []


def test_scan_merged_branches_strips_asterisk_and_whitespace():
    """`* ` 付きの現在ブランチマーカーを正しく除去する。"""
    def fake_git(args):
        return "  feat/a\n* feat/current\n  feat/b  \n"

    result = scan_merged_branches(
        base_branches=["main"],
        current_branch="feat/current",
        protected=[],
        git_cmd=fake_git,
    )
    assert result == ["feat/a", "feat/b"]


# ---------- scan_prunable_remote_refs ----------

def test_scan_prunable_remote_refs_parses_dry_run_output():
    """`git fetch --prune --dry-run` の出力から prune 候補を抽出する。"""
    def fake_git(args):
        assert args == ["fetch", "--prune", "--dry-run"]
        return (
            "From github.com:min-sys/rl-anything\n"
            " - [would prune] origin/feat/merged-a\n"
            " - [would prune] origin/feat/merged-b\n"
        )

    result = scan_prunable_remote_refs(git_cmd=fake_git)
    assert result == ["origin/feat/merged-a", "origin/feat/merged-b"]


def test_scan_prunable_remote_refs_handles_pruned_token():
    """一部環境では `[pruned]` 表記になる。"""
    def fake_git(args):
        return " x [pruned] origin/old-ref\n"

    result = scan_prunable_remote_refs(git_cmd=fake_git)
    assert result == ["origin/old-ref"]


def test_scan_prunable_remote_refs_empty_when_clean():
    def fake_git(args):
        return ""

    assert scan_prunable_remote_refs(git_cmd=fake_git) == []


# ---------- scan_removable_worktrees ----------

def test_scan_removable_worktrees_excludes_main_and_locked():
    """メイン worktree と locked な worktree は除外。"""
    porcelain = (
        "worktree /Users/me/proj\n"
        "HEAD abc123\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /Users/me/proj-wt-feature\n"
        "HEAD def456\n"
        "branch refs/heads/feature\n"
        "\n"
        "worktree /Users/me/proj-wt-hotfix\n"
        "HEAD 789abc\n"
        "branch refs/heads/hotfix\n"
        "locked\n"
        "\n"
    )

    def fake_git(args):
        assert args == ["worktree", "list", "--porcelain"]
        return porcelain

    result = scan_removable_worktrees(
        main_worktree_path="/Users/me/proj",
        git_cmd=fake_git,
    )
    assert len(result) == 1
    assert result[0]["path"] == "/Users/me/proj-wt-feature"
    assert result[0]["branch"] == "feature"


def test_scan_removable_worktrees_empty_when_only_main():
    porcelain = (
        "worktree /Users/me/proj\n"
        "HEAD abc123\n"
        "branch refs/heads/main\n"
        "\n"
    )

    def fake_git(args):
        return porcelain

    result = scan_removable_worktrees(
        main_worktree_path="/Users/me/proj",
        git_cmd=fake_git,
    )
    assert result == []


# ---------- scan_tmp_dirs ----------

def test_scan_tmp_dirs_matches_prefixes(tmp_path):
    """指定 prefix にマッチするディレクトリだけを返す。"""
    (tmp_path / "claude-sandbox-1").mkdir()
    (tmp_path / "gstack-qa-2").mkdir()
    (tmp_path / "rl-anything-bench-3").mkdir()
    (tmp_path / "other-keep").mkdir()
    (tmp_path / "claude-not-a-dir.txt").write_text("x")

    result = scan_tmp_dirs(
        prefixes=["claude-", "gstack-", "rl-anything-"],
        tmp_root=str(tmp_path),
    )
    names = sorted(Path(p).name for p in result)
    assert names == ["claude-sandbox-1", "gstack-qa-2", "rl-anything-bench-3"]


def test_scan_tmp_dirs_returns_empty_when_no_match(tmp_path):
    (tmp_path / "keep-me").mkdir()
    assert scan_tmp_dirs(prefixes=["claude-"], tmp_root=str(tmp_path)) == []


def test_scan_tmp_dirs_handles_missing_root(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert scan_tmp_dirs(prefixes=["claude-"], tmp_root=str(missing)) == []


# ---------- extract_issue_numbers_from_branch ----------

def test_extract_issue_numbers_issue_dash_prefix():
    assert extract_issue_numbers_from_branch("feat/issue-69-cleanup-skill") == [69]


def test_extract_issue_numbers_hash_prefix():
    assert extract_issue_numbers_from_branch("fix/#42-bug") == [42]


def test_extract_issue_numbers_multiple():
    """複数 issue 番号が含まれる場合は重複なく返す。"""
    result = extract_issue_numbers_from_branch("feat/issue-10-issue-10-combo")
    assert result == [10]


def test_extract_issue_numbers_none():
    assert extract_issue_numbers_from_branch("main") == []
    assert extract_issue_numbers_from_branch("feat/no-number") == []


def test_extract_issue_numbers_does_not_match_bare_digits():
    """裸の数字は issue 番号扱いしない（false positive 回避）。"""
    assert extract_issue_numbers_from_branch("release/1.32.0") == []


# ---------- extract_unchecked_testplan ----------

def test_extract_unchecked_testplan_finds_unchecked_boxes():
    body = (
        "## Summary\n\n"
        "fix stuff\n\n"
        "## Test plan\n"
        "- [x] Unit tests pass\n"
        "- [ ] Manually verify the happy path\n"
        "- [ ] Check error handling on 404\n"
    )
    result = extract_unchecked_testplan(body)
    assert result == [
        "Manually verify the happy path",
        "Check error handling on 404",
    ]


def test_extract_unchecked_testplan_empty_when_all_checked():
    body = "- [x] done 1\n- [x] done 2\n"
    assert extract_unchecked_testplan(body) == []


def test_extract_unchecked_testplan_handles_none_or_empty():
    assert extract_unchecked_testplan("") == []
    assert extract_unchecked_testplan(None) == []


def test_extract_unchecked_testplan_strips_leading_whitespace():
    """インデント付きチェックボックスも拾う。"""
    body = "  - [ ] nested item\n    - [ ] deeper item\n"
    result = extract_unchecked_testplan(body)
    assert result == ["nested item", "deeper item"]
