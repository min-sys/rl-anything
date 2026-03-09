# evolve-trigger-engine Specification

## Purpose
evolve 実行条件の評価エンジン。複数トリガー条件（セッション数、経過日数）の統合判定、クールダウン管理、ユーザー設定の読み込み、トリガー発火履歴の記録を担当する。

## Requirements
### Requirement: Trigger condition evaluation
`trigger_engine` モジュールは複数のトリガー条件を統合評価し、evolve 実行を提案すべきかどうかを判定しなければならない (SHALL)。判定結果は `TriggerResult` として返却し、トリガーされた条件名と推奨アクションを含まなければならない (MUST)。

#### Scenario: Session count threshold reached
- **WHEN** 前回 evolve 実行以降のセッション数が `min_sessions`（デフォルト: 10）以上
- **THEN** `TriggerResult(triggered=True, reason="session_count", action="/rl-anything:evolve")` を返さなければならない (MUST)

#### Scenario: Days since last evolve exceeded
- **WHEN** 前回 evolve 実行から `max_days`（デフォルト: 7）日以上経過
- **THEN** `TriggerResult(triggered=True, reason="days_elapsed", action="/rl-anything:evolve")` を返さなければならない (MUST)

#### Scenario: No trigger conditions met
- **WHEN** すべてのトリガー条件が閾値未満
- **THEN** `TriggerResult(triggered=False)` を返さなければならない (MUST)

#### Scenario: Evolve state file missing
- **WHEN** `evolve-state.json` が存在しない（初回実行）
- **THEN** 前回 evolve 未実行とみなし、セッション数 ≥ 3 で `triggered=True` を返さなければならない (SHALL)

### Requirement: Cooldown management
同一トリガーの連続発火を防止するため、クールダウン期間を管理しなければならない (SHALL)。

#### Scenario: Within cooldown period
- **WHEN** 同一 reason のトリガーが `cooldown_hours`（デフォルト: 24）時間以内に発火済み
- **THEN** `TriggerResult(triggered=False, reason="cooldown")` を返さなければならない (MUST)

#### Scenario: Cooldown expired
- **WHEN** 前回の同一 reason トリガーから `cooldown_hours` 以上経過
- **THEN** 条件判定を通常通り実行しなければならない (SHALL)

### Requirement: Trigger configuration loading
`evolve-state.json` の `trigger_config` キーからユーザー設定を読み込まなければならない (SHALL)。

#### Scenario: trigger_config key exists
- **WHEN** `evolve-state.json` に `trigger_config` キーが存在し、有効な設定値を含む
- **THEN** その値でデフォルト閾値を上書きしなければならない (MUST)

#### Scenario: trigger_config key missing
- **WHEN** `evolve-state.json` に `trigger_config` キーが存在しない
- **THEN** デフォルト値で動作しなければならない (SHALL)（zero-config）

#### Scenario: Config disables all triggers
- **WHEN** `trigger_config` の `enabled` が `false`
- **THEN** すべてのトリガー評価をスキップし `TriggerResult(triggered=False)` を返さなければならない (MUST)

### Requirement: Trigger history recording
トリガー発火履歴を `evolve-state.json` の `trigger_history` フィールドに記録しなければならない (SHALL)。

#### Scenario: Trigger fired
- **WHEN** トリガーが発火した（`triggered=True`）
- **THEN** `trigger_history` に `{reason, timestamp, action}` を追記しなければならない (MUST)

#### Scenario: History pruning
- **WHEN** `trigger_history` のエントリが 100 件を超える
- **THEN** 古いエントリから削除し 100 件以内に保たなければならない (MUST)

## ADDED Requirements (self-evolution)

### Requirement: Self-evolution trigger condition
trigger_engine は false positive 蓄積に基づく self-evolution トリガー条件を評価しなければならない（SHALL）。

#### Scenario: False positive threshold reached
- **WHEN** remediation-outcomes.jsonl 内の直近 `ANALYSIS_LOOKBACK_DAYS`（デフォルト: 30）日間で、いずれかの issue_type の false_positive_rate が `FALSE_POSITIVE_RATE_THRESHOLD`（デフォルト: 0.3）以上かつサンプル数 `MIN_OUTCOMES_PER_TYPE`（デフォルト: 10）件以上
- **THEN** `TriggerResult(triggered=True, reason="self_evolution", action="/rl-anything:evolve")` を返す

#### Scenario: False positive below threshold
- **WHEN** 全 issue_type の false_positive_rate が `FALSE_POSITIVE_RATE_THRESHOLD`（デフォルト: 0.3）未満
- **THEN** self_evolution reason ではトリガーしない

#### Scenario: Cooldown for self-evolution trigger
- **WHEN** self_evolution reason のトリガーが `SELF_EVOLUTION_COOLDOWN_HOURS`（デフォルト: 72）時間以内に発火済み
- **THEN** self_evolution のトリガーは抑制される（通常クールダウンの 24h より長い `SELF_EVOLUTION_COOLDOWN_HOURS`h）

### Requirement: Approval rate degradation trigger
trigger_engine は承認率の継続的低下に基づくトリガー条件を評価しなければならない（SHALL）。

#### Scenario: Approval rate declining
- **WHEN** 直近 `DECLINE_SAMPLE_SIZE`（デフォルト: 10）件の outcome の approval_rate が、それ以前の `DECLINE_SAMPLE_SIZE` 件と比較して `APPROVAL_RATE_DECLINE_THRESHOLD`（デフォルト: 0.2）以上低下している
- **THEN** `TriggerResult(triggered=True, reason="approval_rate_decline", action="/rl-anything:evolve")` を返す

#### Scenario: Stable approval rate
- **WHEN** 承認率の変化が `APPROVAL_RATE_DECLINE_THRESHOLD`（デフォルト: 0.2）未満
- **THEN** approval_rate_decline reason ではトリガーしない
