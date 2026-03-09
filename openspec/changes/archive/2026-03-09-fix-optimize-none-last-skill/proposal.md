## Why

`optimize.py` の `_collect_corrections()` で `corrections.jsonl` の `last_skill` が `None`（明示的に `null` 設定）の場合に `AttributeError` が発生しクラッシュする。`dict.get("last_skill", "")` はキーが存在しない場合のみ空文字を返し、値が `null` の場合は `None` をそのまま返すため。evolve Step 5 で任意のカスタムスキルを optimize する際に再現する。

## What Changes

- `_collect_corrections()` の `last_skill` 取得を `None` 安全にする
- 同メソッド内の類似パターンがあれば同様に修正
- テストケースを追加して `last_skill: null` のレコードでクラッシュしないことを保証

## Capabilities

### New Capabilities

なし

### Modified Capabilities

なし（実装レベルのバグ修正のみ、仕様変更なし）

## Impact

- `skills/genetic-prompt-optimizer/scripts/optimize.py` — `_collect_corrections()` メソッド
- `skills/genetic-prompt-optimizer/tests/test_optimizer.py` — テスト追加
