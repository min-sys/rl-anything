## ADDED Requirements

### Requirement: Mitigation trend data persistence
evolve 実行時、tool_usage_patterns の検出件数を evolve-state.json に記録し、次回実行時に前回値と比較できるようにする。システムは `tool_usage_snapshot: { timestamp, builtin_replaceable, sleep_patterns, bash_ratio }` フィールドを SHALL 記録する。

#### Scenario: Initial evolve run (no prior snapshot)
- **WHEN** evolve-state.json に tool_usage_snapshot が存在しない状態で evolve を実行する
- **THEN** 現在の検出件数を tool_usage_snapshot に記録し、レポートでは「前回データなし」と表示する

#### Scenario: Subsequent evolve run with prior snapshot
- **WHEN** evolve-state.json に前回の tool_usage_snapshot が存在する状態で evolve を実行する
- **THEN** 前回値との差分（件数差・増減率%）を算出し、レポートの推奨アクションセクションに表示する

#### Scenario: Trend decrease
- **WHEN** 前回比で件数が減少している場合
- **THEN** 「↓ N件減少 (-X%)」形式で改善傾向を表示する

#### Scenario: Trend increase
- **WHEN** 前回比で件数が増加している場合
- **THEN** 「↑ N件増加 (+X%)」形式で悪化傾向を表示する

#### Scenario: No change
- **WHEN** 前回比で件数に変化がない場合
- **THEN** 「→ 変化なし」形式で表示する

#### Scenario: Ratio trend display for bash_ratio
- **WHEN** bash_ratio の前回値と今回値が異なる場合
- **THEN** 「45.4% → 38.2% (↓7.2pp)」形式でパーセントポイント差を表示する
- **WHEN** bash_ratio の前回値と今回値が同一の場合
- **THEN** 「38.2% → 変化なし」形式で表示する

### Normative Statements

- The system SHALL record `tool_usage_snapshot` in evolve-state.json on every evolve execution.
- The system SHALL compute trend deltas when a prior snapshot exists.
- The system SHALL display count-based trends using `↓ N件減少 (-X%)` / `↑ N件増加 (+X%)` / `→ 変化なし` format.
- The system SHALL display ratio-based trends using percentage point difference (`pp`) format.
- The system MUST NOT fail if evolve-state.json is missing or corrupted; it SHALL treat this as an initial run.
