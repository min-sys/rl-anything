## ADDED Requirements

### Requirement: 偽陽性レポート機構
corrections の偽陽性をユーザーが報告できる機構を提供する。報告された偽陽性は `~/.claude/rl-anything/false_positives.jsonl` に JSONL 形式で保存される（MUST）。各レコードの `message_hash` は SHA-256 ハッシュ、`timestamp` は ISO 8601 形式とする（MUST）。

#### Scenario: reflect 実行中に偽陽性を報告
- **WHEN** `/rl-anything:reflect` の実行中にユーザーが correction を「偽陽性」としてマーク
- **THEN** `false_positives.jsonl` に `{"message_hash": "<メッセージの SHA-256 ハッシュ>", "original_type": "<correction_type>", "timestamp": "<ISO 8601 形式のタイムスタンプ>"}` が追記される

#### Scenario: 報告済み偽陽性のフィルタリング
- **WHEN** `detect_correction()` がパターンを検出し、そのメッセージの hash が `false_positives.jsonl` に存在する
- **THEN** 検出結果は `None` を返し、corrections.jsonl にはレコードが追記されない

### Requirement: 偽陽性データの自動クリーンアップ
`false_positives.jsonl` のエントリは180日経過後に自動削除される（MUST）。クリーンアップは `reflect` 実行時に行う。

#### Scenario: 180日超のエントリが削除される
- **WHEN** `reflect` が実行され、`false_positives.jsonl` に180日以上前の timestamp を持つエントリが存在する
- **THEN** 該当エントリは `false_positives.jsonl` から削除される

#### Scenario: false_positives.jsonl 読み込み失敗時
- **WHEN** `detect_correction()` が `false_positives.jsonl` の読み込みに失敗する（ファイル破損、パースエラー等）
- **THEN** 偽陽性フィルタリングをスキップし、通常の検出処理を続行する（サイレント続行）
