## Why

`/optimize` の budget_mpo パイプラインで `claude -p` subprocess 呼び出しが 1回あたり 10-30秒かかり、セクション数が多いスキル（14セクション等）では数分〜十数分を要する。optimize.py 内に `subprocess.run(["claude", "-p"])` が 10箇所以上あり、すべて同期逐次実行。独立したセクションの変異・評価は並行実行可能であり、asyncio で並行化することで大幅な高速化が見込める。

## What Changes

- `model_cascade.py` の `_execute()` を `asyncio.create_subprocess_exec` ベースの async メソッドに変更
- `optimize.py` の evaluate / mutate / crossover の `subprocess.run` 呼び出しを async 化
- セクション単位の変異・評価を `asyncio.gather` で並行実行（同時実行数制限付き）
- `parallel.py` の ThreadPoolExecutor を asyncio ベースに統一
- ルールベース fitness（`skill_quality` 等）利用時に LLM コールをスキップする高速パス追加

## Capabilities

### New Capabilities

- `async-claude-executor`: `claude -p` subprocess の async 実行基盤。Semaphore による同時実行数制御、タイムアウト、エスカレーション対応
- `parallel-section-optimization`: セクション単位の変異・評価の並行実行。asyncio.gather による独立セクションの同時処理

### Modified Capabilities

（既存 spec レベルの要件変更なし — 実装詳細の変更のみ）

## Impact

- **コード**: `model_cascade.py`, `optimize.py`, `parallel.py` の主要3ファイル
- **インターフェース**: `ModelCascade.run_with_tier()` が async に変更（**BREAKING** — 呼び出し元の対応が必要）
- **依存**: Python 標準ライブラリ `asyncio` のみ（新規外部依存なし）
- **テスト**: 既存テストの async 対応が必要（`pytest-asyncio` または同期ラッパー）
- **関連 issue**: closes #18
