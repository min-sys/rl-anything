## MODIFIED Requirements

### Requirement: VERIFICATION_CATALOG にクロスレイヤー整合性エントリを含む
VERIFICATION_CATALOG リストに `cross-layer-consistency` エントリを追加し SHALL する。エントリは以下のフィールドを持つ:
- `id`: `"cross-layer-consistency"`
- `type`: `"rule"`
- `description`: コード↔IaC 間の整合性（環境変数・IAM 権限）を確認するルール
- `rule_template`: クロスレイヤー整合性確認のルールテンプレート文字列
- `rule_filename`: `"verify-cross-layer.md"`
- `detection_fn`: `"detect_cross_layer_consistency"`
- `applicability`: `"conditional"`
- `content_patterns`: `["cross-layer", "IaC", "環境変数", "IAM", "cdk", "aws"]`（参考情報。実装上は `_CONTENT_KEYWORDS_MAP` に登録するキーワードリストが使用される）

#### Scenario: カタログにエントリが存在する
- **WHEN** VERIFICATION_CATALOG を参照する
- **THEN** `id="cross-layer-consistency"` のエントリが含まれ、`applicability="conditional"` である

#### Scenario: detect_verification_needs で IaC プロジェクトに適用
- **WHEN** IaC プロジェクトで `detect_verification_needs()` を呼び出す
- **AND** cross-layer-consistency のルールが未インストール
- **THEN** 結果に `cross-layer-consistency` エントリが含まれ、`detection_result` に evidence が含まれる

#### Scenario: 非 IaC プロジェクトでは適用しない
- **WHEN** IaC マーカーのないプロジェクトで `detect_verification_needs()` を呼び出す
- **THEN** 結果に `cross-layer-consistency` エントリが含まれない

### Requirement: ルールテンプレートが整合性確認を指示する
`rule_template` は、コード変更時に IaC 定義（環境変数設定・IAM 権限）との整合性を確認する指示を含み SHALL する。

#### Scenario: ルールテンプレートの内容
- **WHEN** `cross-layer-consistency` エントリの `rule_template` を参照する
- **THEN** 「環境変数」「IAM 権限」「IaC 定義」への言及を含み、確認すべき観点が明記されている
