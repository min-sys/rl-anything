## Context

`/optimize` の遺伝的最適化パイプラインは `claude -p` subprocess で LLM を呼び出す。現状は `subprocess.run` による同期逐次実行で、セクション変異・評価・クロスオーバーすべてが直列。14セクションのスキルでは 1世代あたり数分〜十数分かかる。

既存の `parallel.py` は `ThreadPoolExecutor` で references/ ファイル単位の並行処理を実装済み。これをセクション粒度に拡張し、`asyncio` ベースに統一する。

制約: Claude API (anthropic SDK) は使わない。`claude -p` subprocess のまま高速化する。

## Goals / Non-Goals

**Goals:**
- セクション単位の変異・評価を並行実行し、14セクションスキルで 3-5倍の高速化を実現
- `model_cascade.py` を async 化し、並行実行の基盤とする
- 既存の同期 API を `asyncio.run` ラッパーで維持し、後方互換性を確保
- 同時実行数を制限し、Claude Code のレート制限に配慮

**Non-Goals:**
- Claude API (anthropic Python SDK) への移行
- `claude -p` 以外の LLM 呼び出し方法の導入
- optimize.py 全体の async/await 化（エントリポイントは同期のまま）

## Decisions

### D1: asyncio.create_subprocess_exec を採用

**選択**: `subprocess.run` → `asyncio.create_subprocess_exec`

**代替案**:
- `ThreadPoolExecutor` + `subprocess.run`: GIL の影響を受けない I/O bound タスクでは有効だが、asyncio の方がきめ細かい並行制御（Semaphore、タイムアウト）が可能
- `multiprocessing.Pool`: プロセス起動コストが追加で発生し、オーバーヘッドが大きい

**理由**: `claude -p` は I/O bound（API 待ち）なので asyncio が最適。Semaphore で同時実行数を制御でき、`asyncio.gather` で自然にセクション並行化できる。

### D2: Semaphore による同時実行数制御

**選択**: `asyncio.Semaphore(max_concurrent)` でグローバルに同時実行数を制限

**デフォルト**: `max_concurrent=4`（環境変数 `OPTIMIZE_MAX_CONCURRENT` で上書き可能）

**理由**: Claude Code のレート制限を超えないようにする。ユーザーの Claude Code サブスクプランによって許容並行数が異なるため、設定可能にする。

### D3: 同期ラッパーによる後方互換性

**選択**: async メソッドに対して `run_with_tier_sync()` 等の同期ラッパーを提供

**理由**: テストや既存の呼び出し元で async 非対応のコードがある。`asyncio.run()` でラップすることで段階的に移行可能にする。

### D4: parallel.py を asyncio ベースに統一

**選択**: `ThreadPoolExecutor` → `asyncio.gather` + `asyncio.Semaphore`

**理由**: model_cascade が async になるため、parallel.py も asyncio に統一した方が自然。`run_parallel` は async 版を本体、sync ラッパーを互換 API として提供。

## Risks / Trade-offs

- **[レート制限超過]** → Semaphore で同時実行数を制限。デフォルト 4、環境変数で調整可能
- **[既存テスト破壊]** → 同期ラッパー提供 + pytest-asyncio 追加で段階移行
- **[subprocess のエラーハンドリング複雑化]** → asyncio.wait_for でタイムアウト制御、既存のカスケードエスカレーションロジックを維持
- **[イベントループのネスト]** → エントリポイント（main）は同期のまま、内部で `asyncio.run()` を1回だけ呼ぶ設計。ネストを避ける
