## Context

`optimize.py:142` で `record.get("last_skill", "")` を使用しているが、corrections.jsonl に `"last_skill": null` が明示的に書かれている場合、`dict.get()` はデフォルト値ではなく `None` を返す。これにより `.lower()` 呼び出しで `AttributeError` が発生する。

## Goals / Non-Goals

**Goals:**
- `last_skill` が `None` のレコードでクラッシュしない
- テストカバレッジ追加

**Non-Goals:**
- corrections.jsonl のスキーマ変更や書き込み側の修正
- 他メソッドの防御的コーディング全般の見直し

## Decisions

### `or ""` パターンで None を空文字に変換

```python
last_skill = record.get("last_skill") or ""
```

**理由**: `get(key, default)` は key が存在しない場合のみ default を返す。値が `None` の場合は `or ""` で空文字にフォールバックする方が確実。Issue #24 の修正案（`if last_skill and ...`）でも動作するが、`or ""` パターンの方が後続の `.lower()` 呼び出しを変更せずに済み、影響範囲が最小。

## Risks / Trade-offs

- **リスク**: なし。`last_skill` が `None` のレコードは元々マッチしないため、スキップと同等の結果になる
