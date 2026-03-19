## Why

コードとインフラ定義（IaC）間の整合性ミスは「コード変更 → 実行時エラー / silent failure」として繰り返し発生するが、テストではモックで通ってしまい検出できない。discover の RECOMMENDED_ARTIFACTS / verification_catalog に「クロスレイヤー整合性チェック」カテゴリを追加し、IaC プロジェクトでのみ自動検出・ルール提案を行う。Related: #32

## What Changes

- **verification_catalog に cross-layer-consistency エントリ追加**: `os.environ.get()` 参照と IaC 定義の突合、`boto3.client()` 使用と IAM 権限定義の突合を検出する条件付き検証パターン
- **プロジェクト適用条件（applicability gate）の導入**: `cdk.json`/`serverless.yml`/`template.yaml`(SAM)/`*.template.json`(CFn) 等の AWS マーカー存在チェックで AWS プロジェクトかを判定し、該当時のみ検出を有効化
- **既存の issue_schema `make_verification_rule_issue` factory を再利用**: discover → evolve → remediation のデータフロー統合（新 factory 不要）
- **discover の run_discover に cross-layer 検出ステップ追加**: verification_needs と同様のフローで統合

## Capabilities

### New Capabilities
- `cross-layer-detection`: コード↔IaC 間の整合性ギャップ（環境変数未定義・IAM権限不足）をファイルスキャンで検出するロジック
- `iac-project-gate`: IaC プロジェクト判定ゲート（ファイル存在チェックベース）

### Modified Capabilities
- `verification-catalog`: cross-layer-consistency エントリの追加と applicability gate の拡張

## Impact

- **変更対象**: `scripts/lib/verification_catalog.py`, `skills/discover/scripts/discover.py`
- **テスト**: `scripts/tests/test_verification_catalog.py` に cross-layer 検出テスト追加
- **依存**: なし（既存の verification_catalog フレームワーク上に構築）
- **互換性**: 既存動作に影響なし（IaC ファイルが存在しないプロジェクトでは何も検出されない）
