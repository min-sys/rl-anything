Closes: #25

## Why

evolve が `reflect_data_count: 7` と報告するが、reflect 単体実行では `validate_corrections count mismatch (expected 7, got 0)` で 0 件になるバグ（#25）。evolve と reflect で corrections.jsonl の読み込み・フィルタリングロジックが不一致であり、semantic validation の LLM 呼び出し失敗時に全件 `is_learning=False` にフォールバックして全件除外される。

## What Changes

- `semantic_detector.py` の `validate_corrections` / `semantic_analyze` で件数不一致時のフォールバックを安全側（全件除外）から適切なリカバリに変更
- evolve（discover）の `reflect_data_count` を reflect と同じフィルタ条件（`reflect_status == "pending"`）でカウントするよう修正
- reflect の `is_learning` フォールバック時に全件除外ではなく、regex フォールバックの結果を尊重する

## Capabilities

### New Capabilities

（なし）

### Modified Capabilities

- `semantic-validation`: LLM 件数不一致時のフォールバック戦略を「全件除外」から「regex フォールバック」に変更
- `reflect`: semantic validation 失敗時の is_learning フィルタ挙動を修正
- `project-aware-telemetry`: evolve の reflect_data_count が pending フィルタを適用するよう修正

## Impact

- **影響コード**: `scripts/lib/semantic_detector.py`, `skills/reflect/scripts/reflect.py`, `skills/discover/scripts/discover.py`
- **テスト**: 既存の semantic_detector / reflect テストの更新が必要
- **後方互換**: フォールバック挙動の変更のみ、API・スキーマ変更なし
