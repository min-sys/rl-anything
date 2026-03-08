## MODIFIED Requirements

### Requirement: Audit report output
audit スキルは `--telemetry-score` オプションで Telemetry Score セクションをレポートに追加する。

既存の `--coherence-score` と同様のフォーマットで:
- 3軸スコア（Utilization / Effectiveness / Implicit Reward）を個別表示 MUST
- overall スコアを表示 MUST
- data_sufficiency が False の場合は警告メッセージを表示 MUST
- `--coherence-score` と `--telemetry-score` の両方が指定された場合、Environment Fitness（統合スコア）も表示 MUST

#### Scenario: Telemetry score display
- **WHEN** `audit --telemetry-score` を実行する
- **THEN** レポートに Telemetry Score セクション（3軸 + overall + data_sufficiency）が表示される

#### Scenario: Combined score display
- **WHEN** `audit --coherence-score --telemetry-score` を実行する
- **THEN** Coherence Score + Telemetry Score + Environment Fitness（統合スコア）が表示される

#### Scenario: Insufficient data warning
- **WHEN** `audit --telemetry-score` を実行し、data_sufficiency が False
- **THEN** 警告メッセージ「Data insufficient: N sessions (minimum 30 required)」が表示される
