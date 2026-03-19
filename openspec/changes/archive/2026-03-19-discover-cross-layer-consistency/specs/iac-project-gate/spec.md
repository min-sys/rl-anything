## ADDED Requirements

### Requirement: IaC プロジェクト判定関数を提供する
`detect_iac_project(project_dir: Path) -> Dict[str, Any]` を提供し SHALL する。戻り値は `{"is_iac": bool, "iac_type": str | None, "marker_path": str | None}` とする。

#### Scenario: CDK プロジェクトを判定
- **WHEN** プロジェクトルートに `cdk.json` が存在する
- **THEN** `is_iac=True`, `iac_type="cdk"`, `marker_path="cdk.json"` を返す

#### Scenario: Serverless Framework プロジェクトを判定
- **WHEN** プロジェクトルートに `serverless.yml` または `serverless.yaml` が存在する
- **THEN** `is_iac=True`, `iac_type="serverless"` を返す

#### Scenario: SAM プロジェクトを判定
- **WHEN** プロジェクトルートに `template.yaml` が存在し、ファイル内に `AWSTemplateFormatVersion` を含む
- **THEN** `is_iac=True`, `iac_type="sam"` を返す

#### Scenario: CloudFormation テンプレートを判定
- **WHEN** プロジェクトルートに `*.template.json` または `*.template.yaml` が存在し、ファイル内に `AWSTemplateFormatVersion` を含む
- **THEN** `is_iac=True`, `iac_type="cloudformation"` を返す

#### Scenario: IaC マーカーなし
- **WHEN** 上記いずれのマーカーも存在しない
- **THEN** `is_iac=False`, `iac_type=None`, `marker_path=None` を返す

#### Scenario: project_dir が存在しない
- **WHEN** `project_dir` が存在しないパスである
- **THEN** `_safe_result()` 相当の安全な戻り値 `{"is_iac": False, "iac_type": None, "marker_path": None}` を返す

#### Scenario: 複数 AWS マーカーが一致する
- **WHEN** プロジェクトルートに `cdk.json` と `serverless.yml` が両方存在する
- **THEN** 優先度順（CDK > SAM > Serverless > CloudFormation）で最初の一致を返す（`iac_type="cdk"`）

### Requirement: detection 関数の前段ゲートとして機能する
`detect_cross_layer_consistency()` は、最初に `detect_iac_project()` を呼び出し、`is_iac=False` の場合は即座に `{"applicable": False}` を返却し SHALL する。

#### Scenario: 非 IaC プロジェクトではスキャンをスキップ
- **WHEN** `detect_iac_project()` が `is_iac=False` を返す
- **THEN** ファイルスキャンを実行せず `{"applicable": False, "evidence": [], "confidence": 0.0}` を返す

#### Scenario: IaC プロジェクトではスキャンを実行
- **WHEN** `detect_iac_project()` が `is_iac=True` を返す
- **THEN** 環境変数参照・AWS SDK 使用のスキャンを実行する
