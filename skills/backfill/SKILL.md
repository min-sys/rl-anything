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

### Step 2: 分析レポート出力

```bash
python3 <PLUGIN_DIR>/skills/backfill/scripts/analyze.py
```

マークダウン形式の分析レポートをユーザーに表示する（MUST）。
レポート内容: ワークフロー一貫性分析、ステップバリエーション、介入分析（workflow 内 vs ad-hoc）、Discover/Prune 比較データ。

### Step 3: --force による再実行（オプション）

ユーザーが `--force` を指定した場合のみ、Step 1 のコマンドに `--force` を追加する。
既存のバックフィルレコード（usage.jsonl, workflows.jsonl の source:"backfill"）を削除して全セッションを再処理する。

## allowed-tools

Read, Bash, Glob, Grep

## Tags

backfill, observe, usage, history, analyze, workflow
