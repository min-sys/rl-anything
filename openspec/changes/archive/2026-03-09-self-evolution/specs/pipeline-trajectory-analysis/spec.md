## ADDED Requirements

### Requirement: Trajectory analysis from remediation outcomes
`pipeline_reflector` モジュールは `remediation-outcomes.jsonl` を読み込み、パイプラインの弱点を分析しなければならない（MUST）。分析結果は issue_type 別の precision（正解率）、approval_rate（承認率）、false_positive_rate を含む。

#### Scenario: Sufficient outcomes for analysis
- **WHEN** remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件以上の outcome レコードが存在する
- **THEN** issue_type 別の precision、approval_rate、false_positive_rate を算出し、構造化データとして返す

#### Scenario: Insufficient outcomes
- **WHEN** remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件未満のレコードしかない
- **THEN** 「データ不足（N/`MIN_OUTCOMES_FOR_ANALYSIS` 件）」としてスキップし、空の分析結果を返す

#### Scenario: Missing outcomes file
- **WHEN** remediation-outcomes.jsonl が存在しない
- **THEN** 空の分析結果を返す（エラーにしない）

#### Scenario: Dry-run mode
- **WHEN** `dry_run=True` で実行される
- **THEN** 分析結果の算出と表示は通常通り行うが、状態ファイル（evolve-state.json 等）への書き込みは行わない

### Requirement: False positive detection
auto_fixable に分類されたが user_decision が "rejected" または "skipped" の outcome を false positive として検出しなければならない（MUST）。

#### Scenario: High-confidence rejection detected
- **WHEN** confidence_score >= 0.9 かつ user_decision == "rejected" の outcome が存在する
- **THEN** 該当 issue_type の false_positive_rate に反映され、診断レポートに「{issue_type}: confidence 0.95 で提案したが reject された（N 件）」と記載される

#### Scenario: Proposable rejection pattern
- **WHEN** 同一 issue_type の proposable カテゴリで rejection が `SYSTEMATIC_REJECTION_THRESHOLD`（デフォルト: 3）件以上連続する
- **THEN** 該当 issue_type を「systematic rejection」として診断レポートにフラグする

### Requirement: Natural language diagnosis generation
分析結果をもとに、パイプラインの弱点と改善ポイントを自然言語で診断しなければならない（SHALL）。

#### Scenario: False positive dominant type
- **WHEN** ある issue_type の false_positive_rate が `FALSE_POSITIVE_RATE_THRESHOLD`（デフォルト: 0.3）以上
- **THEN** 「{issue_type} の confidence_score が過大評価されています。実績 approval_rate: {rate}。confidence の引き下げを推奨します。」のような診断テキストを生成する

#### Scenario: All types healthy
- **WHEN** 全 issue_type の approval_rate が `APPROVAL_RATE_HEALTHY_THRESHOLD`（デフォルト: 0.8）以上
- **THEN** 「パイプラインは健全です。全 issue_type で承認率 80% 以上を維持しています。」のような診断テキストを生成する
