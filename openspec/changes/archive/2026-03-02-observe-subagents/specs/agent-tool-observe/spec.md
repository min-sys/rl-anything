## ADDED Requirements

### Requirement: PostToolUse で Agent ツール呼び出しを観測しなければならない（MUST）
既存の observe.py の PostToolUse ハンドラを拡張し、Agent ツール呼び出し時に subagent_type, prompt（200文字上限）, timestamp を `~/.claude/rl-anything/usage.jsonl` に追記しなければならない（MUST）。

#### Scenario: Agent ツール呼び出しの記録
- **WHEN** PostToolUse イベントで tool_name が "Agent" である
- **THEN** usage.jsonl に skill_name="Agent:{subagent_type}", subagent_type, prompt（200文字以内）, session_id, timestamp が追記される

#### Scenario: Agent ツール呼び出しの JSONL レコード形式
- **WHEN** PostToolUse イベントで tool_name が "Agent"、subagent_type が "Explore" である
- **THEN** 以下の形式で usage.jsonl に追記される:
  ```json
  {
    "skill_name": "Agent:Explore",
    "subagent_type": "Explore",
    "prompt": "codebase を探索...",
    "session_id": "...",
    "timestamp": "..."
  }
  ```
- **AND** `skill_name` は discover.py との一貫性のため `Agent:{subagent_type}` 形式とする
- **AND** `subagent_type` は個別フィルタリング用に独立フィールドとしても保持する

#### Scenario: prompt が空の場合
- **WHEN** PostToolUse イベントで tool_name が "Agent" かつ prompt が空文字列である
- **THEN** 空文字列として記録しなければならない（MUST）

#### Scenario: subagent_type が未指定の場合
- **WHEN** PostToolUse イベントで tool_name が "Agent" かつ subagent_type が未指定である
- **THEN** `"unknown"` として記録しなければならない（MUST）

#### Scenario: Skill ツール呼び出しは既存動作を維持する
- **WHEN** PostToolUse イベントで tool_name が "Skill" である
- **THEN** 従来通り skill_name, file_path, session_id, timestamp が usage.jsonl に追記される

### Requirement: hooks.json の PostToolUse matcher を拡張しなければならない（MUST）
PostToolUse の matcher を `Skill` から正規表現 `Skill|Agent` に変更し、Agent ツール呼び出しも observe.py に送信しなければならない（MUST）。matcher は正規表現として評価される。

#### Scenario: matcher 拡張後の動作
- **WHEN** Agent ツールが呼び出される
- **THEN** PostToolUse フックが発火し observe.py にイベントが送信される

#### Scenario: matcher が正規表現として評価される
- **WHEN** hooks.json の PostToolUse matcher が `Skill|Agent` に設定されている
- **THEN** tool_name が "Skill" または "Agent" の場合にのみフックが発火する
- **AND** 他の tool_name（例: "Read", "Bash"）では発火しない
