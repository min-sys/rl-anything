## ADDED Requirements

### Requirement: 複数カテゴリの evidence 表示

検出関数が複数カテゴリ（DB操作・メッセージキュー・外部API）のパターンを検出した場合、`evidence` はプレーンなファイルパスリストを維持しなければならない（MUST）。既存の `VRC_EVIDENCE` 契約（`List[str]` 型のファイルパスリスト）を破壊してはならない（MUST NOT）。

カテゴリ情報は `detection_result` の別フィールド `detected_categories: List[str]` として返さなければならない（MUST）。値は `"db"`, `"mq"`, `"api"` のいずれか。

#### Scenario: evidence はプレーンパスリスト
- **WHEN** DB操作とメッセージキューの両方が検出される
- **THEN** `evidence` は `["path/to/db_file.py", "path/to/mq_file.py"]` のようなプレーンパスリストでなければならない（MUST）
- **AND** `detected_categories` に `["db", "mq"]` が含まれなければならない（MUST）

#### Scenario: remediation.py の rationale テンプレートとの互換性
- **WHEN** `len(evidence)` で件数を取得する
- **THEN** 正しい整数が返らなければならない（MUST）。カテゴリプレフィクス付き文字列を含んではならない（MUST NOT）

### Requirement: 言語別テンプレート切り替え

`get_rule_template()` は `side-effect-verification` エントリに対し、Python プロジェクトと TypeScript プロジェクトで同一のテンプレートを返さなければならない（MUST）。副作用チェックは言語非依存の原則であるため。

#### Scenario: Python プロジェクト
- **WHEN** Python 主体のプロジェクトで `get_rule_template()` を呼び出す
- **THEN** 副作用チェックルールテンプレートを返さなければならない（MUST）

#### Scenario: TypeScript プロジェクト
- **WHEN** TypeScript 主体のプロジェクトで `get_rule_template()` を呼び出す
- **THEN** Python と同一の副作用チェックルールテンプレートを返さなければならない（MUST）
