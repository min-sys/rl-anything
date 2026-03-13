## ADDED Requirements

### Requirement: Bootstrap mode for fitness evolution
fitness evolution の MIN_DATA_COUNT 未満でも、蓄積済みデータで簡易分析を実行する bootstrap モードを提供する。システムは BOOTSTRAP_MIN 以上のデータがある場合に簡易分析を SHALL 実行する。

#### Scenario: Data count between BOOTSTRAP_MIN and MIN_DATA_COUNT
- **WHEN** accept/reject データが BOOTSTRAP_MIN (5件) 以上 MIN_DATA_COUNT (30件) 未満の場合
- **THEN** 簡易分析（基本統計: 承認率、平均スコア、スコア分布）を実行し、結果を `status: "bootstrap"` で返却する
- **THEN** 「簡易分析モード (N/30件)」とレポートに表示する

#### Scenario: Data count below BOOTSTRAP_MIN
- **WHEN** accept/reject データが BOOTSTRAP_MIN (5件) 未満の場合
- **THEN** 従来通り `status: "insufficient_data"` を返却する

#### Scenario: Data count at or above MIN_DATA_COUNT
- **WHEN** accept/reject データが MIN_DATA_COUNT (30件) 以上の場合
- **THEN** 従来の完全分析（相関分析含む）を実行する（既存動作を維持）

### Normative Statements

- The system SHALL define `BOOTSTRAP_MIN = 5` as a module-level constant in `fitness_evolution.py`.
- When data count is in range [BOOTSTRAP_MIN, MIN_DATA_COUNT), the system SHALL return `status: "bootstrap"` with basic statistics (approval_rate, mean_score, score_distribution).
- When data count is below BOOTSTRAP_MIN, the system SHALL return `status: "insufficient_data"`.
- The system MUST NOT perform correlation analysis in bootstrap mode.
- The bootstrap report MUST clearly indicate "簡易分析モード (N/30件)" to distinguish from full analysis.
