## ADDED Requirements

### Requirement: _collect_corrections は last_skill が None のレコードをスキップする

`_collect_corrections()` は corrections.jsonl のレコードで `last_skill` が `None` または未設定の場合、`AttributeError` を発生させず安全にスキップしなければならない（SHALL）。

#### Scenario: last_skill が null のレコード
- **WHEN** corrections.jsonl に `"last_skill": null` のレコードが存在する
- **THEN** そのレコードはスキップされ、他のレコードは正常に収集される

#### Scenario: last_skill キーが存在しないレコード
- **WHEN** corrections.jsonl に `last_skill` キー自体がないレコードが存在する
- **THEN** そのレコードはスキップされ、エラーは発生しない
