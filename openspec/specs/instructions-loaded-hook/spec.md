## ADDED Requirements

### Requirement: InstructionsLoaded イベントを hooks.json に登録する
hooks.json に `InstructionsLoaded` イベントエントリを追加し、`instructions_loaded.py` を実行する（SHALL）。

#### Scenario: CLAUDE.md がロードされた時に hook が発火する
- **WHEN** Claude Code が CLAUDE.md または `.claude/rules/*.md` をコンテキストに読み込む
- **THEN** `instructions_loaded.py` が実行される

### Requirement: InstructionsLoaded イベントを sessions.jsonl に記録する
`instructions_loaded.py` は InstructionsLoaded イベントを `sessions.jsonl` に `type: "instructions_loaded"` として記録する（SHALL）。
セッション内で複数回発火した場合、最初の 1 回のみ記録する（SHALL）。

#### Scenario: 初回ロードが記録される
- **WHEN** セッション内で初めて InstructionsLoaded が発火する
- **THEN** sessions.jsonl に `type: "instructions_loaded"` のレコードが追記される

#### Scenario: 2回目以降はスキップされる
- **WHEN** 同一セッション内で既に InstructionsLoaded が記録されている
- **THEN** sessions.jsonl への追記は行われない

### Requirement: 重複検出にセッション固有の一時ファイルを使用する
重複検出は `{DATA_DIR}/tmp/{INSTRUCTIONS_LOADED_FLAG_PREFIX}{session_id}` ファイルの存在チェックで行う（SHALL）。
定数 `INSTRUCTIONS_LOADED_FLAG_PREFIX` と `STALE_FLAG_TTL_HOURS` は `common.py` に定義する（SHALL）。
session_summary.py（Stop hook）でこのファイルをクリーンアップする（SHALL）。

#### Scenario: フラグファイルによる dedup
- **WHEN** InstructionsLoaded 発火時にフラグファイルが存在しない
- **THEN** フラグファイルを作成し、sessions.jsonl に記録する

#### Scenario: フラグファイルが既に存在する場合
- **WHEN** InstructionsLoaded 発火時にフラグファイルが既に存在する
- **THEN** 何もせずに終了する

### Requirement: stale flag file の自動除去
instructions_loaded.py は起動時にフラグファイルの mtime を確認し、`STALE_FLAG_TTL_HOURS` 以上古ければ削除してから処理を継続する（SHALL）。
これによりクラッシュ時に Stop hook が呼ばれず残存した flag file を自動回復する。

#### Scenario: stale flag file が除去される
- **WHEN** フラグファイルが存在し、mtime が `STALE_FLAG_TTL_HOURS`（24h）以上古い
- **THEN** フラグファイルを削除し、新規として記録処理を行う

#### Scenario: fresh flag file はスキップされる
- **WHEN** フラグファイルが存在し、mtime が `STALE_FLAG_TTL_HOURS` 未満
- **THEN** 何もせずに終了する（通常の dedup 動作）

### Requirement: エラー時のサイレント失敗
instructions_loaded.py で例外が発生した場合、stderr にログ出力し、セッションをブロックせずに終了する（SHALL）。
既存 hook パターン（observe.py, subagent_observe.py）に準拠する。

#### Scenario: JSON パースエラー
- **WHEN** stdin の JSON パースに失敗する
- **THEN** stderr にエラーメッセージを出力し、正常終了する（exit code 0）

#### Scenario: ファイルI/Oエラー
- **WHEN** sessions.jsonl への書き込みやフラグファイル操作で IOError が発生する
- **THEN** stderr にエラーメッセージを出力し、正常終了する（exit code 0）
