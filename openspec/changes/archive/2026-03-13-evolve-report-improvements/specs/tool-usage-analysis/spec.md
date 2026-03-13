## MODIFIED Requirements

### Requirement: Display BASH_RATIO_THRESHOLD in report
evolve レポートの Bash 割合表示に目標閾値を併記し、達成/未達を SHALL 明示する。

#### Scenario: Bash ratio above threshold
- **WHEN** Bash 割合が BASH_RATIO_THRESHOLD (40%) 以上の場合
- **THEN** 「Bash 割合: X% (目標: ≤40%) — 未達」形式で表示する

#### Scenario: Bash ratio below threshold
- **WHEN** Bash 割合が BASH_RATIO_THRESHOLD (40%) 未満の場合
- **THEN** 「Bash 割合: X% (目標: ≤40%) — 達成」形式で表示する

### Requirement: Threshold constants accessible for report
tool_usage_analyzer.py の閾値定数（BASH_RATIO_THRESHOLD, BUILTIN_THRESHOLD, SLEEP_THRESHOLD）をレポート生成時に参照可能に SHALL する。

#### Scenario: Import threshold constants
- **WHEN** evolve レポート生成コードが tool_usage_analyzer の閾値を参照する
- **THEN** モジュールから定数をインポートして使用できる（既に export 済みの場合は変更不要）

### Normative Statements

- The system SHALL display the target threshold alongside the actual Bash ratio.
- The system SHALL indicate achievement status using 「達成」/「未達」 labels.
- The system SHALL use the existing `BASH_RATIO_THRESHOLD` constant; it MUST NOT hardcode the threshold value in report templates.
- BUILTIN_THRESHOLD and SLEEP_THRESHOLD SHALL also be displayed when relevant metrics are shown.
