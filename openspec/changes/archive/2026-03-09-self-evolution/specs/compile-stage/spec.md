## MODIFIED Requirements

### Requirement: Self-evolution phase in Compile stage
Compile ステージは既存の Phase 5（Fitness Evolution）の後に Phase 6（Self-Evolution）を実行しなければならない（MUST）。Phase 6 は pipeline-trajectory-analysis → confidence-calibration → adaptive-pipeline-config の順に実行する。

#### Scenario: Data sufficient for self-evolution
- **WHEN** remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件以上の outcome が存在する
- **THEN** Phase 6 が trajectory analysis → calibration 提案 → ユーザー確認の順に実行される

#### Scenario: Data insufficient — skip self-evolution
- **WHEN** remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件未満のレコードしかない
- **THEN** Phase 6 をスキップし、「Self-evolution: データ不足（N/`MIN_OUTCOMES_FOR_ANALYSIS` 件）、スキップ」と表示する

#### Scenario: Dry-run mode
- **WHEN** `dry_run=True` で実行される
- **THEN** Phase 6 の分析・表示は通常通り行うが、状態ファイル（evolve-state.json, confidence-calibration.json, pipeline-proposals.jsonl）への書き込みは行わない

### Requirement: State management for self-evolution
Self-evolution の実行状態を `evolve-state.json` に記録しなければならない（SHALL）。

#### Scenario: Calibration timestamp recorded
- **WHEN** self-evolution Phase 6 が正常に完了した
- **THEN** `evolve-state.json` の `last_calibration_timestamp` が現在時刻で更新される

#### Scenario: Calibration history preserved
- **WHEN** 新しいキャリブレーション結果が生成された
- **THEN** `evolve-state.json` の `calibration_history` に結果が追記され、既存の履歴は保持される
