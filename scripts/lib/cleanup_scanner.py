"""cleanup スキル用の後片付け候補スキャナ群。

`/rl-anything:cleanup` から呼ばれる純粋なスキャナ関数を提供する。
副作用（削除）は含まず、候補リストの返却に責務を限定する。

Design notes:
- `git_cmd` callable を注入可能にしてテスト容易性を確保する。
- 外部コマンド失敗時は例外を潰さず caller にハンドリングを委ねる。
  （呼び出し側の SKILL で graceful degradation する方針）
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Callable, Iterable, Optional


GitCmd = Callable[[list[str]], str]


def _default_git_cmd(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def scan_merged_branches(
    base_branches: Iterable[str],
    current_branch: str,
    protected: Iterable[str],
    git_cmd: Optional[GitCmd] = None,
) -> list[str]:
    """`base_branches` の少なくとも一つにマージ済みのローカルブランチを列挙する。

    現在 checkout 中のブランチ、`protected` に含まれるブランチは常に除外する。
    """
    git = git_cmd or _default_git_cmd
    protected_set = set(protected) | {current_branch}

    merged: set[str] = set()
    order: list[str] = []
    for base in base_branches:
        output = git(["branch", "--merged", base, "--format=%(refname:short)"])
        for raw_line in output.splitlines():
            name = raw_line.lstrip("*").strip()
            if not name or name in protected_set:
                continue
            if name in merged:
                continue
            merged.add(name)
            order.append(name)
    return order


_PRUNE_LINE_RE = re.compile(r"\[(?:would prune|pruned)\]\s+(\S+)")


def scan_prunable_remote_refs(git_cmd: Optional[GitCmd] = None) -> list[str]:
    """`git fetch --prune --dry-run` の出力から prune 候補を抽出する。"""
    git = git_cmd or _default_git_cmd
    output = git(["fetch", "--prune", "--dry-run"])
    return [m.group(1) for m in _PRUNE_LINE_RE.finditer(output)]


def scan_removable_worktrees(
    main_worktree_path: str,
    git_cmd: Optional[GitCmd] = None,
) -> list[dict]:
    """削除可能な worktree 候補を返す。

    メイン worktree（リポジトリ本体）と `locked` な worktree は除外する。
    戻り値: `[{"path": str, "branch": str | None, "head": str}, ...]`
    """
    git = git_cmd or _default_git_cmd
    output = git(["worktree", "list", "--porcelain"])

    worktrees: list[dict] = []
    current: dict = {}

    def flush() -> None:
        if current:
            worktrees.append(current.copy())
            current.clear()

    for line in output.splitlines():
        if not line.strip():
            flush()
            continue
        if line.startswith("worktree "):
            flush()
            current["path"] = line[len("worktree "):].strip()
            current["locked"] = False
            current["branch"] = None
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):].strip()
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            current["branch"] = ref.removeprefix("refs/heads/")
        elif line.strip() == "locked" or line.startswith("locked "):
            current["locked"] = True
    flush()

    normalized_main = os.path.normpath(main_worktree_path)
    removable = []
    for wt in worktrees:
        if wt.get("locked"):
            continue
        if os.path.normpath(wt.get("path", "")) == normalized_main:
            continue
        removable.append({
            "path": wt["path"],
            "branch": wt.get("branch"),
            "head": wt.get("head"),
        })
    return removable


# dogfood (PR #70) で `/tmp/claude-501` (Claude Code ランタイム UID dir) と
# `/tmp/claude-mcp-*` (実行中 MCP server bridge) を削除候補に含める危険なバグを検出。
# defense-in-depth として、呼び出し側が `claude-` を prefix に指定しても
# 絶対に削除してはいけないものは scanner 側で除外する安全網を常時有効化する。
_DEFAULT_TMP_EXCLUDE_PATTERNS: tuple[str, ...] = (
    r"^claude-\d+$",       # /tmp/claude-<uid> (Claude Code runtime socket/pid dir)
    r"^claude-mcp-.*",     # /tmp/claude-mcp-*  (running MCP server bridges)
)


def scan_tmp_dirs(
    prefixes: Iterable[str],
    tmp_root: str = "/tmp",
    exclude_patterns: Optional[Iterable[str]] = None,
) -> list[str]:
    """`tmp_root` 配下で `prefixes` に前方一致するディレクトリの絶対パスを返す。

    `exclude_patterns` は basename に対して re.search でマッチングする。`None` を渡すと
    デフォルトの安全網 (`_DEFAULT_TMP_EXCLUDE_PATTERNS`) が適用される。`[]` を渡せば
    明示的に無効化できる（通常は非推奨）。
    """
    if not os.path.isdir(tmp_root):
        return []
    prefix_list = list(prefixes)
    patterns = _DEFAULT_TMP_EXCLUDE_PATTERNS if exclude_patterns is None else list(exclude_patterns)
    compiled = [re.compile(p) for p in patterns]

    results: list[str] = []
    for name in sorted(os.listdir(tmp_root)):
        if not any(name.startswith(p) for p in prefix_list):
            continue
        if any(rx.search(name) for rx in compiled):
            continue
        full = os.path.join(tmp_root, name)
        if not os.path.isdir(full):
            continue
        results.append(full)
    return results


_ISSUE_RE = re.compile(r"(?:issue-|#)(\d+)")


def extract_issue_numbers_from_branch(name: str) -> list[int]:
    """ブランチ名から issue 番号を抽出する（重複排除・出現順保持）。

    `issue-\\d+` / `#\\d+` のみを拾う。`release/1.32.0` のような裸の数字は拾わない。
    """
    if not name:
        return []
    seen: set[int] = set()
    numbers: list[int] = []
    for match in _ISSUE_RE.finditer(name):
        n = int(match.group(1))
        if n in seen:
            continue
        seen.add(n)
        numbers.append(n)
    return numbers


_UNCHECKED_RE = re.compile(r"^\s*-\s*\[\s\]\s+(.+?)\s*$")


def parse_prefix_config(value: Optional[str]) -> list[str]:
    """userConfig の `cleanup_tmp_prefixes` (カンマ区切り文字列) を list に展開する。

    Claude Code の `manifest.userConfig` は boolean/number/string のみサポートする
    ため、複数 prefix を指定する手段としてカンマ区切り文字列を採用している。この
    関数は以下を保証する:

    - 各要素の前後空白を trim
    - 空要素・空白のみ要素は無視
    - 重複は最初の出現順を保持して排除
    - `None` や空文字は空 list を返す（呼び出し側で「候補なし」扱いにできる）
    """
    if not value or not value.strip():
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in value.split(","):
        item = raw.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def extract_unchecked_testplan(pr_body: Optional[str]) -> list[str]:
    """PR 本文から未チェック `- [ ]` 項目を抽出する。"""
    if not pr_body:
        return []
    result: list[str] = []
    for line in pr_body.splitlines():
        match = _UNCHECKED_RE.match(line)
        if match:
            result.append(match.group(1))
    return result
