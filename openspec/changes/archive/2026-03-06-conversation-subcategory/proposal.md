## Why

backfill 分析で `conversation` カテゴリが最多（188件/163セッション）を占めるが、内訳が不明のため「ユーザーがどんな対話をしているか」の洞察が得られない。確認応答・質問・方針指示・承認など性質の異なるプロンプトが一括りにされており、分析価値が低い。

## What Changes

- `hooks/common.py` の `PROMPT_CATEGORIES` に conversation サブカテゴリを導入: `conversation:confirmation`, `conversation:question`, `conversation:direction`, `conversation:approval`, `conversation:thanks`
- `classify_prompt()` を更新し、conversation マッチ時にサブカテゴリまで分類
- `skills/backfill/scripts/reclassify.py` の `VALID_CATEGORIES` にサブカテゴリを追加し、LLM reclassification でもサブカテゴリを出力可能にする
- `skills/backfill/scripts/analyze.py` に `conversation:*` の集約表示（合計 + サブカテゴリ内訳）を追加
- 既存の `conversation` ラベルとの後方互換を維持（サブカテゴリ未分類のものは `conversation` のまま）

## Capabilities

### New Capabilities
- `conversation-subcategory`: conversation カテゴリのサブカテゴリ分類ロジックと集約レポート

### Modified Capabilities
- `reclassify`: VALID_CATEGORIES にサブカテゴリを追加

## Impact

- `hooks/common.py`: PROMPT_CATEGORIES 定数変更、classify_prompt() ロジック変更
- `skills/backfill/scripts/reclassify.py`: VALID_CATEGORIES 拡張
- `skills/backfill/scripts/analyze.py`: レポート出力フォーマット変更
- 既存の usage.jsonl データは後方互換（`conversation` ラベルのまま有効）
- 関連 Issue: #4
