## Purpose

verification_catalog における副作用検出機能。共有リソースアクセスパターン（DB操作・メッセージキュー・外部API）を走査し、副作用チェックルールの必要性を判定する。

## Requirements

### Requirement: 副作用検出カタログエントリ

VERIFICATION_CATALOG に `side-effect-verification` エントリを追加しなければならない（MUST）。エントリは `id: "side-effect-verification"`, `type: "rule"`, `applicability: "conditional"`, `detection_fn: "detect_side_effect_verification"`, `rule_filename: "verify-side-effects.md"` を持たなければならない（MUST）。

#### Scenario: カタログエントリが存在する
- **WHEN** `VERIFICATION_CATALOG` をインポートする
- **THEN** `id` が `"side-effect-verification"` のエントリが含まれなければならない（MUST）

#### Scenario: ルールテンプレートが3行以内
- **WHEN** `side-effect-verification` エントリの `rule_template` を取得する
- **THEN** テンプレートは3行以内でなければならない（MUST）

### Requirement: 副作用検出関数

`detect_side_effect_verification(project_dir: Path) -> Dict[str, Any]` は、プロジェクト内の共有リソースアクセスパターンを走査し、副作用チェックルールの必要性を判定しなければならない（MUST）。

検出対象は以下の3カテゴリ（MUST）:
1. **DB操作**: `session.add`, `cursor.execute`, `.commit()`, `INSERT INTO`, `UPDATE`, `DELETE FROM`, `prisma.*.create`, `.save()`, `knex.*insert`
2. **メッセージキュー/イベント**: `sqs.send_message`, `publish(`, `channel.basic_publish`, `sendMessage`, `channel.sendToQueue`
3. **外部API/Webhook**: `requests.post`, `httpx.post`, `aiohttp.*post`, `fetch(`, `axios.post`, `webhook`

テストファイル（`test_*.py`, `*_test.py`, `*.test.ts`, `*.test.tsx`, `__tests__/` 配下）は走査対象から除外しなければならない（MUST）。除外は `detect_side_effect_verification` 内で `_iter_source_files()` の結果をフィルタして行う。

返り値は既存の検出関数インターフェース（`applicable`, `evidence`, `confidence`, `llm_escalation_prompt`）に準拠しなければならない（MUST）。加えて `detected_categories: List[str]` を返さなければならない（MUST）。

#### Scenario: DB操作パターンが検出される
- **WHEN** プロジェクト内に `session.add` や `.commit()` を含む非テストファイルが SIDE_EFFECT_MIN_PATTERNS 箇所以上ある
- **THEN** `applicable` が `True` でなければならない（MUST）。`evidence` に検出ファイルパスをプレーンリストで含まなければならない（MUST）。`detected_categories` に `"db"` を含まなければならない（MUST）

#### Scenario: メッセージキューパターンが検出される
- **WHEN** プロジェクト内に `sqs.send_message` や `publish(` を含む非テストファイルが SIDE_EFFECT_MIN_PATTERNS 箇所以上ある
- **THEN** `applicable` が `True` でなければならない（MUST）

#### Scenario: 外部APIパターンが検出される
- **WHEN** プロジェクト内に `requests.post` や `axios.post` を含む非テストファイルが SIDE_EFFECT_MIN_PATTERNS 箇所以上ある
- **THEN** `applicable` が `True` でなければならない（MUST）

#### Scenario: 閾値未満の場合
- **WHEN** 全カテゴリの合計検出箇所が SIDE_EFFECT_MIN_PATTERNS 未満
- **THEN** `applicable` が `False` でなければならない（MUST）

#### Scenario: テストファイルが除外される
- **WHEN** 副作用パターンが `test_api.py` や `__tests__/handler.test.ts` にのみ存在する
- **THEN** `applicable` が `False` でなければならない（MUST）。テストファイルは evidence に含まれてはならない（MUST NOT）

#### Scenario: confidence の上限
- **WHEN** regex のみで検出した場合
- **THEN** `confidence` は 0.7 を超えてはならない（MUST NOT）

#### Scenario: タイムアウト
- **WHEN** 検出関数の実行が DETECTION_TIMEOUT_SECONDS を超過する
- **THEN** `{"applicable": False, "evidence": [], "confidence": 0.0}` を返さなければならない（MUST）

#### Scenario: llm_escalation_prompt の生成
- **WHEN** `applicable` が `True` の場合
- **THEN** `llm_escalation_prompt` に検出カテゴリと evidence を含むプロンプトを設定しなければならない（MUST）

### Requirement: 閾値定数

副作用検出の閾値は `SIDE_EFFECT_MIN_PATTERNS = 3` として `verification_catalog.py` に定義しなければならない（MUST）。既存の `DATA_CONTRACT_MIN_PATTERNS` を流用してはならない（MUST NOT）。

#### Scenario: 閾値定数が独立して存在する
- **WHEN** `verification_catalog.py` をインポートする
- **THEN** `SIDE_EFFECT_MIN_PATTERNS` が `3` として定義されていなければならない（MUST）
- **AND** `DATA_CONTRACT_MIN_PATTERNS` とは別の定数でなければならない（MUST）

### Requirement: _DETECTION_FN_DISPATCH への登録

`detect_side_effect_verification` は `_DETECTION_FN_DISPATCH` に登録しなければならない（MUST）。

#### Scenario: ディスパッチから呼び出し可能
- **WHEN** `_run_detection_fn("detect_side_effect_verification", project_dir)` を呼び出す
- **THEN** `detect_side_effect_verification` が実行されなければならない（MUST）

### Requirement: content-aware インストール済みチェック

`check_verification_installed()` は、`rule_filename` のファイル存在チェックに加え、対象プロジェクトの `.claude/rules/` ディレクトリ内の既存ファイルに副作用関連キーワード（「副作用」「side effect」）が含まれるかも確認しなければならない（MUST）。

これにより、既存の `verification.md` に副作用チェックの行が含まれている場合、重複するルールファイル `verify-side-effects.md` の提案を抑制する。

#### Scenario: rule_filename のファイルが存在する
- **WHEN** `.claude/rules/verify-side-effects.md` が存在する
- **THEN** `True` を返さなければならない（MUST）

#### Scenario: 別ファイルに副作用キーワードが含まれる
- **WHEN** `.claude/rules/verify-side-effects.md` は存在しないが、`.claude/rules/verification.md` に「副作用」の文字列が含まれる
- **THEN** `True` を返さなければならない（MUST）

#### Scenario: どちらも該当しない
- **WHEN** `.claude/rules/verify-side-effects.md` が存在せず、他のルールファイルにも副作用キーワードが含まれない
- **THEN** `False` を返さなければならない（MUST）
