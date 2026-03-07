## ADDED Requirements

### Requirement: セクション単位の並行変異
独立したセクションの変異処理を `asyncio.gather` で並行実行する。

#### Scenario: 複数セクションの同時変異
- **WHEN** budget_mpo パイプラインで N 個のセクションが変異対象として選択される
- **THEN** N 個の変異を `asyncio.gather` で並行実行し、すべての完了を待つ

#### Scenario: 部分失敗時の継続
- **WHEN** N 個中の一部のセクション変異が失敗する
- **THEN** 失敗したセクションはスキップし、成功したセクションの結果のみ返す

### Requirement: セクション単位の並行評価
独立したセクションの適応度評価を並行実行する。

#### Scenario: 複数候補の同時評価
- **WHEN** 世代内で M 個の候補個体の評価が必要な場合
- **THEN** M 個の evaluate を `asyncio.gather` で並行実行する

#### Scenario: Semaphore との連携
- **WHEN** 評価の並行実行中に Semaphore の上限に達する
- **THEN** 空きが出るまで待機し、上限を超えて `claude -p` を起動しない

### Requirement: parallel.py の asyncio 統一
既存の `ThreadPoolExecutor` ベースの `run_parallel` を asyncio ベースに置き換える。

#### Scenario: references 並行最適化の async 化
- **WHEN** `run_parallel(plan, optimize_fn)` を呼び出す
- **THEN** references/ ファイルの最適化を `asyncio.gather` で並行実行する

#### Scenario: 既存インターフェースの維持
- **WHEN** `run_parallel` を同期コンテキストから呼び出す
- **THEN** 内部で `asyncio.run()` を使用し、既存の `ParallelPlan` / `OptimizeResult` 型を維持する

#### Scenario: dedup_consolidate の互換性
- **WHEN** 並行最適化の結果を `dedup_consolidate` に渡す
- **THEN** 既存と同じ重複除去ロジックが適用される
