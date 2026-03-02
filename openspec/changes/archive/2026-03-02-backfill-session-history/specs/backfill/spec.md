## ADDED Requirements

### Requirement: セッショントランスクリプトから Skill ツール呼び出しを抽出しなければならない（MUST）
`~/.claude/projects/<project-dir>/*.jsonl` 内の `type: "assistant"` レコードから `tool_use` ブロック（`name: "Skill"`）を検出し、`skill_name`, `session_id`, `timestamp` を usage.jsonl に追記しなければならない（MUST）。timestamp はトランスクリプトレコードのトップレベル `timestamp` フィールドから取得する（MUST）。

#### Scenario: Skill ツール呼び出しの抽出
- **WHEN** トランスクリプトに `name: "Skill"`, `input.skill: "my-skill"` の tool_use ブロックが存在し、レコードの `timestamp` が `"2025-06-15T10:30:00Z"` である
- **THEN** usage.jsonl に `skill_name: "my-skill"`, `session_id`, `timestamp: "2025-06-15T10:30:00Z"`, `source: "backfill"` が追記される

#### Scenario: Skill 呼び出しがないセッション
- **WHEN** トランスクリプトに Skill の tool_use ブロックが存在しない
- **THEN** usage.jsonl には何も追記されない

### Requirement: セッショントランスクリプトから Agent ツール呼び出しを抽出しなければならない（MUST）
`tool_use` ブロック（`name: "Agent"`）から `subagent_type`, `prompt`（200文字上限）, `session_id`, `timestamp` を usage.jsonl に追記しなければならない（MUST）。`skill_name` は `Agent:{subagent_type}` 形式とする。timestamp はトランスクリプトレコードのトップレベル `timestamp` フィールドから取得する（MUST）。

#### Scenario: Agent ツール呼び出しの抽出
- **WHEN** トランスクリプトに `name: "Agent"`, `input.subagent_type: "Explore"` の tool_use ブロックが存在し、レコードの `timestamp` が `"2025-06-15T11:00:00Z"` である
- **THEN** usage.jsonl に `skill_name: "Agent:Explore"`, `subagent_type: "Explore"`, `prompt`（200文字以内）, `timestamp: "2025-06-15T11:00:00Z"`, `source: "backfill"` が追記される

#### Scenario: subagent_type が未指定の Agent 呼び出し
- **WHEN** `input.subagent_type` が存在しないまたは null である
- **THEN** `subagent_type: "unknown"`, `skill_name: "Agent:unknown"` として記録しなければならない（MUST）

### Requirement: パース失敗したレコードはスキップしなければならない（MUST）
不正な JSON やスキーマ不一致のレコードはスキップし、処理を継続しなければならない（MUST）。スキップしたレコード数をサマリの errors フィールドに含める。

#### Scenario: 不正 JSON レコード
- **WHEN** トランスクリプトに不正な JSON 行が含まれる
- **THEN** その行をスキップし、次の行の処理を継続する
- **AND** サマリの errors が1増加する

#### Scenario: tool_use ブロックのないアシスタントレコード
- **WHEN** `type: "assistant"` のレコードに tool_use ブロックがない
- **THEN** そのレコードはスキップされる（エラーカウントに含めない）

### Requirement: バックフィルレコードに source タグを付与しなければならない（MUST）
全てのバックフィルレコードに `source: "backfill"` フィールドを付与し、リアルタイム hooks データと区別可能にしなければならない（MUST）。

#### Scenario: source タグの付与
- **WHEN** バックフィルスクリプトが JSONL レコードを書き出す
- **THEN** 全レコードに `source: "backfill"` が含まれる

#### Scenario: リアルタイムデータとの共存
- **WHEN** usage.jsonl に既存のリアルタイムデータが存在する
- **THEN** バックフィルデータは追記され、既存データを上書きしてはならない（MUST NOT）

### Requirement: 重複バックフィルを防止しなければならない（MUST）
同一セッションを2回バックフィルした場合、重複レコードを生成してはならない（MUST NOT）。

#### Scenario: 同一セッションの再バックフィル
- **WHEN** session_id "sess-001" のデータが既に usage.jsonl に `source: "backfill"` で存在する
- **THEN** 同一セッションのレコードはスキップされ、重複は発生しない

#### Scenario: 初回バックフィル
- **WHEN** usage.jsonl にバックフィルデータが存在しない
- **THEN** 全セッションのデータが書き出される

#### Scenario: 中断後の再実行
- **WHEN** バックフィルが途中で中断し、session_id "sess-001" の一部レコードのみ書き出されている
- **THEN** 再実行時に session_id "sess-001" は既にバックフィル済みとしてスキップされる
- **AND** ユーザーは `--force` フラグで再処理を強制できる

#### Scenario: --force フラグによる再処理
- **WHEN** `--force` フラグを指定して実行する
- **THEN** 既にバックフィル済みのセッションも含め、全セッションを再処理する
- **AND** 既存のバックフィルレコード（`source: "backfill"`）を削除してから書き出す

### Requirement: プロジェクトディレクトリを指定してバックフィルできなければならない（MUST）
バックフィル対象のプロジェクトを引数で指定可能とし、デフォルトはカレントディレクトリに対応するプロジェクトとしなければならない（MUST）。

#### Scenario: カレントディレクトリのバックフィル
- **WHEN** `--project-dir` を省略して実行する
- **THEN** カレントディレクトリに対応する `~/.claude/projects/` 配下のトランスクリプトが処理される

#### Scenario: 指定ディレクトリのバックフィル
- **WHEN** `--project-dir /path/to/project` を指定して実行する
- **THEN** 指定パスに対応するトランスクリプトが処理される

### Requirement: バックフィル結果のサマリを出力しなければならない（MUST）
処理完了後、抽出した Skill 呼び出し数・Agent 呼び出し数・エラー数・スキップしたセッション数を JSON で出力しなければならない（MUST）。

#### Scenario: サマリ出力
- **WHEN** バックフィルが完了する
- **THEN** `{"sessions_processed": N, "skill_calls": N, "agent_calls": N, "errors": N, "skipped_sessions": N}` 形式の JSON が stdout に出力される
