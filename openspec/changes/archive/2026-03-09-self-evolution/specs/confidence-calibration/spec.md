## ADDED Requirements

### Requirement: Confidence score calibration from historical data
`pipeline_reflector` モジュールは remediation-outcomes.jsonl の実績データから、issue_type 別の最適 confidence_score を EWA（指数加重平均）方式で算出しなければならない（MUST）。

#### Scenario: Calibration with sufficient data
- **WHEN** ある issue_type の outcome レコードが `MIN_OUTCOMES_PER_TYPE`（デフォルト: 10）件以上存在する
- **THEN** EWA 方式で calibrated_confidence を算出する。計算式: `calibrated = α * observed_approval_rate + (1 - α) * current_confidence` where `α = min(sample_size / CALIBRATION_SAMPLE_THRESHOLD, MAX_CALIBRATION_ALPHA)`（デフォルト: `CALIBRATION_SAMPLE_THRESHOLD`=30, `MAX_CALIBRATION_ALPHA`=0.7）

#### Scenario: Calibration with insufficient data
- **WHEN** ある issue_type の outcome レコードが `MIN_OUTCOMES_PER_TYPE`（デフォルト: 10）件未満
- **THEN** 該当 issue_type のキャリブレーションをスキップし、現在の静的値を維持する

#### Scenario: Dry-run mode
- **WHEN** `dry_run=True` で実行される
- **THEN** キャリブレーション結果の算出と表示は通常通り行うが、confidence-calibration.json への書き込みは行わない

### Requirement: Calibration result storage
キャリブレーション結果を `~/.claude/rl-anything/confidence-calibration.json` に保存しなければならない（SHALL）。

#### Scenario: Calibration file format
- **WHEN** キャリブレーションが完了した
- **THEN** `{last_calibrated: timestamp, calibrations: {issue_type: {current: float, calibrated: float, alpha: float, sample_size: int, approval_rate: float}}}` 形式で保存される

#### Scenario: Calibration applied after approval
- **WHEN** ユーザーがキャリブレーション結果を承認した
- **THEN** `remediation.py` の `compute_confidence_score()` が confidence-calibration.json の calibrated 値を参照して上書きする

### Requirement: Calibration does not bypass human approval
キャリブレーション結果の適用は AskUserQuestion で承認を得なければならない（MUST）。自動適用してはならない（MUST NOT）。

#### Scenario: User approves calibration
- **WHEN** キャリブレーション結果が提示され、ユーザーが「適用」を選択した
- **THEN** confidence-calibration.json の status が "active" に更新され、次回 evolve から反映される

#### Scenario: User rejects calibration
- **WHEN** ユーザーが「却下」を選択した
- **THEN** confidence-calibration.json の status が "rejected" のままで、現在の静的値が維持される
