## 1. async-claude-executor 基盤

- [ ] 1.1 `model_cascade.py` に `_async_execute()` メソッド追加（`asyncio.create_subprocess_exec` ベース）
- [ ] 1.2 `async_run_with_tier()` メソッド追加（async カスケードエスカレーション）
- [ ] 1.3 `asyncio.Semaphore` によるグローバル同時実行数制御を追加（デフォルト4、`OPTIMIZE_MAX_CONCURRENT` 環境変数対応）
- [ ] 1.4 既存の `run_with_tier()` を同期ラッパーとして維持（内部で `asyncio.run()` 呼び出し）
- [ ] 1.5 `test_model_cascade.py` に async テスト追加 + 既存同期テストの動作確認

## 2. optimize.py の async 化

- [ ] 2.1 `_evaluate_fitness()` を async 化（`claude -p` 呼び出しを `_async_execute` 経由に）
- [ ] 2.2 `_mutate()` を async 化
- [ ] 2.3 `_execution_evaluate()` を async 化（Stage 1 / Stage 2 の subprocess を async に）
- [ ] 2.4 `_crossover()` を async 化
- [ ] 2.5 エントリポイント（`main` / `run`）は同期のまま、内部で `asyncio.run()` を1回だけ呼ぶ構成に

## 3. セクション並行最適化

- [ ] 3.1 `_optimize_sections()` でセクション変異を `asyncio.gather` で並行実行
- [ ] 3.2 `_evaluate_population()` で候補評価を `asyncio.gather` で並行実行
- [ ] 3.3 部分失敗時のエラーハンドリング（`return_exceptions=True` + 失敗セクションスキップ）

## 4. parallel.py の asyncio 統一

- [ ] 4.1 `_run_batch()` を `asyncio.gather` ベースに置き換え
- [ ] 4.2 `run_parallel()` を async 版に変更 + 同期ラッパー `run_parallel_sync()` 追加
- [ ] 4.3 既存テストの動作確認（`ParallelPlan` / `OptimizeResult` インターフェース維持）

## 5. テスト・検証

- [ ] 5.1 全既存テスト (`pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v`) のパス確認
- [ ] 5.2 14セクションスキルでの実行時間ベンチマーク（before/after 計測）
- [ ] 5.3 `OPTIMIZE_MAX_CONCURRENT=1` での逐次実行が既存動作と同等であることを確認
