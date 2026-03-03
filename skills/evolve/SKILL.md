---
name: evolve
description: |
  Run the full autonomous evolution pipeline: Observe → Discover → Optimize → Prune → Report.
  Designed for daily execution to continuously improve skills and rules.
  Trigger: evolve, 自律進化, evolution pipeline, 日次実行, daily run, パイプライン実行
disable-model-invocation: true
---

# /rl-anything:evolve — 全フェーズ統合実行

Observe データ確認 → Discover → Optimize → Prune → Report の全フェーズを
ワンコマンドで実行する。日次実行を想定（MUST）。

## Usage

```
/rl-anything:evolve              # 通常実行
/rl-anything:evolve --dry-run    # レポートのみ、変更なし
```

## 前提

セクション 1-6 のコンポーネント（Observe hooks, テレメトリ, Feedback, Audit, Prune, Discover）が全て利用可能であること。

## 実行手順

### Step 1: データ十分性チェック

```bash
python3 <PLUGIN_DIR>/skills/evolve/scripts/evolve.py --project-dir "$(pwd)" --dry-run
```

- 前回 evolve 実行以降のセッション数が3未満、または10観測未満の場合:
  - 「データ不足のためスキップ推奨」メッセージを表示（MUST）
  - AskUserQuestion で実行/スキップを選択させる

### Step 2: Fitness 関数チェック

evolve.py の出力に含まれる `fitness` フェーズを確認する。

- `has_fitness: false` の場合:
  - AskUserQuestion ツールで以下を質問する（MUST — テキスト表示だけで済ませてはならない）:
    - question: 「プロジェクト固有の評価関数が未生成です。生成しますか？」
    - options: 「生成する（generate-fitness --ask）」「スキップ（組み込み default で続行）」
  - ユーザーが「生成する」を選んだ場合: `/rl-anything:generate-fitness --ask` を実行してから Step 3 に進む（MUST）
  - ユーザーが「スキップ」を選んだ場合: 組み込み評価関数（default）で続行
- `has_fitness: true` の場合: 利用可能な fitness 関数名を表示して次へ

### Step 3: Discover フェーズ

パターン検出結果を表示。候補があれば生成を提案。

### Step 4: Optimize フェーズ（オプション）

既存スキルの改善を `/rl-anything:optimize` で実行。
Step 2 で生成した fitness 関数がある場合は `--fitness {name}` を付与。

**外部インストールスキルは除外（MUST）。** `classify_artifact_origin()` が `"plugin"` を返すスキル
（openspec-*, claude-reflect-* 等）は最適化対象外。
ユーザーが自作したスキル（custom / global）のみが対象。

### Step 5: Prune フェーズ

淘汰候補をスキルの出自別に3セクションで表示する（MUST）:

#### Custom Skills（淘汰候補）
カスタムスキルのうち、ゼロ呼び出しのものをアーカイブ候補として表示。
承認されたもののみアーカイブ。

#### Plugin Skills（レポートのみ）
プラグイン由来で未使用のスキルを表示。アーカイブはせず情報提供のみ。
「未使用。`claude plugin uninstall` を検討？」と案内する。

#### Global Skills（既存ロジック維持）
Usage Registry の cross-PJ 使用状況を確認し、既存の `safe_global_check` で処理。

### Step 6: Fitness Evolution — 評価関数の改善チェック

evolve.py の出力に含まれる `fitness_evolution` フェーズを確認する。

- `status: "insufficient_data"` の場合:
  - 「データ不足: N/30件」と表示
  - optimize で accept/reject を蓄積する旨を案内
- `status: "ready"` の場合:
  - score-acceptance 相関を表示（相関 < 0.50 なら警告）
  - 頻出 rejection_reason があれば新軸追加を提案
  - 提案がある場合、AskUserQuestion で承認を求める（MUST）
  - 承認されたもののみ fitness 関数に反映

### Step 7: Report フェーズ

Audit レポートを表示。全体の進捗サマリを出力。

### べき等性

連続実行時、前回以降の新規データのみを対象に処理する（MUST）。
重複した提案を行ってはならない（MUST NOT）。

## allowed-tools

Read, Bash, AskUserQuestion, Write, Glob, Grep

## Tags

evolve, orchestrator, pipeline
