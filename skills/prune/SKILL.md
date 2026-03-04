---
name: prune
description: |
  Detect unused artifacts (dead globs, zero invocations, duplicates) and propose archiving.
  Never deletes directly — all archiving requires human approval.
  Trigger: prune, 淘汰, cleanup, archive, 未使用削除, unused
disable-model-invocation: true
---

# /rl-anything:prune — 未使用アーティファクトの淘汰

dead glob・zero invocation・重複の3基準でアーティファクトを検出し、アーカイブを提案する。
直接削除は行わない（MUST NOT）。全淘汰は人間承認が必須（MUST）。

## Usage

```
/rl-anything:prune [project-dir]
/rl-anything:prune --restore          # アーカイブから復元
/rl-anything:prune --list-archive     # アーカイブ一覧表示
```

## 実行手順

### Step 1: 候補検出

```bash
python3 <PLUGIN_DIR>/skills/prune/scripts/prune.py "$(pwd)"
```

### Step 2: 候補リストの表示 + 推薦ラベル判定

検出された候補を以下のカテゴリ別に表示:
- **Dead Glob**: rules の paths 対象がマッチしないもの
- **Zero Invocation**: 30日間使用記録がないもの（カスタムスキルのみ）
- **Plugin Unused**: プラグイン由来で未使用のスキル（レポートのみ、アーカイブ対象外）
- **Global 候補**: Usage Registry で cross-PJ 使用状況を確認
- **重複候補**: audit-report の意味的類似度検出結果

Plugin Unused のスキルはアーカイブ対象外とする（MUST）。
「未使用。`claude plugin uninstall` を検討？」とレポートのみ出力する。

#### コンテキスト収集（MUST）

Step 1 の JSON 出力に各候補の `description`（SKILL.md から抽出済み）と `recommendation`（Python 一次判定）が含まれる。

各候補スキルの SKILL.md を **Read で全文読み取り**、以下のチェックリストで推薦ラベルの最終判定を行う（MUST）。Python 一次判定（`recommendation` フィールド）を上書きしてよい。

**archive推奨チェックリスト:**
- [ ] 特定PJ固有で他PJでは使えない
- [ ] 一時デバッグ・hotfix 用途で目的完了済み
- [ ] 他スキルに機能が統合済み
- [ ] description に "deprecated" や "obsolete" を含む

**keep推奨チェックリスト:**
- [ ] 複数PJで利用可能な汎用スキル
- [ ] リファレンス・テンプレート価値がある
- [ ] 定期的に必要になる性質（daily, weekly, deploy 等）
- [ ] Trigger が3個以上定義されている

**判定ルール**: いずれか2つ以上該当 → そのラベル、両方1つずつ or いずれも0 → 要確認

#### description 空文字時のフォールバック

候補の `description` が空文字の場合は `"(説明なし)"` と表示する（MUST）。
その場合、SKILL.md 全文を Read で読み取り、1行要約を生成して表示に使用する（MUST）。

### Step 3: 人間承認フロー（2段階）（MUST）

自動的にアーカイブを実行してはならない（MUST NOT）。
AskUserQuestion の options は常に **4つ以下** とする（MUST）。

#### Stage 1: テキスト出力で全候補一覧を表示

カテゴリごとに候補一覧をテキスト出力する（MUST）。各スキルは以下の形式:

```
### Zero Invocation（過去30日間 呼び出しゼロ）

1. スキル名 [推薦ラベル]
   説明: description（空文字の場合は "(説明なし)"）

2. スキル名 [推薦ラベル]
   説明: description
```

#### Stage 2: AskUserQuestion で方針を選択（3択）

AskUserQuestion で以下の3つの options を提示する（MUST）:
- label: `全てアーカイブ`, description: `一覧の全候補をアーカイブする`
- label: `個別に選択`, description: `各候補について個別に判断する`
- label: `スキップ`, description: `全て維持し、何もしない`

候補が0件の場合は AskUserQuestion を表示せず「未使用スキルはありません」と報告する（MUST）。

#### Stage 3: 個別選択フロー（「個別に選択」の場合）

各候補スキルに対して個別に AskUserQuestion を表示する（MUST）。
質問テキストにスキル名・推薦ラベル・description を含め、options は3つ:
- label: `アーカイブ`, description: `このスキルをアーカイブする`
- label: `維持`, description: `このスキルを維持する`
- label: `後で判断`, description: `今回はスキップする`

### Step 4: アーカイブ実行

承認された候補のみ `~/.claude/rl-anything/archive/` に移動:

```python
from scripts.prune import archive_file
archive_file("/path/to/file", "zero_invocation")
```

### Step 5: 復元（--restore 時）

```python
from scripts.prune import restore_file, list_archive
items = list_archive()  # 一覧表示
restore_file("/path/to/archive/file")  # 復元
```

復元失敗時（archive にファイルが存在しない場合）はエラーメッセージを表示する。

## allowed-tools

Read, Bash, AskUserQuestion, Glob, Grep

## Tags

prune, archive, cleanup
