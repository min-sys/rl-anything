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

### Step 2: Discover フェーズ

パターン検出結果を表示。候補があれば生成を提案。

### Step 3: Optimize フェーズ（オプション）

Discover で生成された候補、または既存スキルの改善を `/rl-anything:optimize` で実行。

### Step 4: Prune フェーズ

淘汰候補を表示。承認されたもののみアーカイブ。

### Step 5: Report フェーズ

Audit レポートを表示。全体の進捗サマリを出力。

### べき等性

連続実行時、前回以降の新規データのみを対象に処理する（MUST）。
重複した提案を行ってはならない（MUST NOT）。

## allowed-tools

Read, Bash, AskUserQuestion, Write, Glob, Grep

## Tags

evolve, orchestrator, pipeline
