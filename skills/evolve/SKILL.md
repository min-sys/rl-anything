---
name: evolve
description: |
  Run the full autonomous evolution pipeline: Observe → Discover → Enrich → Optimize → Reorganize → Prune(+Merge) → Fitness Evolution → Report.
  Designed for daily execution to continuously improve skills and rules.
  Trigger: evolve, 自律進化, evolution pipeline, 日次実行, daily run, パイプライン実行
disable-model-invocation: true
---

# /rl-anything:evolve — 全フェーズ統合実行

Observe データ確認 → Discover → Enrich → Optimize → Reorganize → Prune(+Merge) → Fitness Evolution → Report の全フェーズをワンコマンドで実行する。日次実行を想定（MUST）。

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

### Step 3.5: Enrich フェーズ

evolve.py の出力に含まれる `enrich` フェーズ結果を確認する。
enrich.py は Discover の出力パターン（error/rejection/behavior）を既存スキルと Jaccard 係数で照合し、JSON を出力する（型A パターン: LLM 呼び出しなし）。

- `skipped_reason: "no_patterns_available"` の場合:
  - 「照合対象パターンなし — Enrich スキップ」と表示し、次のステップへ
- `enrichments` が存在する場合（最大3件）:
  - 各 enrichment について、マッチしたパターンとスキルの組を表示
  - 各ペアに対して、Claude が改善提案（diff 形式）を生成し、ユーザーに対話的に提示する（MUST）
  - AskUserQuestion で「適用する」「スキップ」を選択させる（MUST）
  - ユーザーが承認した場合のみ、スキルファイルに変更を適用する
- `unmatched_patterns` がある場合:
  - 「既存スキルに関連なし → Discover の新規候補として処理」と表示

### Step 4: Optimize フェーズ（オプション）

既存スキルの改善を `/rl-anything:optimize` で実行。
Step 2 で生成した fitness 関数がある場合は `--fitness {name}` を付与。

**外部インストールスキルは除外（MUST）。** `classify_artifact_origin()` が `"plugin"` を返すスキル
（openspec-*, claude-reflect-* 等）は最適化対象外。
ユーザーが自作したスキル（custom / global）のみが対象。

### Step 4.5: Reorganize フェーズ

evolve.py の出力に含まれる `reorganize` フェーズ結果を確認する。
reorganize.py は TF-IDF + 階層クラスタリングでスキル群を分析し、JSON を出力する。

- `skipped: true` の場合:
  - 理由（`insufficient_skills` / `scipy_not_available`）を表示
  - `scipy_not_available` の場合: 「`pip install scipy scikit-learn` でインストールしてください」と案内
- `skipped: false` の場合:
  - クラスタ一覧を表示（各クラスタのスキル名とキーワード）
  - `merge_groups` があれば「統合候補グループ」として表示（情報提供のみ、Merge で処理）
  - `split_candidates` があれば「分割候補」として表示し、分割を提案

### Step 5: Prune フェーズ（+Merge）

淘汰候補をスキルの出自別に3セクションで表示する（MUST）:

#### Custom Skills（淘汰候補）
カスタムスキルのうち、ゼロ呼び出しのものをアーカイブ候補として表示。
承認されたもののみアーカイブ。

#### Plugin Skills（レポートのみ）
プラグイン由来で未使用のスキルを表示。アーカイブはせず情報提供のみ。
「未使用。`claude plugin uninstall` を検討？」と案内する。

#### Global Skills（既存ロジック維持）
Usage Registry の cross-PJ 使用状況を確認し、既存の `safe_global_check` で処理。

#### Merge サブステップ

evolve.py の出力に含まれる `prune.merge_result` を確認する。
prune.py の `merge_duplicates()` は `reorganize.merge_groups` と `duplicate_candidates` の和集合（重複排除済み）から統合候補を JSON で出力する（型A パターン: LLM 呼び出しなし）。

- `merge_proposals` の各エントリについて:
  - `status: "skipped_pinned"` / `"skipped_plugin"` → スキップ理由を表示
  - `status: "proposed"` → Claude が primary と secondary の SKILL.md を読み込み、統合版を生成してユーザーに提示する（MUST）
    - AskUserQuestion で「承認（統合を適用）」「却下（変更なし）」を選択させる（MUST）
    - 承認された場合: 統合版を primary の SKILL.md に上書きし、secondary を `archive_file()` でアーカイブ
    - 却下された場合: 当該ペアを merge suppression に登録して次回以降の提案を抑制する。以下のコマンドを実行する（MUST）:
      ```bash
      python3 -c "
      import sys; sys.path.insert(0, '<PLUGIN_DIR>/skills/discover/scripts')
      from discover import add_merge_suppression
      add_merge_suppression('<primary_skill_name>', '<secondary_skill_name>')
      "
      ```

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

### Step 6.5: Reflect フェーズ

evolve.py の出力に含まれる `reflect` フェーズ結果を確認する。

- `pending_count >= 5` または前回 reflect から 7日超経過 → AskUserQuestion で `/rl-anything:reflect` の実行を提案する（MUST）
  - question: 「未処理の修正フィードバックが {N} 件あります（最終 reflect: {date}）。/reflect を実行しますか？」
  - options: 「実行する」「スキップ」
- `0 < pending_count < 5` かつ前回 reflect から 7日以内 → Report に「未処理修正 {N} 件あり」と表示のみ
- `pending_count == 0` → スキップ

### Step 7: Report フェーズ

Audit レポートを表示。全体の進捗サマリを出力。

レポートには以下のセクションが含まれる:
- **Usage (last 30 days)**: PJ 固有スキルのみのメインランキング（プラグインスキルは除外）
- **Plugin usage**: プラグイン別の総使用回数サマリ（例: `openspec(340) / rl-anything(30)`）
- **OpenSpec Workflow Analytics**: openspec プラグインが検出された場合、ファネル（propose→archive の完走率）、フェーズ別効率、品質トレンド、最適化候補を表示

### べき等性

連続実行時、前回以降の新規データのみを対象に処理する（MUST）。
重複した提案を行ってはならない（MUST NOT）。

## allowed-tools

Read, Bash, AskUserQuestion, Write, Glob, Grep

## Tags

evolve, orchestrator, pipeline
