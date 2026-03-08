# telemetry-score Specification

## Purpose
テレメトリデータから環境の実効性を3軸（Utilization/Effectiveness/Implicit Reward）で測定する fitness 関数。LLM コストゼロで hooks が蓄積した JSONL データを集計し、行動実績ベースのスコア（0.0〜1.0）を算出する。

## Requirements
### Requirement: Utilization score calculation
`score_utilization()` SHALL calculate Skill utilization based on usage.jsonl data for the specified time window.

- 全 Skill 数の定義: `project_dir/.claude/skills/` 配下の `SKILL.md` を持つディレクトリ数（coherence.py の `_find_project_artifacts()` パターンと一致）
- Skill 利用率: 過去 N 日で 1回以上 invoke された Skill 数 / 全 Skill 数
- Skill 利用偏り: Shannon entropy を Skill 数で正規化（entropy / log2(skill_count)）して [0, 1] に収める
- 最終スコア: (利用率 * 0.5 + 正規化 entropy * 0.5)

#### Scenario: All skills used evenly
- **WHEN** 全 Skill が過去30日で均等に利用されている
- **THEN** score_utilization() は 0.9 以上を返す

#### Scenario: Half skills unused
- **WHEN** 全 Skill の半分が過去30日で未利用
- **THEN** score_utilization() は 0.5 前後を返す

#### Scenario: No usage data
- **WHEN** usage.jsonl が空またはデータ期間が不足
- **THEN** score_utilization() は 0.0 を返す

### Requirement: Effectiveness score calculation
`score_effectiveness()` SHALL calculate environment effectiveness by comparing recent vs previous time windows.

- エラー減少率: (前期間エラー数 - 直近エラー数) / max(前期間エラー数, 1) をクリップ [-1, 1] → [0, 1] にスケール
- 修正頻度トレンド: corrections.jsonl の直近 vs 前期間の件数比較（同上のスケール）
- ワークフロー完走率: workflows.jsonl の非自明ワークフロー比率（step_count >= 2 のワークフロー / 全ワークフロー）。単一ステップのみのワークフローは自明とみなし完走に含めない。代替として、ワークフロー中にエラーが発生していないことを errors.jsonl とのタイムスタンプ突合で検証してもよい
- 最終スコア: (エラー減少率 * 0.35 + 修正トレンド * 0.35 + 完走率 * 0.30)

#### Scenario: Errors decreasing
- **WHEN** 直近30日のエラー数が前30日より50%減少
- **THEN** score_effectiveness() のエラー減少率要素は 0.75 を返す

#### Scenario: No previous data for comparison
- **WHEN** 前期間のデータが存在しない（全てが直近期間のみ）
- **THEN** score_effectiveness() はトレンド比較を 0.5（中立）として算出する

#### Scenario: Workflows completing successfully
- **WHEN** workflows.jsonl の80%が完走している
- **THEN** score_effectiveness() のワークフロー完走率要素は 0.8 を返す

### Requirement: Implicit reward score calculation
`score_implicit_reward()` SHALL estimate per-skill contribution from behavioral signals.

- Skill 成功率推定: invoke 後60秒以内に corrections が発生しない = success。MUST: `corrections.session_id == usage.session_id` の一致を要件とする（クロスセッションの誤検出を防止）
- 繰り返し利用スコア: 複数回利用された Skill の割合
- 最終スコア: (成功率平均 * 0.6 + 繰り返し利用率 * 0.4)

#### Scenario: Skills with high success rate
- **WHEN** 全 Skill invoke の90%で60秒以内の correction が発生していない
- **THEN** score_implicit_reward() の成功率要素は 0.9 を返す

#### Scenario: No corrections data
- **WHEN** corrections.jsonl が空
- **THEN** score_implicit_reward() は全 invoke を success とみなし成功率 1.0 で算出する

### Requirement: Telemetry score integration
`compute_telemetry_score()` SHALL integrate the three sub-scores with configurable weights.

- デフォルト重み: utilization=0.30, effectiveness=0.40, implicit_reward=0.30
- 結果に data_sufficiency フラグを含める（30セッション以上 AND 7日以上のデータ幅）
- WEIGHTS/THRESHOLDS は coherence.py と同じパターンでモジュールレベル定数として定義

#### Scenario: Sufficient data
- **WHEN** sessions.jsonl に30件以上かつ7日以上のデータ幅がある
- **THEN** compute_telemetry_score() は data_sufficiency=True を含む dict を返す

#### Scenario: Insufficient data
- **WHEN** sessions.jsonl が20件しかない
- **THEN** compute_telemetry_score() は data_sufficiency=False を含む dict を返し、overall スコアも算出する（ただし信頼性が低い旨を示す）

### Requirement: Time-range query support
`telemetry_query.py` の query_usage() / query_errors() / query_sessions() は `since` / `until` パラメータ（ISO 8601 文字列）をサポートしなければならない（MUST）。

- DuckDB 使用時: WHERE timestamp >= since AND timestamp < until を SQL に追加
- Python フォールバック時: timestamp フィールドの文字列比較でフィルタ
- 既存の呼び出し元に影響なし（パラメータはオプション、デフォルト None）

#### Scenario: Query with time range
- **WHEN** query_usage(since="2026-02-01", until="2026-03-01") を呼び出す
- **THEN** 2026-02 のレコードのみが返される

#### Scenario: Query without time range (backward compatible)
- **WHEN** query_usage() を既存と同じ引数で呼び出す
- **THEN** 全レコードが返される（既存動作と同一）

### Requirement: argparse CLI interface
`telemetry.py` は argparse ベースの CLI（`python3 telemetry.py <project_dir> [--days N]`）を提供しなければならない（MUST）。`--fitness` フラグでは使用しない（既存 fitness インターフェースは stdin にスキル内容を受け取るため、プロジェクトパスが必要な telemetry.py とは互換性がない）。audit 統合のみが公開インターフェースとなる。

#### Scenario: CLI invocation
- **WHEN** `python3 telemetry.py /path/to/project --days 30` を実行する
- **THEN** stdout に JSON 形式のスコア結果（overall, sub-scores, data_sufficiency）が出力される
