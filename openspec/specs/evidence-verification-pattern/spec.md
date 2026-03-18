## ADDED Requirements

### Requirement: evidence-before-claims パターンを verification_catalog に追加する
VERIFICATION_CATALOG に「証拠提示義務」パターンを MUST 追加する。完了主張の前に検証コマンドの実行結果を提示することを求めるルール。

#### Scenario: プロジェクトに evidence-before-claims ルールが未導入の場合
- **WHEN** discover がプロジェクトを分析し、証拠提示義務に関するルール/スキルが検出されない
- **THEN** evidence-before-claims パターンを verification_needs として出力する

#### Scenario: 既に類似ルールが存在する場合
- **WHEN** プロジェクトに verify-before-claim, verification-before-completion 等のキーワードを含むルール/スキルが存在する
- **THEN** content-aware install check で「導入済み」と判定し、重複提案しない

### Requirement: evidence-before-claims の検出ロジック
verification_catalog の detect 関数は既存パターン `fn(project_dir: Path) -> Dict[str, Any]` に準拠し、project_dir からテレメトリを内部取得して「証拠なき完了主張」パターンを MUST 検出する。

#### Scenario: corrections に「テスト実行して」「確認して」等の修正がある場合
- **WHEN** `detect_evidence_verification(project_dir: Path)` が呼び出され、project_dir の corrections に EVIDENCE_MIN_PATTERNS (3) 件以上の証拠要求パターンがある
- **THEN** evidence-before-claims パターンの検出スコアを返す

### Requirement: issue_schema 経由で remediation に統合する
evidence-before-claims の検出結果は既存の verification_rule_candidate として issue_schema 経由で remediation に MUST 流れる。

#### Scenario: remediation が evidence-before-claims を処理する場合
- **WHEN** remediation が verification_rule_candidate タイプの issue を受信
- **THEN** 既存の fix_verification_rule ハンドラで「証拠提示義務」ルールの生成を提案する
