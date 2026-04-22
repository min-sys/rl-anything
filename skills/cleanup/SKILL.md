---
name: cleanup
effort: low
description: |
  PR マージ・デプロイ後に残る後片付け（マージ済みローカルブランチ削除、remote refs の prune、一時 worktree 削除、一時ディレクトリ削除、関連 Issue の close 候補提案、元 PR の Test plan 残件リマインド）を候補提示→個別承認→実行で安全に片付ける。
  Trigger: cleanup, 後片付け, 片付け, ブランチ整理, worktree 整理, merged branches, stale branches, prune, tidy up, /ship 後の片付け
allowed-tools: Bash, Read, AskUserQuestion
---

# cleanup — デプロイ後の後片付け

PR マージ・デプロイ完了後に残る以下の「痕跡」を、**候補を列挙 → `AskUserQuestion` で個別承認 → 実行** の流れで安全に片付ける。

1. マージ済みローカルブランチの削除
2. stale な remote tracking branch の prune
3. 一時 worktree の削除（`locked` は除外）
4. `/tmp/rl-anything-*` 配下の削除（CRITICAL: `claude-` / `gstack-` はランタイム領域と衝突するためデフォルト対象外。拡張は Issue #71 で userConfig 化予定）
5. マージ済みブランチ名から推定した関連 Issue の close 候補提案（**自動 close はしない**）
6. 元 PR の Test plan 未完了チェックの残件リマインド

**なぜ個別承認が必要か**: これらはどれも不可逆寄りの操作（ブランチ削除・ディレクトリ削除・fetch --prune）で、かつ「他セッションが作業中のもの」や「ユーザーが意図的に残しているもの」が混ざる可能性がある。一括実行すると取り返しがつかなくなるため、1 候補ずつ承認を取る。

## 実行手順

### Step 1: 候補の収集（副作用なし）

`scripts/lib/cleanup_scanner.py` の純粋関数で候補を全カテゴリ一括収集する。副作用ゼロ（読み取りのみ）。

```python
# スキル内から Bash 経由で実行する想定のスニペット
import json, os, subprocess, sys
sys.path.insert(0, "scripts/lib")
from cleanup_scanner import (
    scan_merged_branches, scan_prunable_remote_refs,
    scan_removable_worktrees, scan_tmp_dirs,
    extract_issue_numbers_from_branch, extract_unchecked_testplan,
)

current = subprocess.run(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    capture_output=True, text=True
).stdout.strip()
main_wt = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"],
    capture_output=True, text=True
).stdout.strip()

merged = scan_merged_branches(
    base_branches=["main"],
    current_branch=current,
    protected=["main", "master", "develop"],
)
prune = scan_prunable_remote_refs()
worktrees = scan_removable_worktrees(main_worktree_path=main_wt)
tmp_dirs = scan_tmp_dirs(prefixes=["rl-anything-"])  # narrow default — see CRITICAL note below
```

**収集結果を一覧表示**してからユーザーに見せる:

```
後片付け候補
═══════════
[1] マージ済みローカルブランチ: 3 件
    - feat/issue-65-foo
    - feat/issue-66-bar
    - hotfix/typo
[2] Remote prune 候補: 2 件
    - origin/feat/issue-65-foo
    - origin/feat/issue-66-bar
[3] 削除可能 worktree: 1 件
    - /Users/.../proj-wt-review (branch=review/pr-64)
[4] 一時ディレクトリ: 2 件
    - /tmp/claude-sandbox-abc
    - /tmp/gstack-qa-xyz
[5] close 候補 Issue: #65, #66
[6] PR Test plan 残件: 1 件
    - #64: "Manually verify on staging"
```

候補がゼロなら「片付けるものはありません」と返して終了。

### Step 2: カテゴリごとに個別承認 → 実行

カテゴリ単位で順に確認する。各カテゴリ内で候補が複数ある場合、**1 つずつ** `AskUserQuestion` で承認を取る（一括の "Yes to all" は提供しない）。

#### カテゴリ 1: マージ済みローカルブランチ

各ブランチについて:

```
ローカルブランチ `feat/issue-65-foo` を削除しますか？
(git branch -D feat/issue-65-foo)

A) Yes - 削除する
B) Skip - このブランチは残す
C) Abort - 以降の cleanup を中止する
```

承認時: `git branch -D <name>` を実行し、結果を報告。

#### カテゴリ 2: Remote prune

prune はブランチ単位ではなく `git fetch --prune` で一括実行される操作なので、**全候補をまとめて 1 つの質問**にする:

```
以下の stale remote refs を prune しますか？
- origin/feat/issue-65-foo
- origin/feat/issue-66-bar
(git fetch --prune)

A) Yes - prune する
B) Skip
```

#### カテゴリ 3: 一時 worktree

各 worktree について:

