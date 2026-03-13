---
name: evolve
description: |
  Run the full autonomous evolution pipeline: Observe → Diagnose → Compile → Housekeeping → Report.
  Designed for daily execution to continuously improve skills and rules.
  Trigger: evolve, 自律進化, evolution pipeline, 日次実行, daily run, パイプライン実行
disable-model-invocation: true
---

# /rl-anything:evolve — 全フェーズ統合実行

Observe データ確認 → Diagnose → Compile → Housekeeping → Report の全フェーズをワンコマンドで実行する。日次実行を想定（MUST）。

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

---

## Stage 1: Diagnose（パターン検出 + 問題診断）

### Step 3: Discover フェーズ（enrich 統合済み）

パターン検出結果を表示。候補があれば生成を提案。

`tool_usage_patterns` が結果に含まれる場合、以下を追加表示:
- **Built-in 代替可能**: 件数と上位パターン（例: `cat → Read: 12回`）をルール候補として提案
- **繰り返しパターン**: 上位パターンとサブカテゴリをスキル候補として提案
- **Bash 割合**: 全ツール呼び出し数と Bash の割合（例: `Bash: 31.8% (127/400)`）

discover の出力に含まれる enrich 結果（Jaccard 照合）を確認する。
discover.py は Discover のパターン（error/rejection/behavior）を既存スキルと Jaccard 係数で照合し、`matched_skills` と `unmatched_patterns` を出力する（型A パターン: LLM 呼び出しなし）。

- `matched_skills` が存在する場合（最大3件）:
  - 各マッチについて、パターンとスキルの組を表示
  - 各ペアに対して、Claude が改善提案（diff 形式）を生成し、ユーザーに対話的に提示する（MUST）
  - AskUserQuestion で「適用する」「スキップ」を選択させる（MUST）
  - ユーザーが承認した場合のみ、スキルファイルに変更を適用する
- `unmatched_patterns` がある場合:
  - 「既存スキルに関連なし → Discover の新規候補として処理」と表示

### Step 3.5: レイヤー別診断

evolve.py の出力に含まれる `layer_diagnose` フェーズ結果を確認する。
`diagnose_all_layers()` は Rules / Memory / Hooks / CLAUDE.md の4レイヤーを診断し、issue リストを返す。

各レイヤーの結果を表示:
- `rules`: `orphan_rule`（孤立ルール）、`stale_rule`（参照先不在）
- `memory`: `stale_memory`（陳腐化エントリ）、`memory_duplicate`（重複セクション）
- `hooks`: `hooks_unconfigured`（hooks 設定なし）
- `claudemd`: `claudemd_phantom_ref`（幻影参照）、`claudemd_missing_section`（セクション欠落）

issue があれば Compile ステージの remediation で対処する。

### Step 3.6: スキル自己進化適性判定

evolve.py の出力に含まれる `skill_evolve` フェーズ結果を確認する。
`skill_evolve_assessment()` は全カスタムスキルの自己進化適性を5項目（各1-3点、15点満点）でスコアリングする。

- **already_evolved**: 既に自己進化パターンが組み込まれたスキル数
- **high_suitability**: 適性高（12-15点）のスキル数 → Compile で変換を推奨
- **medium_suitability**: 適性中（8-11点）のスキル数 → ユーザー判断に委ねる
- **rejected**: アンチパターン2件以上該当で変換非推奨

適性高/中のスキルがあれば `skill_evolve_candidate` issue として Remediation パイプラインに注入され、Step 5.5 で変換提案が生成される。

### Step 3.7: Audit 問題検出

evolve.py の出力に含まれる audit の `collect_issues()` 結果を確認し、問題リストを Compile ステージに渡す。
（collect_issues() 内で layer_diagnose も統合されている）
discover の `tool_usage_rule_candidate` / `tool_usage_hook_candidate` と skill_evolve の `skill_evolve_candidate` も issue リストに統合される。

### Step 4: Reorganize フェーズ（split 検出のみ）

evolve.py の出力に含まれる `reorganize` フェーズ結果を確認する。
reorganize.py は TF-IDF + 階層クラスタリングでスキル群を分析し、JSON を出力する。

- `skipped: true` の場合:
  - 理由（`insufficient_skills` / `scipy_not_available`）を表示
  - `scipy_not_available` の場合: 「`pip install scipy scikit-learn` でインストールしてください」と案内
- `skipped: false` の場合:
  - クラスタ一覧を表示（各クラスタのスキル名とキーワード）
  - `split_candidates` があれば「分割候補」として表示し、分割を提案

---

## Stage 2: Compile（パッチ生成 + メモリルーティング）

### Step 5: Optimize フェーズ

既存スキルの改善を `/rl-anything:optimize` で実行。
Step 2 で生成した fitness 関数がある場合は `--fitness {name}` を付与。

**外部インストールスキルは除外（MUST）。** `classify_artifact_origin()` が `"plugin"` を返すスキル
（openspec-*, claude-reflect-* 等）は最適化対象外。
ユーザーが自作したスキル（custom / global）のみが対象。

