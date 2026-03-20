---
name: reflect
effort: medium
description: |
  corrections を対話的にレビューし CLAUDE.md/rules/auto-memory に反映する。
  ユーザー修正の蓄積を構造化し、適切なメモリ層にルーティングする。
  Trigger: reflect, 振り返り, corrections, 修正反映, 学習
---

# /rl-anything:reflect — corrections の対話的レビューと反映

corrections.jsonl に蓄積されたユーザー修正を分析し、
適切なメモリ層（CLAUDE.md / rules / auto-memory）にルーティングして反映する。

## Usage

```
/rl-anything:reflect                        # 対話レビュー
/rl-anything:reflect --dry-run              # 分析のみ（書き込みなし）
/rl-anything:reflect --view                 # pending 一覧表示
/rl-anything:reflect --skip-all             # 全 pending をスキップ
/rl-anything:reflect --apply-all            # 高信頼度を自動適用
/rl-anything:reflect --min-confidence 0.70  # 閾値変更
/rl-anything:reflect --skip-semantic        # セマンティック検証スキップ
```

## 実行手順

### Step 1: reflect.py を実行

```bash
python3 <PLUGIN_DIR>/skills/reflect/scripts/reflect.py [オプション]
```

### Step 2: 出力 JSON を読み取る

出力は JSON 形式。`status` フィールドで分岐する。

### Step 3: status が "empty" なら終了

「未処理の修正はありません」と表示して終了する。

### Step 4: --dry-run の場合

分析結果を表示するが Edit ツールを使わず終了する（MUST NOT edit）。
各 correction のルーティング提案・重複状態・信頼度を一覧表示する。

### Step 5: --apply-all の場合

corrections の `apply: true` のものを確認なしで適用する:
- Edit ツールで `suggested_file` に学習内容を書き込む
- corrections.jsonl の該当レコードの `reflect_status` を "applied" に更新

`apply: false` の corrections（閾値未満）は Step 6 の対話レビューに進む。

### Step 6: 各 correction を対話レビュー

duplicate_found が true の correction は「既に記録済み」と表示し、自動スキップするか確認する。

各 correction について AskUserQuestion で以下の選択肢を提供する:
- **approve**: suggested_file に書き込み → reflect_status を "applied" に更新
- **edit**: ユーザーの編集内容で書き込み
- **false-positive**: 偽陽性として報告 → `false_positives.jsonl` に SHA-256 ハッシュを追記し、reflect_status を "skipped" に更新
- **skip**: reflect_status を "skipped" に更新

3件目以降は追加の選択肢を提供する:
- **skip-remaining**: 残り全件を "skipped" に更新して終了

#### 書き込み時のルール

- suggested_file が既存ファイルの場合: 末尾に追記（Edit ツール）
- suggested_file が存在しないファイルの場合: 新規作成（Write ツール）
- routing_hint が "global" の場合: global スコープのファイルにのみ書き込む
- routing_hint が "skip" の場合: 対話レビューで表示するが、自動適用はしない
- line_limit_warning がある場合: 警告メッセージを表示し、分離を提案する

### Step 7: promotion_candidates の表示

corrections レビュー完了後、promotion_candidates がある場合は別セクションとして表示する。
「auto-memory への昇格候補」として、各候補のメッセージ・出現回数・推奨トピックを一覧表示する。
昇格の実行はユーザー判断に委ねる（自動実行しない）。

### Step 7.5: memory_update_candidates の表示

promotion_candidates 表示の後、memory_update_candidates がある場合は「MEMORY 更新候補」セクションとして表示する。
各候補の correction_message、memory_file、memory_line を一覧表示する。
更新の実行はユーザー判断に委ねる（自動実行しない）。

### Step 8: 完了サマリを表示

- 処理件数（applied / skipped / remaining）
- 重複検出数
- promotion 候補数
- MEMORY 更新候補数

## allowed-tools

Read, Bash, Edit, Write, AskUserQuestion, Glob, Grep

## Tags

reflect, corrections, memory, routing, learning
