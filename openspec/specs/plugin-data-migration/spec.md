## ADDED Requirements

### Requirement: DATA_DIR が CLAUDE_PLUGIN_DATA を優先する
`hooks/common.py` の `DATA_DIR` は `${CLAUDE_PLUGIN_DATA}` 環境変数が設定されていればそれを使用し、未設定時は `~/.claude/rl-anything/` にフォールバックする（SHALL）。

#### Scenario: CLAUDE_PLUGIN_DATA が設定されている場合
- **WHEN** 環境変数 `CLAUDE_PLUGIN_DATA` が "/path/to/plugin-data" に設定されている
- **THEN** `DATA_DIR` は `Path("/path/to/plugin-data")` となる

#### Scenario: CLAUDE_PLUGIN_DATA が未設定の場合
- **WHEN** 環境変数 `CLAUDE_PLUGIN_DATA` が設定されていない
- **THEN** `DATA_DIR` は `Path.home() / ".claude" / "rl-anything"` となる

#### Scenario: CLAUDE_PLUGIN_DATA が空文字列の場合
- **WHEN** 環境変数 `CLAUDE_PLUGIN_DATA` が空文字列に設定されている
- **THEN** `DATA_DIR` は従来の `~/.claude/rl-anything/` にフォールバックする

### Requirement: 既存データのマイグレーションは行わない
本変更では既存テレメトリデータの移行は行わない（SHALL NOT）。
新規データのみ `CLAUDE_PLUGIN_DATA` に書き込まれる。
