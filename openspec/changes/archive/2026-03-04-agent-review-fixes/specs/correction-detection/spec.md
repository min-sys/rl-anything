## MODIFIED Requirements

### Requirement: UserPromptSubmit hook で修正パターンを検出
hooks/correction_detect.py は UserPromptSubmit イベントの human message テキストに対して CJK/英語の修正パターンをマッチし、検出時に corrections.jsonl にレコードを追記する。LLM 呼び出しは行わない（MUST NOT）。レコードは正式スキーマに準拠すること（MUST）。偽陽性として報告済みのメッセージは `~/.claude/rl-anything/false_positives.jsonl` の SHA-256 ハッシュと照合し、検出対象から除外する（MUST）。

#### Scenario: 日本語修正パターン検出
- **WHEN** ユーザーが「いや、そうじゃなくて skill-evolve を使って」と入力する
- **THEN** corrections.jsonl に `{"correction_type": "iya", "message": "いや、そうじゃなくて skill-evolve を使って", "last_skill": null, "confidence": 0.85, "timestamp": "...", "session_id": "..."}` が追記される

#### Scenario: 英語修正パターン検出
- **WHEN** ユーザーが「No, don't use that approach」と入力する
- **THEN** corrections.jsonl に `{"correction_type": "no", "message": "No, don't use that approach", "last_skill": null, "confidence": 0.75, "timestamp": "...", "session_id": "..."}` が追記される

#### Scenario: 疑問文は除外
- **WHEN** ユーザーが「いや、それでいいの？」と末尾が「？」で終わる文を入力する
- **THEN** corrections.jsonl にはレコードが追記されない

#### Scenario: 偽陽性報告済みメッセージの除外
- **WHEN** ユーザーが以前に偽陽性として報告したメッセージと同一内容を入力し、そのメッセージの SHA-256 ハッシュが `~/.claude/rl-anything/false_positives.jsonl` に存在する
- **THEN** corrections.jsonl にはレコードが追記されない