### Step 5.5: Remediation フェーズ

evolve.py の出力に含まれる `remediation` フェーズ結果を確認する。
remediation.py は audit の検出結果を confidence_score / impact_scope ベースで3カテゴリに動的分類する。

- `total_issues == 0` の場合: 「問題なし — Remediation スキップ」と表示
- `dry_run` の場合: 分類結果サマリのみ表示（auto_fixable: N件, proposable: N件, manual_required: N件）

**auto_fixable** (confidence ≥ 0.9, impact_scope in (file, project)):
- rationale 付きで一括表示し、AskUserQuestion で「一括修正」「スキップ」を選択（MUST）
- 承認後: `FIX_DISPATCH[issue_type]` で対応する fix 関数を実行 → `verify_fix()` + `check_regression()` で2段階検証
- 対応 type: stale_ref, stale_rule, claudemd_phantom_ref, claudemd_missing_section, skill_evolve_candidate
- regression 検出時: `rollback_fix()` で復元し manual_required に格上げ
- 結果を `record_outcome()` で記録
- `collect_issues()` は内部で `diagnose_all_layers()` を統合済みのため、別途マージ不要

**proposable** (confidence ≥ 0.5, scope != global, confidence < 0.9 for non-file/project):
- 各修正案を rationale 付きで個別表示し、AskUserQuestion で個別承認（MUST）
- 対応 type: line_limit_violation, near_limit, orphan_rule, stale_memory, memory_duplicate
- 承認された修正のみ実行 → 検証 → 記録

**manual_required** (confidence < 0.5, or impact_scope = global):
- 問題の概要、推奨アクション、分類理由を表示のみ

**サマリ**: 「Remediation 完了: N件修正 / M件スキップ / K件ロールバック（要手動対応）」

### Step 6: Reflect フェーズ

evolve.py の出力に含まれる `reflect` フェーズ結果を確認する。

- `pending_count >= 5` または前回 reflect から 7日超経過 → AskUserQuestion で `/rl-anything:reflect` の実行を提案する（MUST）
  - question: 「未処理の修正フィードバックが {N} 件あります（最終 reflect: {date}）。/reflect を実行しますか？」
  - options: 「実行する」「スキップ」
- `0 < pending_count < 5` かつ前回 reflect から 7日以内 → Report に「未処理修正 {N} 件あり」と表示のみ
- `pending_count == 0` → スキップ

---

## Stage 3: Housekeeping（淘汰 + 評価関数改善）

### Step 7: Prune フェーズ（+Merge）

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
prune.py の `merge_duplicates()` は `duplicate_candidates` から統合候補を JSON で出力する（型A パターン: LLM 呼び出しなし）。マージ候補検出は prune に一元化済み。

- `merge_proposals` の各エントリについて:
  - `status: "skipped_pinned"` / `"skipped_plugin"` / `"skipped_suppressed"` / `"skipped_low_similarity"` → スキップ理由を表示
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
  - `status: "interactive_candidate"` → 対話的統合提案（MUST）:
    - `similarity_score` 降順で最大3件を処理する（1回の evolve あたりの上限）
    - 各ペアについて、Claude が primary と secondary の SKILL.md を読み込み、統合案の概要を提示する
    - AskUserQuestion で「承認（統合を適用）」「却下（次回以降も提案しない）」を選択させる（MUST）
    - 承認された場合: proposed と同じフロー（統合版生成 → primary の SKILL.md に上書き → secondary を `archive_file()` でアーカイブ）を適用する
    - 却下された場合: `add_merge_suppression()` で suppression 登録し、次回以降の再提案を抑制する:
      ```bash
      python3 -c "
      import sys; sys.path.insert(0, '<PLUGIN_DIR>/skills/discover/scripts')
      from discover import add_merge_suppression
      add_merge_suppression('<primary_skill_name>', '<secondary_skill_name>')
      "
      ```

### Step 7.5: Pitfall 剪定

evolve.py の出力に含まれる `pitfall_hygiene` フェーズ結果を確認する。
`pitfall_hygiene()` は自己進化済みスキルの pitfalls を回避回数ベースで卒業判定する。

- **graduation_candidates**: 卒業候補（Avoidance-count が閾値以上）→ AskUserQuestion で卒業確認（MUST）
- **cap_exceeded**: Active pitfall が10件超のスキル → 剪定レビューを推奨
- **stale_warnings**: 6ヶ月以上更新のない Active pitfall → 検証を推奨
- **cross_skill_analysis**: 根本原因カテゴリの横断集中検出 → 共通ルール化を提案

### Step 8: Fitness Evolution — 評価関数の改善チェック

evolve.py の出力に含まれる `fitness_evolution` フェーズを確認する。

- `status: "insufficient_data"` の場合:
  - 「データ不足: N/30件」と表示
  - optimize で accept/reject を蓄積する旨を案内
- `status: "bootstrap"` の場合:
  - 「簡易分析モード (N/30件)」と表示
  - 基本統計（承認率、平均スコア、スコア分布）を表示
  - 相関分析は行わない旨を注記
