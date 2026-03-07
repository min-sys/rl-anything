## ADDED Requirements

### Requirement: Async subprocess execution
`claude -p` subprocess の実行を `asyncio.create_subprocess_exec` で非同期に行う基盤を提供する。既存の `ModelCascade._execute()` を async 化し、`run_with_tier()` も async メソッドとして提供する。

#### Scenario: 単一プロンプトの async 実行
- **WHEN** `await cascade.async_execute(prompt, model)` を呼び出す
- **THEN** `asyncio.create_subprocess_exec` で `claude -p --model {model}` を起動し、stdout を返す

#### Scenario: タイムアウト制御
- **WHEN** subprocess が指定タイムアウト（デフォルト120秒）を超過する
- **THEN** プロセスを kill し `asyncio.TimeoutError` を発生させる

#### Scenario: カスケードエスカレーション
- **WHEN** Tier N のモデルが失敗する（returncode != 0 またはタイムアウト）
- **THEN** Tier N+1 のモデルで自動リトライする（Tier 3 失敗時はエラーを伝搬）

### Requirement: Semaphore による同時実行数制御
グローバル `asyncio.Semaphore` で `claude -p` の同時実行数を制限する。

#### Scenario: デフォルト同時実行数
- **WHEN** `max_concurrent` を指定せずに実行する
- **THEN** 同時実行数は 4 に制限される

#### Scenario: 環境変数による上書き
- **WHEN** 環境変数 `OPTIMIZE_MAX_CONCURRENT` が設定されている
- **THEN** その値を同時実行数の上限として使用する

#### Scenario: Semaphore による待機
- **WHEN** 同時実行中のプロセス数が `max_concurrent` に達している
- **THEN** 空きが出るまで新しいプロセスの起動を待機する

### Requirement: 同期ラッパー
async メソッドに対応する同期ラッパーを提供し、既存の呼び出し元との後方互換性を維持する。

#### Scenario: sync ラッパー経由の実行
- **WHEN** `cascade.run_with_tier(prompt, tier)` を同期コンテキストから呼び出す
- **THEN** 内部で `asyncio.run()` を使用して async メソッドを実行し、結果を返す

#### Scenario: 既存テストの互換性
- **WHEN** 既存の同期テストが `run_with_tier()` を呼び出す
- **THEN** テストは変更なしで動作する
