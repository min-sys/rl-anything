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

### Step 2: 候補リストの表示（コンテキスト付き）

検出された候補を以下のカテゴリ別に表示:
- **Dead Glob**: rules の paths 対象がマッチしないもの
- **Zero Invocation**: 30日間使用記録がないもの（カスタムスキルのみ）
- **Plugin Unused**: プラグイン由来で未使用のスキル（レポートのみ、アーカイブ対象外）
- **Global 候補**: Usage Registry で cross-PJ 使用状況を確認
- **重複候補**: audit-report の意味的類似度検出結果

Plugin Unused のスキルはアーカイブ対象外とする（MUST）。
「未使用。`claude plugin uninstall` を検討？」とレポートのみ出力する。

#### コンテキスト収集（MUST）

候補のスキルごとに SKILL.md を Read で読み取り、description（1行要約）を取得する（MUST）。
ユーザーが判断できるよう、各スキルの内容を把握した上で提示する。

### Step 3: 人間承認フロー（MUST）

自動的にアーカイブを実行してはならない（MUST NOT）。

AskUserQuestion で候補を提示する際、**各スキルの説明を含めて** multiSelect で選択させる（MUST）。

表示フォーマット例（Zero Invocation の場合）:
```
過去30日間で呼び出しゼロのスキルが3つあります。アーカイブするものを選んでください:
```
options に各スキルを **label: スキル名, description: SKILL.md から取得した1行説明** で列挙する。
加えて「全てアーカイブ」「スキップ（全て維持）」を選択肢に含める。
multiSelect: true にして、ユーザーが個別に選べるようにする。

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
