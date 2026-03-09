## MODIFIED Requirements

### Requirement: Remediation outcome recording
修正結果を `~/.claude/rl-anything/remediation-outcomes.jsonl` に記録する（SHALL）。dry-run 時は記録しない。outcome レコードには修正の詳細メタデータ（fix 結果、検証結果、所要時間）を含めなければならない（MUST）。

#### Scenario: Successful fix recorded with extended metadata
- **WHEN** auto_fixable な修正が成功した
- **THEN** `{timestamp, issue_type, category, confidence_score, impact_scope, action, result: "success", user_decision: "approved", rationale, fix_detail: {changed_files: list, lines_removed: int, lines_added: int}, verify_result: {resolved: bool}, duration_ms: int}` が remediation-outcomes.jsonl に追記される

#### Scenario: Failed fix recorded
- **WHEN** auto_fixable な修正が実行されたが VERIFY_DISPATCH で resolved=False となった
- **THEN** `{..., result: "fix_failed", fix_detail: {...}, verify_result: {resolved: false, remaining: str}}` が記録される

#### Scenario: Skipped fix recorded
- **WHEN** ユーザーが修正をスキップした
- **THEN** `{..., result: "skipped", user_decision: "skipped"}` が記録される

#### Scenario: Rejected fix recorded
- **WHEN** ユーザーが proposable な修正案を却下した
- **THEN** `{..., result: "rejected", user_decision: "rejected"}` が記録される

#### Scenario: Dry-run does not record
- **WHEN** evolve が `dry_run=True` で実行されている
- **THEN** remediation-outcomes.jsonl への書き込みは行われない

### Requirement: Confidence-based issue classification
remediation engine は audit の検出結果を受け取り、各問題に対して `confidence_score`（修正の確実性 0.0〜1.0）と `impact_scope`（file / project / global）を算出し、閾値ベースで `auto_fixable`、`proposable`、`manual_required` の3カテゴリに動的分類する（SHALL）。confidence_score の算出時、confidence-calibration.json が存在しアクティブな場合は、キャリブレーション済みの値で静的値を上書きしなければならない（MUST）。

#### Scenario: Calibrated confidence applied
- **WHEN** confidence-calibration.json に `{stale_ref: {calibrated: 0.80, status: "active"}}` が存在する
- **THEN** stale_ref の confidence_score は 0.95（静的値）ではなく 0.80（キャリブレーション値）が使用される

#### Scenario: Calibration file missing or inactive
- **WHEN** confidence-calibration.json が存在しない、または status が "active" でない
- **THEN** 既存の静的 confidence_score がそのまま使用される

#### Scenario: High-confidence file-scoped issue classified as auto_fixable
- **WHEN** audit が通常の MEMORY ファイル内の陳腐化参照を検出した
- **THEN** confidence_score ≥ 0.9 かつ impact_scope = file と判定され、`auto_fixable` カテゴリに分類される

#### Scenario: Same type escalated by impact scope
- **WHEN** 同一 issue_type だが impact_scope が "global" の問題が検出された
- **THEN** confidence_score が高くても `proposable` 以上に分類される（auto_fixable にならない）

#### Scenario: Minor line limit violation downgraded
- **WHEN** Rules ファイルの行数が上限を `MINOR_LINE_EXCESS`（デフォルト: 2）行以内で超過している
- **THEN** confidence_score が低く算出され、`proposable` に分類される

#### Scenario: Major line limit violation escalated
- **WHEN** Rules ファイルの行数が上限を大幅に超過している
- **THEN** confidence_score が高く算出され、`auto_fixable` に分類される

#### Scenario: No issues detected
- **WHEN** audit の検出結果に問題が含まれない
- **THEN** 分類処理をスキップし、空の分類結果を返す

#### Scenario: Dry-run mode
- **WHEN** evolve が `dry_run=True` で実行されている
- **THEN** 分類と提案の表示は行うが、修正の実行と outcome の記録は行わない
