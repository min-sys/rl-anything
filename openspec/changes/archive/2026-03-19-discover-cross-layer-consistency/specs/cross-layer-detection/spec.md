## ADDED Requirements

### Requirement: コード内の環境変数参照を検出する
detection 関数 `detect_cross_layer_consistency()` は、プロジェクト内の非テストソースファイルをスキャンし、環境変数参照パターン（Python: `os.environ.get()` / `os.environ[]` / `os.getenv()`、TypeScript: `process.env.`）を検出し、変数名と出現ファイルを evidence として返却し SHALL する。

#### Scenario: Python プロジェクトで環境変数参照を検出
- **WHEN** プロジェクト内に `os.environ.get("DATABASE_URL")` を含むファイルが MIN_CROSS_LAYER_PATTERNS 件以上存在する
- **THEN** detection result の `applicable` が True となり、evidence に変数名・ファイルパス・カテゴリ `env_var` が含まれる

#### Scenario: TypeScript プロジェクトで環境変数参照を検出
- **WHEN** プロジェクト内に `process.env.API_KEY` を含むファイルが MIN_CROSS_LAYER_PATTERNS 件以上存在する
- **THEN** detection result の `applicable` が True となり、evidence に変数名・ファイルパス・カテゴリ `env_var` が含まれる

#### Scenario: 環境変数参照が閾値未満
- **WHEN** 環境変数参照パターンが MIN_CROSS_LAYER_PATTERNS 件未満
- **THEN** `applicable` が False となる

> **閾値適用方式**: `env_var` カテゴリと `aws_service` カテゴリの検出数を**合算**し、合計が `MIN_CROSS_LAYER_PATTERNS`（デフォルト 3）以上の場合に `applicable=True` とする。単一カテゴリのみでも閾値を超えれば検出対象となる。

### Requirement: AWS SDK 使用パターンを検出する
detection 関数は、`boto3.client()` / `boto3.resource()` / AWS SDK v3 の `new *Client()` パターンを検出し、使用サービス名を evidence に含め SHALL する。

#### Scenario: boto3 使用を検出
- **WHEN** プロジェクト内に `boto3.client("s3")` や `boto3.resource("dynamodb")` が存在する
- **THEN** evidence にサービス名（`s3`, `dynamodb`）とファイルパス、カテゴリ `aws_service` が含まれる

#### Scenario: AWS SDK v3 (TypeScript) を検出
- **WHEN** プロジェクト内に `new S3Client()` や `new DynamoDBClient()` が存在する
- **THEN** evidence にサービス名とファイルパス、カテゴリ `aws_service` が含まれる

### Requirement: テストファイルを除外する
検出対象は非テストファイルに限定する。既存の `_TEST_FILE_PATTERNS` および `_TEST_DIR_NAMES` を再利用し SHALL する。

#### Scenario: テストファイル内の参照は無視
- **WHEN** `test_handler.py` 内に `os.environ.get("X")` が存在する
- **THEN** evidence に含まれない

### Requirement: confidence は evidence 数に基づく
confidence は `0.5 + count * 0.04`（最大 0.7）とし SHALL する。既存の verification_catalog エントリと同一の算出方式を踏襲する。

#### Scenario: evidence 5件の confidence
- **WHEN** 環境変数参照 + AWS SDK 使用が合計 5 件検出される
- **THEN** confidence は `0.5 + 5 * 0.04 = 0.7` となる（上限 0.7 でクリップ）

### Requirement: detected_categories フィールドを返却する
detection result に `detected_categories: List[str]` を含め SHALL する。値は `"env_var"`, `"aws_service"` のいずれか。evidence はプレーンなファイルパスリストを維持し SHALL する。

#### Scenario: 両カテゴリ検出時
- **WHEN** 環境変数参照と AWS SDK 使用の両方が検出される
- **THEN** `detected_categories` に `["env_var", "aws_service"]` が含まれる
- **AND** evidence はプレーンパスリスト（カテゴリプレフィクスなし）

#### Scenario: 単一カテゴリ検出時
- **WHEN** 環境変数参照のみが検出される
- **THEN** `detected_categories` に `["env_var"]` のみが含まれる

### Requirement: エラーハンドリングは既存仕様に準拠する
`detect_cross_layer_consistency()` は verification-catalog spec の「検出関数のエラーハンドリング」要件（タイムアウト/例外/不在ディレクトリ）に準拠し SHALL する。`_safe_result()` を使用する。

#### Scenario: タイムアウト時
- **WHEN** 検出処理が DETECTION_TIMEOUT_SECONDS を超過する
- **THEN** `{"applicable": False, "evidence": [], "confidence": 0.0}` を返す

### Requirement: llm_escalation_prompt を生成する
detection result に `llm_escalation_prompt` を含め SHALL する。プロンプトには検出された環境変数名・AWS サービス名の一覧と「IaC 定義との突合確認」指示を含める。

#### Scenario: LLM エスカレーションプロンプト生成
- **WHEN** `applicable` が True
- **THEN** `llm_escalation_prompt` に検出された変数名/サービス名と「IaC 定義ファイルとの整合性を確認してください」の指示が含まれる
