# adaptive-pipeline-config Specification

## Purpose
confidence-calibration の算出結果に基づき、パイプラインパラメータの調整提案を生成する。提案は人間承認が必須であり、自動適用は禁止。

## Requirements
### Requirement: Pipeline parameter adjustment proposals
confidence-calibration の算出結果に基づき、パイプラインパラメータの調整提案を生成しなければならない（MUST）。提案は人間承認が必須であり、自動適用してはならない（MUST NOT）。

#### Scenario: Confidence delta proposal
- **WHEN** issue_type "stale_ref" の false_positive_rate が `FALSE_POSITIVE_RATE_THRESHOLD`（デフォルト: 0.3）以上
- **THEN** `{issue_type: "stale_ref", current_confidence: 0.95, proposed_confidence: 0.825, delta: -0.125, alpha: 0.5, evidence: "approval_rate=0.70, sample_size=15, α=0.5"}` 形式の調整提案を生成する

#### Scenario: Delta within control limits
- **WHEN** 算出された delta が μ ± 2σ 範囲内
- **THEN** 提案に `risk_level: "low"` を付与する

#### Scenario: Delta exceeds control limits
- **WHEN** 算出された delta が μ ± 2σ 範囲外
- **THEN** 提案に `risk_level: "high"` を付与し、「統計的に外れ値の調整幅です。慎重にレビューしてください。」の警告を追加する

#### Scenario: Dry-run mode
- **WHEN** `dry_run=True` で実行される
- **THEN** 提案の算出と表示は通常通り行うが、pipeline-proposals.jsonl への書き込みは行わない

### Requirement: Proposal persistence
生成された調整提案を `~/.claude/rl-anything/pipeline-proposals.jsonl` に記録しなければならない（SHALL）。

#### Scenario: Proposal recorded
- **WHEN** 調整提案が生成された
- **THEN** `{timestamp, issue_type, current_value, proposed_value, delta, alpha, risk_level, evidence, status: "pending"}` が pipeline-proposals.jsonl に追記される

#### Scenario: Proposal approved
- **WHEN** ユーザーが提案を承認した
- **THEN** 該当レコードの status が "approved" に更新され、remediation.py の該当パラメータが更新される

#### Scenario: Proposal rejected
- **WHEN** ユーザーが提案を却下した
- **THEN** 該当レコードの status が "rejected" に更新される

### Requirement: Regression check for parameter changes
パラメータ変更適用前に、変更後の confidence で既存 outcomes を再評価し、回帰がないか検証しなければならない（MUST）。

#### Scenario: No regression detected
- **WHEN** 提案された confidence で既存 outcomes を再分類した結果、新たな false positive が増加しない
- **THEN** 「回帰なし」として提案を続行する

#### Scenario: Regression detected
- **WHEN** 再分類の結果、別の issue_type で false positive が `REGRESSION_FP_INCREASE_THRESHOLD`（デフォルト: 0.1）以上増加する
- **THEN** 提案を `risk_level: "regression"` に格上げし、影響を受ける issue_type を明示する
