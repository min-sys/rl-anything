Closes: #25

## 1. semantic_detector.py のフォールバック修正

- [x] 1.1 `semantic_analyze()` の件数不一致フォールバックで `is_learning=True` を返すよう変更（`scripts/lib/semantic_detector.py`）
- [x] 1.2 `semantic_analyze()` の partial success 対応 — LLM が N < len(batch) 件返した場合、`index` フィールドで入力とマッチングし、マッチ分を適用し残りを `is_learning=True` でパススルー
- [x] 1.3 `validate_corrections()` の例外フォールバックで `is_learning=True` を返すよう変更
- [x] 1.4 semantic_detector のテスト更新 — 件数不一致/パース失敗/partial success の各ケースで `is_learning=True` を検証

## 2. discover.py の reflect_data_count 修正

- [x] 2.1 `load_claude_reflect_data()` に `reflect_status == "pending"` フィルタを追加（`skills/discover/scripts/discover.py`）
- [x] 2.2 discover のテスト更新 — pending フィルタ適用後のカウントを検証

## 3. テスト・検証

- [x] 3.1 reflect のテスト更新 — semantic validation 失敗時に corrections が 0 件にならないことを検証
- [x] 3.2 全テスト実行（`python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v`）で regression なしを確認