```
worktree `/Users/.../proj-wt-review` (branch=review/pr-64) を削除しますか？
(git worktree remove /Users/.../proj-wt-review)

A) Yes - 削除する
B) Skip
C) Abort
```

`locked` worktree はそもそもスキャナが返さないのでここには出ない。

#### カテゴリ 4: 一時ディレクトリ

初版デフォルト prefix は **`rl-anything-` のみ**。`claude-` / `gstack-` は Claude Code ランタイム (`/tmp/claude-<uid>`) や MCP bridge (`/tmp/claude-mcp-*`)、gstack 作業ディレクトリ (`/tmp/gstack-work`) と衝突し、削除するとセッションが壊れる危険があるため**デフォルトから除外**している。なお scanner 側 `_DEFAULT_TMP_EXCLUDE_PATTERNS` で `claude-<uid>` / `claude-mcp-*` は二重に保護している（ユーザー独自拡張時の保険）。prefix 拡張は Issue #71 で userConfig 化予定。

各ディレクトリについて個別に:

```
一時ディレクトリ `/tmp/rl-anything-bench-abc` を削除しますか？
(rm -rf /tmp/rl-anything-bench-abc)

A) Yes - 削除する
B) Skip
C) Abort
```

`rm -rf` 実行前に、パスが `/tmp/rl-anything-` で始まることを再確認する（防衛）。

#### カテゴリ 5: 関連 Issue close 候補

**自動 close は絶対にしない**。`gh` が利用可能なら各 issue の状態を確認し、既に closed なら黙ってスキップ。OPEN の issue についてのみ:

```
Issue #65 ("ブランチ名: feat/issue-65-foo" から推定) は close 候補です。
現在の状態: OPEN

A) gh issue view #65 で中身を確認する
B) Skip - 手動で判断する
C) gh issue close #65 でクローズ（内容を確認済みの場合のみ）
```

C を選んだ場合も、直前に `gh issue view` で本文を表示し「本当に close しますか？」で最終確認する。

#### カテゴリ 6: PR Test plan 残件

これは**削除ではなくリマインダー**。実行はせず、表示のみ。

```
元 PR の Test plan に未完了チェックが残っています:
- #64:
  - [ ] Manually verify on staging

対応しますか？
A) 手動で対応する（このまま終了）
B) 該当 PR を gh pr view で開く
C) Skip
```

### Step 3: 未コミット変更のガード

スキル実行の冒頭（Step 1 より前）で以下を確認する:

```bash
if [ -n "$(git status --porcelain)" ]; then
  # 未コミット変更あり
fi
```

未コミット変更がある場合、`AskUserQuestion` で確認:

```
未コミットの変更があります。cleanup は破壊的な操作を含むため、
先に commit / stash しておくことを推奨します。

A) このまま続行する（リスク承知）
B) 中止して commit / stash してから再実行
```

B を選んだら即終了。

### Step 4: サマリ報告

全カテゴリ処理後、結果を集約:

```
cleanup 完了
═══════════
削除ブランチ: 2 件 (feat/issue-65-foo, feat/issue-66-bar)
Prune: 実行
削除 worktree: 1 件
削除 tmp dir: 1 件
Issue close: 0 件（手動で対応）
Test plan リマインド: 1 件（#64）
```

## エッジケース

- **`git` / `gh` 未インストール**: `command -v git` / `command -v gh` で事前チェック。`gh` が無い場合はカテゴリ 5 と 6 を「スキップ（gh 未インストール）」として表示のみ。
- **リモート未設定**: `git remote -v` が空なら カテゴリ 2（prune）はスキップ。
- **デフォルトブランチが `main` 以外**: `git symbolic-ref refs/remotes/origin/HEAD` で解決。解決できなければ `main` と `master` の両方を base として試す。
- **候補がゼロ**: Step 1 時点で全カテゴリ空なら「片付けるものはありません」と返して終了。
- **`Abort` 選択**: 以降の全カテゴリをスキップし、そこまでの結果でサマリ表示して終了。
- **ブランチ削除で `-D` が失敗**: upstream 未 merge 等のケース。エラーを表示し、そのブランチはスキップして次へ進む（`-d` へのフォールバックはしない — 意図して `-D` 使用）。

## 既存スキルとの関係

| スキル | カバー範囲 |
|--------|-----------|
| `/ship` (gstack) | PR 作成まで |
| `/land-and-deploy` (gstack) | マージ + デプロイ検証まで |
| **`/rl-anything:cleanup`** | **マージ・デプロイ後の痕跡掃除** |

将来的に gstack flow-chain の末尾に cleanup を組み込むことを検討（別 issue）。

## 使用例

```
# 全カテゴリ対話的に処理
/rl-anything:cleanup

# 会話上で「ブランチ整理したい」等の発話でも起動可能
```
