## 1. サブカテゴリ定義

- [x] 1.1 `hooks/common.py` の `PROMPT_CATEGORIES` から `conversation` エントリを5つのサブカテゴリ（`conversation:approval`, `conversation:confirmation`, `conversation:question`, `conversation:direction`, `conversation:thanks`）に分割。`いいえ` を `conversation:approval` に含める（承認/否認は同じ意思決定カテゴリ）
- [x] 1.2 `classify_prompt()` のフォールバックロジック追加: サブカテゴリにマッチしない場合は `conversation` を返す
- [x] 1.3 `hooks/common.py` のユニットテスト追加: 各サブカテゴリのマッチ、conversation フォールバック、複数キーワードマッチ時の優先度（挿入順で最初にマッチしたサブカテゴリが返ること）

## 2. reclassify 対応

- [x] 2.1 `skills/backfill/scripts/reclassify.py` の `VALID_CATEGORIES` に5つのサブカテゴリを追加
- [x] 2.2 reclassify のテスト追加: サブカテゴリが有効なカテゴリとして受け入れられることを確認

## 3. analyze レポート対応

- [x] 3.1 `skills/backfill/scripts/analyze.py` に `conversation:*` 集約ロジック追加: 合計行 + 内訳行
- [x] 3.2 analyze のテスト追加: サブカテゴリ集約表示の出力確認

## 4. 検証

- [x] 4.1 既存テスト全体の回帰テスト実行
- [x] 4.2 実際の usage.jsonl データでサブカテゴリ分類結果を確認

関連 Issue: #4
