## ADDED Requirements

### Requirement: observe.py が Agent 記録に agent_id を含める
observe.py の Agent ツール記録時、event payload から `agent_id` を読み取り、usage.jsonl レコードに含めなければならない（SHALL）。
`agent_id` が event に存在しない場合は空文字列とする。

#### Scenario: Agent ツール呼び出しで agent_id が記録される
- **WHEN** PostToolUse event で tool_name が "Agent" かつ event に `agent_id` フィールドがある
- **THEN** usage.jsonl のレコードに `agent_id` フィールドが含まれる

#### Scenario: agent_id がない旧バージョンでも動作する
- **WHEN** PostToolUse event で tool_name が "Agent" かつ event に `agent_id` フィールドがない
- **THEN** usage.jsonl のレコードの `agent_id` は空文字列となる

### Requirement: worktree 情報を全テレメトリレコードに記録する
observe.py / subagent_observe.py が worktree セッション時に event payload の `worktree` フィールドを読み取り、テレメトリレコードに含めなければならない（SHALL）。
非 worktree セッションでは `worktree` キーを省略する（SHALL）。

#### Scenario: worktree セッションで usage が記録される
- **WHEN** PostToolUse event に `worktree` オブジェクト（name, path, branch）がある
- **THEN** usage.jsonl レコードに `worktree` フィールドが dict として含まれる

#### Scenario: 非 worktree セッションでは worktree キーが省略される
- **WHEN** PostToolUse event に `worktree` フィールドがない
- **THEN** usage.jsonl レコードに `worktree` キーは含まれない

#### Scenario: subagent_observe.py でも worktree が記録される
- **WHEN** SubagentStop event に `worktree` オブジェクトがある
- **THEN** subagents.jsonl レコードに `worktree` フィールドが dict として含まれる

### Requirement: common.py に worktree 抽出ヘルパーを提供する
`common.py` に `extract_worktree_info(event: dict) -> dict | None` 関数を追加する（SHALL）。
worktree フィールドが存在すれば `name` と `branch` のみを抽出した dict を返し、なければ None を返す（SHALL）。
`path` や `original_repo_dir` はフルパスを含むためテレメトリに記録してはならない（SHALL NOT）。

#### Scenario: worktree ありの event
- **WHEN** event に `worktree` キーが存在し dict 型である
- **THEN** `{"name": "<value>", "branch": "<value>"}` の dict を返す

#### Scenario: worktree なしの event
- **WHEN** event に `worktree` キーが存在しない
- **THEN** None を返す

#### Scenario: worktree に name/branch がない不完全な event
- **WHEN** event に `worktree` キーが存在するが `name` または `branch` がない
- **THEN** 存在するフィールドのみを含む dict を返す（空の場合は None）
