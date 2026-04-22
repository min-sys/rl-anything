"""cleanup_scanner.py のテスト。

Issue #69: 後片付けスキル用のスキャナ関数群をテスト駆動で定義する。
外部コマンド（git / fs）は `git_cmd` や `tmp_root` 引数でモック可能な設計にする。
"""
import os
import sys
from pathlib import Path

_lib = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(_lib))

from cleanup_scanner import (
    extract_issue_numbers_from_branch,
    extract_unchecked_testplan,
    parse_prefix_config,
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


def test_scan_tmp_dirs_default_excludes_claude_runtime_uid(tmp_path):
    """`/tmp/claude-<uid>` は Claude Code のランタイムディレクトリで絶対に削除してはいけない。

    dogfood (PR #70) で `/tmp/claude-501` が候補に含まれるバグを検出したための defense-in-depth。
    ユーザーが prefix `claude-` を明示的に指定した場合でも、デフォルト exclude_patterns で守る。
    """
    (tmp_path / "claude-501").mkdir()
    (tmp_path / "claude-12345").mkdir()
    (tmp_path / "claude-sandbox-ok").mkdir()

    result = scan_tmp_dirs(prefixes=["claude-"], tmp_root=str(tmp_path))
    names = sorted(os.path.basename(p) for p in result)
    assert names == ["claude-sandbox-ok"], (
        f"UID 付き claude-<digits> はデフォルトで除外されるべき。got: {names}"
    )


def test_scan_tmp_dirs_default_excludes_mcp_bridge(tmp_path):
    """`/tmp/claude-mcp-*` は実行中の MCP server bridge なので削除禁止。"""
    (tmp_path / "claude-mcp-browser-bridge-matsukaze").mkdir()
    (tmp_path / "claude-mcp-gmail").mkdir()
    (tmp_path / "claude-scratch-ok").mkdir()

    result = scan_tmp_dirs(prefixes=["claude-"], tmp_root=str(tmp_path))
    names = sorted(os.path.basename(p) for p in result)
    assert names == ["claude-scratch-ok"], (
        f"claude-mcp-* はデフォルトで除外されるべき。got: {names}"
    )


def test_scan_tmp_dirs_custom_exclude_patterns(tmp_path):
    """呼び出し側で独自の exclude_patterns を指定できる。

    デフォルトを上書きする形で `exclude_patterns=[]` を渡すと、exclusion を解除できる
    （ただし通常は推奨しない — デフォルトはセーフティネットとして機能する）。
    """
    (tmp_path / "gstack-work").mkdir()
    (tmp_path / "gstack-scratch-ok").mkdir()

    result = scan_tmp_dirs(
        prefixes=["gstack-"],
        tmp_root=str(tmp_path),
        exclude_patterns=[r"gstack-work$"],
    )
    names = sorted(os.path.basename(p) for p in result)
    assert names == ["gstack-scratch-ok"]


# ---------- parse_prefix_config ----------

def test_parse_prefix_config_single():
    assert parse_prefix_config("rl-anything-") == ["rl-anything-"]


def test_parse_prefix_config_multiple():
    """カンマ区切りで複数 prefix を受け付ける。"""
    result = parse_prefix_config("rl-anything-,claude-sandbox-,gstack-scratch-")
    assert result == ["rl-anything-", "claude-sandbox-", "gstack-scratch-"]


def test_parse_prefix_config_trims_whitespace():
    """各要素前後の空白を除去する（人間が手書きで編集する想定）。"""
    result = parse_prefix_config(" rl-anything- , claude-sandbox- ")
    assert result == ["rl-anything-", "claude-sandbox-"]


def test_parse_prefix_config_drops_empty_items():
    """空要素（連続カンマ・前後カンマ）は無視する。"""
    result = parse_prefix_config(",rl-anything-,,claude-sandbox-,")
    assert result == ["rl-anything-", "claude-sandbox-"]


def test_parse_prefix_config_dedupes_preserving_order():
    """重複 prefix は最初の出現順を保持して排除する。"""
    result = parse_prefix_config("rl-anything-,claude-sandbox-,rl-anything-")
    assert result == ["rl-anything-", "claude-sandbox-"]


def test_parse_prefix_config_empty_or_whitespace_returns_empty():
    """空文字・空白のみは空 list を返す（scan を実質無効化）。"""
    assert parse_prefix_config("") == []
    assert parse_prefix_config("   ") == []
    assert parse_prefix_config(",,,") == []


def test_parse_prefix_config_handles_none():
    """None も空 list にフォールバック（load_user_config が未設定時に None を返す可能性に備える）。"""
    assert parse_prefix_config(None) == []


def test_scan_tmp_dirs_override_exclude_patterns_with_empty_list(tmp_path):
    """exclude_patterns=[] を明示的に渡すとデフォルトの安全網を外せる。

    逃げ道として残してあるが、SKILL.md は明示的にこれをしないことを前提とする。
    """
    (tmp_path / "claude-501").mkdir()

    result = scan_tmp_dirs(
        prefixes=["claude-"],
        tmp_root=str(tmp_path),
        exclude_patterns=[],
    )
    names = sorted(os.path.basename(p) for p in result)
    assert names == ["claude-501"]


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
