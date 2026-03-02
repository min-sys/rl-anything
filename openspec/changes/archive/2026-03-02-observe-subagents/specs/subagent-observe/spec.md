## ADDED Requirements

### Requirement: SubagentStop イベントで subagent の完了データを記録しなければならない（MUST）
SubagentStop フック `hooks/subagent_observe.py` で、agent_type, agent_id, last_assistant_message（500文字上限）, agent_transcript_path, timestamp を `~/.claude/rl-anything/subagents.jsonl` に追記しなければならない（MUST）。LLM 呼び出しは行ってはならない（MUST NOT）。

#### Scenario: subagent 正常完了時の記録
- **WHEN** subagent が正常に完了し SubagentStop イベントが発火する
- **THEN** subagents.jsonl に agent_type, agent_id, last_assistant_message（500文字以内）, agent_transcript_path, session_id, timestamp が1行追記される

#### Scenario: last_assistant_message が 500 文字を超える場合
- **WHEN** last_assistant_message が 500 文字を超える
- **THEN** 先頭 500 文字で切り詰めて記録しなければならない（MUST）

#### Scenario: 書き込み失敗時のサイレント失敗
- **WHEN** subagents.jsonl への書き込みに失敗する
- **THEN** セッションをブロックしてはならない（MUST NOT）。stderr にエラーを出力する

#### Scenario: last_assistant_message が空または null の場合
- **WHEN** last_assistant_message が空文字列または null である
- **THEN** 空文字列として記録しなければならない（MUST）

#### Scenario: agent_transcript_path が存在しないパスの場合
- **WHEN** agent_transcript_path が実在しないファイルパスである
- **THEN** パスのみ記録し、ファイル存在チェックは行ってはならない（MUST NOT）

### Requirement: hooks.json に SubagentStop エントリを追加しなければならない（MUST）
hooks.json の hooks セクションに SubagentStop イベントを定義し、`hooks/subagent_observe.py` を呼び出さなければならない（MUST）。

#### Scenario: SubagentStop フック設定
- **WHEN** プラグインが読み込まれる
- **THEN** hooks.json に SubagentStop エントリが存在し、`${CLAUDE_PLUGIN_ROOT}/hooks/subagent_observe.py` を実行する
