## ADDED Requirements

### Requirement: カタログモジュールの提供

`scripts/lib/verification_catalog.py` は VERIFICATION_CATALOG リストを公開しなければならない（MUST）。各エントリは以下のフィールドを持つ dict とする: `id` (str), `type` (str: "rule"), `description` (str), `rule_template` (str), `detection_fn` (Optional[str]), `applicability` (str: "always" | "conditional"), `rule_filename` (str)。`rule_filename` は catalog 内で一意でなければならない（MUST）。

#### Scenario: カタログの初期エントリ
- **WHEN** `VERIFICATION_CATALOG` をインポートする
- **THEN** `data-contract-verification` エントリが含まれなければならない（MUST）。`rule_template` は3行以内の Markdown ルールテンプレートであること

### Requirement: 検出関数のインターフェース

`detection_fn` で参照される検出関数は `detect_{id}(project_dir: Path) -> Dict[str, Any]` のシグネチャを持たなければならない（MUST）。返り値は `{"applicable": bool, "evidence": list[str], "confidence": float, "llm_escalation_prompt": Optional[str]}` とする。

- `evidence`: project_dir からの相対パスのリスト、最大10件（MUST）
- `confidence` セマンティクス: 0.0=証拠なし、0.3-0.5=弱い一致、0.5-0.7=閾値達成(regex)、0.8-1.0=強い証拠(LLM確認含む)
- `llm_escalation_prompt`: confidence 0.4-0.7 の場合に `claude --print` で再判定するためのプロンプト（SHOULD）

#### Scenario: 検出関数が適用可能と判定
- **WHEN** プロジェクト内にモジュール間 dict 変換パターンが3箇所以上ある
- **THEN** `applicable` が `True` でなければならない（MUST）。`evidence` に検出箇所のファイルパスを含まなければならない（MUST）。`confidence` は 0.0-1.0 の範囲でなければならない（MUST）

#### Scenario: 検出関数が適用不可と判定
- **WHEN** プロジェクト内にモジュール間 dict 変換パターンが2箇所以下
- **THEN** `applicable` が `False` でなければならない（MUST）

### Requirement: 検出関数のエラーハンドリング

検出関数はいかなる場合も例外を呼び出し元に伝播させてはならない（MUST NOT）。

#### Scenario: 検出関数が例外を発生
- **WHEN** 検出関数内で予期しない例外が発生する
- **THEN** `{"applicable": False, "evidence": [], "confidence": 0.0}` を返さなければならない（MUST）。stderr にエラーログを出力しなければならない（MUST）

#### Scenario: 検出関数がタイムアウト
- **WHEN** 検出関数の実行が DETECTION_TIMEOUT_SECONDS を超過する
- **THEN** 実行を中断し `{"applicable": False, "evidence": [], "confidence": 0.0}` を返さなければならない（MUST）

#### Scenario: project_dir が存在しない
- **WHEN** 指定された project_dir が存在しない
- **THEN** `{"applicable": False, "evidence": [], "confidence": 0.0}` を返さなければならない（MUST）

### Requirement: 導入済みチェック

`check_verification_installed(entry, project_dir)` は対象プロジェクトの `.claude/rules/` に `rule_filename` と同名のファイルが既に存在する場合、導入済みと判定しなければならない（MUST）。

#### Scenario: ルールが既に存在する場合
- **WHEN** `.claude/rules/verify-data-contract.md` が既に存在する
- **THEN** `installed` が `True` でなければならない（MUST）

#### Scenario: ルールが未導入の場合
- **WHEN** `.claude/rules/verify-data-contract.md` が存在しない
- **THEN** `installed` が `False` でなければならない（MUST）

### Requirement: RECOMMENDED_ARTIFACTS への動的マージ

discover の RECOMMENDED_ARTIFACTS に検証知見カタログエントリを動的マージしなければならない（MUST）。`detection_fn` フィールドを持つエントリは `detect_recommended_artifacts()` 内で検出関数を呼び出して判定しなければならない（MUST）。

#### Scenario: 適用可能な検証知見がある場合
- **WHEN** `data-contract-verification` が未導入で検出関数が `applicable: True` を返す
- **THEN** discover の結果に `verification_needs` が含まれなければならない（MUST）。当該エントリが含まれること

#### Scenario: 全て導入済みの場合
- **WHEN** 全ての検証知見が導入済み
- **THEN** `verification_needs` が空リストでなければならない（MUST）

### Requirement: evolve remediation パイプラインへの統合

evolve.py の Phase 3.5 で、discover の `verification_needs` を `verification_rule_candidate` issue に変換し、remediation パイプラインに注入しなければならない（MUST）。

#### Scenario: 検証知見が issue として注入される
- **WHEN** discover が `verification_needs` に `data-contract-verification` を含む
- **THEN** remediation の issues に `type: "verification_rule_candidate"` の issue が追加されなければならない（MUST）

#### Scenario: FIX_DISPATCH による自動修正
- **WHEN** `verification_rule_candidate` issue の修正が承認される
- **THEN** プロジェクトの `.claude/rules/{rule_filename}` に `rule_template` の内容が書き込まれなければならない（MUST）

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

### Edge Cases

#### Scenario: 空プロジェクト
- **WHEN** project_dir 内にソースファイルが存在しない
- **THEN** 全エントリで `applicable: False` を返さなければならない（MUST）

#### Scenario: テストファイルのみ
- **WHEN** project_dir 内にテストファイル（test_*.py, *_test.py, *.test.ts）のみ存在する
- **THEN** テストファイルも検出対象に含めなければならない（MUST）

#### Scenario: 全エントリ導入済み
- **WHEN** VERIFICATION_CATALOG の全エントリが導入済み
- **THEN** `verification_needs` は空リストでなければならない（MUST）
