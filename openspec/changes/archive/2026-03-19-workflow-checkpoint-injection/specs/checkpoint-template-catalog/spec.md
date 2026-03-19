## ADDED Requirements

### Requirement: Checkpoint template catalog structure
`CHECKPOINT_CATALOG` は各チェックポイントテンプレートを以下のフィールドで定義する（SHALL）:

| フィールド | 型 | 説明 |
|---|---|---|
| id | str | 一意識別子（kebab-case） |
| category | str | カテゴリ（infra_deploy, data_migration, external_api, secret_rotation） |
| description | str | チェックポイントの説明 |
| detection_fn | str | テレメトリ照合用の検出関数名（`_CHECKPOINT_DETECTION_DISPATCH` で解決） |
| applicability | str or None | 適用条件の判定関数名（None=常時適用） |
| template | str | SKILL.md に注入するステップテンプレート |

#### Scenario: Catalog entry lookup
- **WHEN** `get_checkpoint_template("infra_deploy")` を呼び出す
- **THEN** infra_deploy カテゴリのテンプレートエントリが返される

#### Scenario: Unknown category
- **WHEN** `get_checkpoint_template("unknown_category")` を呼び出す
- **THEN** None が返される

### Requirement: Infrastructure deploy checkpoint
`infra_deploy` チェックポイントは IaC プロジェクトゲート（`detect_iac_project()`）を適用条件とする（SHALL）。

検出関数: `detect_infra_deploy_gap()` — corrections/errors から deploy/デプロイ/prod/本番/hotswap/cdk/cloudformation/stack キーワードを照合

テンプレート: 「インフラ変更が含まれる場合、対象環境（dev/staging/prod）への反映状態を確認する」ステップ。

#### Scenario: IaC project with deploy corrections
- **WHEN** プロジェクトに cdk.json が存在し、corrections に「デプロイ忘れ」パターンがある
- **THEN** infra_deploy チェックポイントが適用対象として検出される

#### Scenario: Non-IaC project
- **WHEN** プロジェクトに IaC 関連ファイルが存在しない
- **THEN** infra_deploy チェックポイントは適用対象外となる

### Requirement: Data migration checkpoint
`data_migration` チェックポイントは DB/スキーマ関連ファイルの存在を適用条件とする（SHALL）。

検出関数: `detect_data_migration_gap()` — corrections/errors から migration/マイグレーション/schema/スキーマ/prisma/alembic/migrate キーワードを照合

適用条件（applicability gate）の検出パターン:
- `prisma/schema.prisma`
- `alembic/`
- `migrations/`
- `knex` （knexfile.js/ts）
- `typeorm` （ormconfig, data-source）
- `drizzle` （drizzle.config）

#### Scenario: Project with Prisma schema
- **WHEN** プロジェクトに `prisma/schema.prisma` が存在し、corrections にスキーマ関連の修正がある
- **THEN** data_migration チェックポイントが適用対象として検出される

#### Scenario: Project with Alembic migrations
- **WHEN** プロジェクトに `alembic/` ディレクトリが存在し、corrections にマイグレーション関連の修正がある
- **THEN** data_migration チェックポイントが適用対象として検出される

### Requirement: External API checkpoint
`external_api` チェックポイントは常時適用（applicability=None）とする（SHALL）。

検出関数: `detect_external_api_gap()` — corrections/errors から API/endpoint/webhook/外部/downstream/breaking change/互換性 キーワードを照合

#### Scenario: API change corrections detected
- **WHEN** corrections に「API 破壊的変更」関連の修正が2件以上ある
- **THEN** external_api チェックポイントが適用対象として検出される

### Requirement: Secret rotation checkpoint
`secret_rotation` チェックポイントは常時適用（applicability=None）とする（SHALL）。

検出関数: `detect_secret_rotation_gap()` — corrections/errors から secret/シークレット/credential/認証/token/API key/rotate キーワードを照合

#### Scenario: Secret-related errors detected
- **WHEN** errors.jsonl にシークレット関連のエラーが2件以上ある
- **THEN** secret_rotation チェックポイントが適用対象として検出される