- `status: "ready"` の場合:
  - score-acceptance 相関を表示（相関 < 0.50 なら警告）
  - 頻出 rejection_reason があれば新軸追加を提案
  - 提案がある場合、AskUserQuestion で承認を求める（MUST）
  - 承認されたもののみ fitness 関数に反映

---

## Report

### Step 9: Report フェーズ

Audit レポートを表示。全体の進捗サマリを出力。

レポートには以下のセクションが含まれる:
- **Usage (last 30 days)**: PJ 固有スキルのみのメインランキング（プラグインスキルは除外）
- **Plugin usage**: プラグイン別の総使用回数サマリ（例: `openspec(340) / rl-anything(30)`）
- **OpenSpec Workflow Analytics**: openspec プラグインが検出された場合、ファネル（propose→archive の完走率）、フェーズ別効率、品質トレンド、最適化候補を表示

### Step 10: 推奨アクション（MUST — スキップ厳禁）

**このセクションは必ず出力すること。条件判定の結果によらず、セクション見出し「推奨アクション」を必ずレポート末尾に表示する。**
該当項目がゼロの場合は「推奨アクション: なし」と1行表示する。1件でもあれば全件列挙する。

#### 10.1: Reflect 推奨

discover 結果の `reflect_data_count` の値を確認し、**必ず**以下のいずれかを表示する:
- `reflect_data_count >= 1` → 「⚠ 未処理の修正フィードバックが {N} 件あります。`/rl-anything:reflect` で反映すると optimize の精度が向上します」
- `reflect_data_count == 0` → 「Reflect: 未処理なし」

#### 10.2: ツール使用改善

discover 結果の `installed_artifacts` と `tool_usage_patterns` を参照し、対策済み/未対策に応じて表示を切り替える。
閾値は `tool_usage_analyzer.py` のモジュール定数（`BUILTIN_THRESHOLD`, `SLEEP_THRESHOLD`, `BASH_RATIO_THRESHOLD`）を参照。

**全対策済みかつ検出ゼロ**: `installed_artifacts` の全 `recommendation_id` 付きエントリが `mitigation_metrics.mitigated=True` かつ `recent_count=0` → 「ツール使用: 全対策済み — 検出なし」と1行表示

**対策済み（検出あり）**: `mitigation_metrics.mitigated=True` かつ `recent_count > 0` → 各項目で「対策済み (hook: {name}, rule: {name}) — 直近 {N} 件検出」形式で表示。件数ベースの提案は表示しない

**未対策**: 対応する推奨の対策が未導入 → 従来通り件数と改善提案を表示:
- **Built-in 代替**: `builtin_replaceable` の合計件数 ≥ `BUILTIN_THRESHOLD` (10件) → 上位パターンと件数を表示し「プロジェクトルールまたは hook で Bash の grep/cat/find を検出・警告する仕組みの導入」を提案
- **sleep パターン**: `repeating_patterns` に `sleep` を含むエントリの合計 ≥ `SLEEP_THRESHOLD` (20件) → 「`run_in_background` + 完了通知待ちへの移行」を提案
- **Bash 割合**: `bash_calls / total_tool_calls` ≥ `BASH_RATIO_THRESHOLD` (40%) → 「Bash割合: {X}% (目標: ≤40%) — 未達」と表示。閾値未満の場合は「Bash割合: {X}% (目標: ≤40%) — 達成」と表示

全て閾値以下かつ未対策なら「ツール使用: 問題なし」と表示

**トレンド表示**: evolve-state.json に前回の `tool_usage_snapshot` がある場合、各指標に前回比トレンドを併記する:
- 件数指標: 「Built-in 代替: 15件 ↓ 5件減少 (-25%)」
- ratio 指標: 「Bash 割合: 45.4% → 38.2% (↓7.2pp)」
- 前回データなし（初回実行時）: トレンド表示なし（実績値のみ表示）

`evolve.py` の `compute_trend()` を使用してトレンドデータを算出する。

#### 10.3: 自己進化ステータス

`skill_evolve` と `pitfall_hygiene` の結果から**必ず**以下を表示する:
- 自己進化済みスキル数
- 各スキルの pitfall 統計（Active/New/Candidate/Graduated 件数）
- 卒業候補/剪定推奨があればフラグ
- 根本原因カテゴリの横断分析結果

自己進化済みスキルが0の場合は「自己進化: 対象スキルなし」と表示。

#### 10.4: Remediation サマリ

remediation 結果から**必ず**以下を表示する:
- `auto_fixable` ≥ 1 → 「通常実行で自動修正可能: {N}件」
- `manual_required` ≥ 1 → 「手動対応推奨: {N}件」（issue type の概要リスト付き）
- 両方 0 → 「Remediation: 対応不要」

### べき等性

連続実行時、前回以降の新規データのみを対象に処理する（MUST）。
重複した提案を行ってはならない（MUST NOT）。

## allowed-tools

Read, Bash, AskUserQuestion, Write, Glob, Grep

## Tags

evolve, orchestrator, pipeline
