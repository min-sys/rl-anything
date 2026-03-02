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

### Step 2: 候補リストの表示

検出された候補を以下のカテゴリ別に表示:
- **Dead Glob**: rules の paths 対象がマッチしないもの
- **Zero Invocation**: 30日間使用記録がないもの
- **Global 候補**: Usage Registry で cross-PJ 使用状況を確認
- **重複候補**: audit-report の意味的類似度検出結果

### Step 3: 人間承認フロー（MUST）

AskUserQuestion ツールで各候補について承認/却下を確認する。
自動的にアーカイブを実行してはならない（MUST NOT）。

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
