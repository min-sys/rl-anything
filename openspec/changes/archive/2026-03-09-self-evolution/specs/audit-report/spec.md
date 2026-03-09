## ADDED Requirements

### Requirement: Pipeline Health section in audit report
audit レポートに `--pipeline-health` オプションが指定された場合、"## Pipeline Health" セクションをレポートに追加しなければならない（MUST）。`--pipeline-health` 未指定時はセクションを表示してはならない（MUST NOT）。

#### Scenario: --pipeline-health with sufficient data
- **WHEN** `audit --pipeline-health` を実行し、remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件以上の outcome がある
- **THEN** "## Pipeline Health" セクションが表示され、issue_type 別の precision、approval_rate、false_positive_count が表形式で表示される

#### Scenario: --pipeline-health with insufficient data
- **WHEN** `audit --pipeline-health` を実行し、remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件未満の outcome しかない
- **THEN** "## Pipeline Health" セクションに「データ不足（N/`MIN_OUTCOMES_FOR_ANALYSIS` 件）。evolve を繰り返し実行してデータを蓄積してください。」と表示する

#### Scenario: --pipeline-health with degraded type
- **WHEN** ある issue_type の approval_rate が `APPROVAL_RATE_DEGRADED_THRESHOLD`（デフォルト: 0.7）未満
- **THEN** 該当行に "DEGRADED" マーカーを表示し、`/rl-anything:evolve` での self-evolution を推奨する

#### Scenario: Section ordering with other score sections
- **WHEN** `audit --pipeline-health --coherence-score --telemetry-score` を実行する
- **THEN** Pipeline Health セクションは既存スコアセクション（Environment Fitness → Constitutional → Coherence → Telemetry）の後に表示される

### Requirement: Pipeline Health は LLM コール不要
Pipeline Health セクションの生成は remediation-outcomes.jsonl の集計のみで行い、LLM 呼び出しを行ってはならない（MUST NOT）。

#### Scenario: No LLM cost
- **WHEN** `audit --pipeline-health` を実行する
- **THEN** LLM API への呼び出しは発生せず、Python の集計処理のみで完了する
