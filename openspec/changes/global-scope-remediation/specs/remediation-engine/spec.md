## MODIFIED Requirements

### Requirement: Confidence-based issue classification
remediation engine は audit の検出結果を受け取り、各問題に対して `confidence_score`（修正の確実性 0.0〜1.0）と `impact_scope`（file / project / global）を算出し、閾値ベースで `auto_fixable`、`proposable`、`manual_required` の3カテゴリに動的分類する（SHALL）。confidence_score の算出時、confidence-calibration.json が存在しアクティブな場合は、キャリブレーション済みの値で静的値を上書きしなければならない（MUST）。global scope の issue は `confidence >= PROPOSABLE_CONFIDENCE` の場合に `proposable` に昇格する（MUST）。`auto_fixable` にはならない（MUST）。

#### Scenario: Global scope + high confidence classified as proposable
- **WHEN** `tool_usage_rule_candidate` issue（scope="global", confidence=0.85）が classify_issue() に渡された
- **THEN** category = "proposable" に分類される

#### Scenario: Global scope never auto_fixable
- **WHEN** scope="global" かつ confidence=0.95 の issue が classify_issue() に渡された
- **THEN** category = "proposable" に分類される（auto_fixable にならない）

#### Scenario: Global scope + low confidence remains manual_required
- **WHEN** scope="global" かつ confidence < PROPOSABLE_CONFIDENCE の issue が classify_issue() に渡された
- **THEN** category = "manual_required" に分類される

#### Scenario: High-confidence file-scoped issue classified as auto_fixable
- **WHEN** audit が通常の MEMORY ファイル内の陳腐化参照を検出した
- **THEN** confidence_score ≥ 0.9 かつ impact_scope = file と判定され、`auto_fixable` カテゴリに分類される（従来動作維持）

#### Scenario: Calibrated confidence applied
- **WHEN** confidence-calibration.json に `{stale_ref: {calibrated: 0.80, status: "active"}}` が存在する
- **THEN** stale_ref の confidence_score は 0.95（静的値）ではなく 0.80（キャリブレーション値）が使用される

#### Scenario: No issues detected
- **WHEN** audit の検出結果に問題が含まれない
- **THEN** 分類処理をスキップし、空の分類結果を返す

### Requirement: remediation は新レイヤーの issue type を分類できる
`classify_issue()` は、tool_usage 由来の issue type（`tool_usage_rule_candidate`, `tool_usage_hook_candidate`）に対して適切な `confidence_score` を算出しなければならない（MUST）。

#### Scenario: tool_usage_rule_candidate の confidence_score
- **WHEN** `tool_usage_rule_candidate` issue が分類される
- **THEN** `confidence_score` は 0.80〜0.90 の範囲で算出される（パターンマッチの確度は高いが global 影響のため慎重に）

#### Scenario: tool_usage_hook_candidate の confidence_score
- **WHEN** `tool_usage_hook_candidate` issue が分類される
- **THEN** `confidence_score` は 0.70〜0.80 の範囲で算出される（hook テンプレートの汎用性にバリエーションがあるため）
