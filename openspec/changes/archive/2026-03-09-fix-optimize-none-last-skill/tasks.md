## 1. バグ修正

- [x] 1.1 `optimize.py:142` の `last_skill` 取得を `record.get("last_skill") or ""` に変更
- [x] 1.2 同メソッド内に他の None 安全でないパターンがないか確認

## 2. テスト

- [x] 2.1 `test_optimizer.py` に `last_skill: null` レコードを含むテストケースを追加
- [x] 2.2 `last_skill` キー自体が存在しないレコードのテストケースを追加
- [x] 2.3 既存テストが通ることを確認（`pytest skills/genetic-prompt-optimizer/tests/ -v`）
