---
name: backfill
description: |
  Setup command: Backfill session transcripts to extract Skill/Agent tool calls and workflow structures.
  Run once during initial setup or after significant session accumulation. Not part of the daily evolve pipeline.
  Writes to usage.jsonl and workflows.jsonl.
  Trigger: backfill, バックフィル, session history, セッション履歴, 分析
disable-model-invocation: true
---

# /rl-anything:backfill — セッション履歴のバックフィル＋分析

既存の Claude Code セッショントランスクリプトから Skill/Agent ツール呼び出しとワークフロー構造を抽出し、
usage.jsonl / workflows.jsonl にバックフィルした上で分析レポートを出力する。

## Usage

```
/rl-anything:backfill                        # バックフィル＋分析
/rl-anything:backfill --force                # 既存バックフィルを削除して再実行＋分析
```

## 実行手順

### Step 1: バックフィル実行

```bash
python3 <PLUGIN_DIR>/skills/backfill/scripts/backfill.py --project-dir "$(pwd)"
```

結果の JSON サマリを表示する（MUST）。
出力される JSONL ファイル:
- `usage.jsonl` — Skill/Agent ツール呼び出しレコード（parent_skill/workflow_id 付き）
- `workflows.jsonl` — ワークフロー単位のシーケンスレコード（Skill → Agent の構造）
- `sessions.jsonl` — セッション単位のメタデータ（全ツール名+順序、ツール種別カウント、セッション長、エラー数、ユーザー意図分類）

### Step 2: Intent 再分類（Claude Code ネイティブ LLM）

キーワード分類で "other" に残ったプロンプトを Claude Code セッション内の LLM で再分類する。

#### Step 2a: "other" プロンプトを抽出

```bash
python3 <PLUGIN_DIR>/skills/backfill/scripts/reclassify.py extract --project "$(basename $(pwd))" --include-reclassified
```

出力 JSON の `total_other_prompts` を確認する。0 件の場合は Step 3 に進む。

#### Step 2b: 各プロンプトを分類

抽出された各プロンプトを以下のカテゴリに分類する:

- `spec-review`: 仕様レビュー、要件確認
- `code-review`: コードレビュー、変更確認
- `git-ops`: git 操作（commit, push, merge 等）
- `deploy`: デプロイ、リリース
- `debug`: デバッグ、バグ修正、エラー調査
- `test`: テスト実行、検証
- `code-exploration`: コード探索、ファイル確認
- `research`: 調査、ベストプラクティス
- `implementation`: 実装、機能追加
- `config`: 設定、構成
- `conversation`: 会話的応答（挨拶、確認、指示）
- `skill-invocation`: スキル/コマンド呼び出し
- `other`: 上記に該当しない場合のみ

分類結果を JSON ファイルに書き出す（MUST）:

```json
{"reclassified": [{"session_id": "...", "intent_index": N, "category": "..."}]}
```

#### Step 2c: 結果を書き戻す

```bash
python3 <PLUGIN_DIR>/skills/backfill/scripts/reclassify.py apply --input <reclassified.json>
```

結果サマリ（updated_sessions, updated_intents, invalid_categories）を表示する（MUST）。

### Step 3: 分析レポート出力

```bash
python3 <PLUGIN_DIR>/skills/backfill/scripts/analyze.py --project "$(basename $(pwd))"
```

マークダウン形式の分析レポートをユーザーに表示する（MUST）。
レポート内容: ワークフロー一貫性分析、ステップバリエーション、介入分析（workflow 内 vs ad-hoc）、Discover/Prune 比較データ。

レポート表示後、次のステップとして `/rl-anything:evolve --dry-run` を推奨する（MUST）。
evolve は discover → prune → optimize を包含するパイプラインであり、個別の discover/prune/optimize を案内してはならない（NOT）。

### Step 4: --force による再実行（オプション）

ユーザーが `--force` を指定した場合のみ、Step 1 のコマンドに `--force` を追加する。
既存のバックフィルレコード（usage.jsonl, workflows.jsonl の source:"backfill"）を削除して全セッションを再処理する。

## allowed-tools

Read, Bash, Glob, Grep

## Tags

backfill, observe, usage, history, analyze, workflow
