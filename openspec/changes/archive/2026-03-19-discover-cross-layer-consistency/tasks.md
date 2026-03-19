## 1. IaC プロジェクト判定ゲート

- [x] 1.1 `detect_iac_project()` のテストを `scripts/tests/test_verification_catalog.py` に追加（CDK/Serverless/SAM/CloudFormation/非IaC の 5 パターン + project_dir不在・複数マーカー優先度の 2 パターン）
- [x] 1.2 `detect_iac_project(project_dir: Path) -> Dict` を `scripts/lib/verification_catalog.py` に実装（マーカーファイル/ディレクトリ存在チェック）
- [x] 1.3 テスト実行・全パス確認

## 2. クロスレイヤー検出ロジック

- [x] 2.1 `MIN_CROSS_LAYER_PATTERNS = 3` 定数を `verification_catalog.py` に定義
- [x] 2.2 `detect_cross_layer_consistency()` のテストを追加（env_var 検出・aws_service 検出・テストファイル除外・閾値未満・非IaCスキップ・detected_categories・エラーハンドリング の 7 パターン）
- [x] 2.3 環境変数参照パターン（Python: `os.environ.get/os.environ[]/os.getenv`、TS: `process.env.`）の正規表現定数を定義
- [x] 2.4 AWS SDK パターン（`boto3.client/resource`、`new *Client()`）の正規表現定数を定義
- [x] 2.5 `detect_cross_layer_consistency(project_dir: Path) -> Dict` を実装（IaC ゲート → ファイルスキャン → evidence 構築 → detected_categories → confidence 算出 → llm_escalation_prompt 生成）
- [x] 2.6 テスト実行・全パス確認

## 3. verification_catalog 統合

- [x] 3.1 `_CROSS_LAYER_RULE_TEMPLATE` ルールテンプレート文字列を定義
- [x] 3.2 VERIFICATION_CATALOG に `cross-layer-consistency` エントリを追加。`_CONTENT_KEYWORDS_MAP` に `"cross-layer-consistency"` キーとキーワードリストを追加。`_DETECTION_FN_DISPATCH` に `detect_cross_layer_consistency` を登録
- [x] 3.3 `detect_verification_needs()` で cross-layer エントリが正しく処理されるテストを追加
- [x] 3.4 テスト実行・全パス確認

## 4. 結合テスト・動作確認

- [x] 4.1 既存テスト全件パス確認（`python3 -m pytest scripts/tests/test_verification_catalog.py -v`）
- [x] 4.2 IaC プロジェクト（CDK）での手動動作確認（discover 実行で cross-layer が検出されること）
- [x] 4.3 discover 経由の結合テスト: `run_discover()` → `verification_needs` に cross-layer エントリが含まれることを確認

## 5. Refine: AWS スコープ絞り込み

- [x] 5.1 `detect_iac_project()` から Terraform マーカー判定（`terraform/` ディレクトリ、`*.tf` ファイル）を削除
- [x] 5.2 `detect_iac_project()` から `infra/` 汎用 IaC ディレクトリ判定を削除
- [x] 5.3 `detect_iac_project()` に複数マーカー優先度ロジックを追加（CDK > SAM > Serverless > CloudFormation）
- [x] 5.4 テストから Terraform/infra テストケースを削除、複数マーカー優先度テストを追加
- [x] 5.5 VERIFICATION_CATALOG の `content_patterns` から `"terraform"` を `"aws"` に変更
- [ ] 5.6 テスト実行・全パス確認
