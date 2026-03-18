## ADDED Requirements

### Requirement: StopFailure イベントを hooks.json に登録する
hooks.json に `StopFailure` イベントエントリを追加し、`stop_failure.py` を実行する（SHALL）。

#### Scenario: API エラーでターンが終了した時に hook が発火する
- **WHEN** Claude Code が rate limit、認証失敗等の API エラーでターンを終了する
- **THEN** `stop_failure.py` が実行される

### Requirement: StopFailure イベントを errors.jsonl に記録する
`stop_failure.py` は StopFailure イベントを `errors.jsonl` に `type: "api_error"` として記録する（SHALL）。
event payload から `error_type` と `error_message` を抽出して記録する（SHALL）。

#### Scenario: rate limit エラーが記録される
- **WHEN** StopFailure event の `error_type` が "rate_limit" である
- **THEN** errors.jsonl に `type: "api_error"`, `error_type: "rate_limit"` のレコードが追記される

#### Scenario: 認証失敗エラーが記録される
- **WHEN** StopFailure event の `error_type` が "auth_failure" である
- **THEN** errors.jsonl に `type: "api_error"`, `error_type: "auth_failure"` のレコードが追記される

#### Scenario: error_type が未設定の場合
- **WHEN** StopFailure event に `error_type` フィールドがない
- **THEN** errors.jsonl の `error_type` は "unknown" となる

### Requirement: worktree 情報を付与する
worktree セッションの場合、StopFailure レコードにも `worktree` フィールドを付与する（SHALL）。
`extract_worktree_info()` を使用し、`name` と `branch` のみを記録する（SHALL）。

#### Scenario: worktree セッションで API エラーが発生
- **WHEN** StopFailure event に `worktree` オブジェクトがある
- **THEN** errors.jsonl レコードに `worktree` フィールドが dict として含まれる

### Requirement: エラー時のサイレント失敗
stop_failure.py で例外が発生した場合、stderr にログ出力し、セッションをブロックせずに終了する（SHALL）。
