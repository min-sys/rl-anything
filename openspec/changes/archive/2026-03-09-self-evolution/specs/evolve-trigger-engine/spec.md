## ADDED Requirements

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
