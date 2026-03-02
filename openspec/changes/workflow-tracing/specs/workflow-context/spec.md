## ADDED Requirements

### Requirement: PreToolUse hook で Skill 呼び出し時にワークフロー文脈ファイルを書き出さなければならない（MUST）
Skill ツールの PreToolUse 時に、セッション内のワークフロー文脈を `$TMPDIR/rl-anything-workflow-{session_id}.json` に書き出さなければならない（MUST）。文脈ファイルには `skill_name`, `session_id`, `workflow_id`, `started_at` を含む。同一セッション内で別の Skill が呼ばれた場合は上書きする。

#### Scenario: Skill 呼び出し時に文脈ファイルが作成される
- **WHEN** Skill ツール `opsx:refine` の PreToolUse イベントが発生する
- **THEN** `$TMPDIR/rl-anything-workflow-{session_id}.json` に `skill_name: "opsx:refine"`, `workflow_id`, `started_at` が書き出される

#### Scenario: 同一セッション内で別の Skill が呼ばれると文脈が上書きされる
- **WHEN** 同一セッション内で `opsx:refine` の後に `opsx:apply` が呼ばれる
- **THEN** 文脈ファイルの `skill_name` が `"opsx:apply"` に更新される
- **AND** `workflow_id` は新しい値に更新される

### Requirement: PostToolUse hook で Agent 呼び出しに parent_skill を付与しなければならない（MUST）
Agent ツールの PostToolUse 時に、ワークフロー文脈ファイルが存在すれば `parent_skill` と `workflow_id` を usage レコードに付与しなければならない（MUST）。文脈ファイルが存在しない場合は `parent_skill: null`, `workflow_id: null` を明示的に設定する。

#### Scenario: Skill 内で Agent が呼ばれた場合
- **WHEN** `opsx:refine` のワークフロー文脈が存在する状態で Agent:Explore が呼ばれる
- **THEN** usage.jsonl のレコードに `parent_skill: "opsx:refine"`, `workflow_id: "wf-abc123"` が付与される

#### Scenario: 手動で Agent が呼ばれた場合
- **WHEN** ワークフロー文脈ファイルが存在しない状態で Agent:Explore が呼ばれる
- **THEN** usage.jsonl のレコードに `parent_skill: null`, `workflow_id: null` が付与される

#### Scenario: 文脈ファイルの読み取りに失敗した場合
- **WHEN** 文脈ファイルが破損または読み取り不可の状態で Agent が呼ばれる
- **THEN** `parent_skill: null`, `workflow_id: null` として処理を継続する（セッションをブロックしてはならない MUST NOT）

#### Scenario: 文脈ファイルが24時間以上経過している場合
- **WHEN** 文脈ファイルが24時間以上前に作成された状態で Agent が呼ばれる
- **THEN** 文脈ファイルを無効とみなし `parent_skill: null`, `workflow_id: null` として処理する

### Requirement: SubagentStop hook にも parent_skill を付与しなければならない（MUST）
SubagentStop イベントの subagents.jsonl レコードにも、ワークフロー文脈ファイルから `parent_skill` と `workflow_id` を付与しなければならない（MUST）。

#### Scenario: Skill 内でサブエージェントが完了した場合
- **WHEN** `opsx:refine` のワークフロー文脈が存在する状態で Agent:Explore のサブエージェントが完了する
- **THEN** subagents.jsonl のレコードに `parent_skill: "opsx:refine"`, `workflow_id: "wf-abc123"` が付与される

#### Scenario: 手動サブエージェントが完了した場合
- **WHEN** ワークフロー文脈ファイルが存在しない状態でサブエージェントが完了する
- **THEN** subagents.jsonl のレコードに `parent_skill: null`, `workflow_id: null` が付与される

#### Scenario: 文脈ファイルが24時間以上経過している場合
- **WHEN** 文脈ファイルが24時間以上前に作成された状態でサブエージェントが完了する
- **THEN** 文脈ファイルを無効とみなし `parent_skill: null`, `workflow_id: null` として処理する

### Requirement: セッション終了時にワークフローシーケンスを workflows.jsonl に記録しなければならない（MUST）
Stop hook でセッション中のワークフロー文脈と usage レコードからシーケンスレコードを組み立て、`workflows.jsonl` に書き出さなければならない（MUST）。レコードは以下のフィールドを含む:

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `workflow_id` | string | `wf-{uuid4先頭8文字}` 形式の一意識別子 |
| `skill_name` | string | トリガーとなった Skill 名 |
| `session_id` | string | セッション ID |
| `started_at` | string (ISO 8601) | ワークフロー開始時刻 |
| `ended_at` | string (ISO 8601) | ワークフロー終了時刻（Stop hook の実行時刻） |
| `steps` | array | ワークフロー内のツール呼び出しシーケンス |
| `steps[].tool` | string | ツール名（例: `Agent:Explore`） |
| `steps[].intent_category` | string | ステップの意図分類（discover.py の `_PROMPT_CATEGORIES` と同じキーワード分類） |
| `steps[].timestamp` | string (ISO 8601) | ステップの実行時刻 |
| `step_count` | number | steps 配列の要素数 |
| `source` | string | `"trace"`（トレーシングによる記録） |

#### Scenario: ワークフローが存在するセッションの終了
- **WHEN** `opsx:refine` のワークフロー内で Agent:Explore が3回呼ばれたセッションが終了する
- **THEN** workflows.jsonl に `skill_name: "opsx:refine"`, `step_count: 3`, `steps` 配列を含むレコードが書き出される

#### Scenario: ワークフローが存在しないセッションの終了
- **WHEN** Skill が一度も呼ばれなかったセッションが終了する
- **THEN** workflows.jsonl には何も書き出されない

### Requirement: ワークフロー文脈ファイルをセッション終了時に削除しなければならない（MUST）
Stop hook でワークフロー文脈ファイル（`$TMPDIR/rl-anything-workflow-{session_id}.json`）を削除しなければならない（MUST）。文脈ファイルが存在しない場合はサイレントにスキップする。24時間以上経過した文脈ファイルは無効とみなす。

#### Scenario: セッション終了時のクリーンアップ
- **WHEN** セッションが終了し文脈ファイルが存在する
- **THEN** 文脈ファイルが削除される

#### Scenario: 文脈ファイルが存在しないセッションの終了
- **WHEN** セッションが終了し文脈ファイルが存在しない
- **THEN** エラーは発生しない

#### Scenario: 24時間以上経過した文脈ファイル
- **WHEN** PostToolUse が24時間以上前に作成された文脈ファイルを読み取る
- **THEN** 文脈ファイルを無効とみなし `parent_skill: null` として処理する

### Requirement: Discover は parent_skill の有無で contextualized / ad-hoc を分類しなければならない（MUST）
`parent_skill` が非 null のレコードは `contextualized`（スキル内呼び出し）、null のレコードは `ad-hoc`（手動呼び出し）として分類しなければならない（MUST）。`ad-hoc` パターンのみを新規スキル候補として提案する。`parent_skill` が null かつ `source: "backfill"` のレコードは `unknown`（不明）として保守的に扱う。

#### Scenario: contextualized な Agent 呼び出しはスキル候補にしない
- **WHEN** Agent:Explore の20回中15回が `parent_skill: "opsx:refine"` である
- **THEN** Discover は ad-hoc の5回のみを集計対象とし、閾値（5回）に達している場合のみスキル候補として提案する

#### Scenario: backfill データは unknown として除外
- **WHEN** Agent:Explore のレコードに `source: "backfill"`, `parent_skill: null` のものがある
- **THEN** そのレコードは `unknown` として ad-hoc にも contextualized にもカウントしない

### Requirement: Prune は parent_skill 経由の使用を使用回数に含めなければならない（MUST）
スキルの使用回数カウントに、直接の Skill tool_use に加えて usage.jsonl の `parent_skill` フィールドで参照されている回数を含めなければならない（MUST）。subagents.jsonl は Prune の参照対象外とする（subagents はスキル名ではなくエージェントタイプで記録されるため）。

#### Scenario: plan mode 経由で使用されているスキルは淘汰候補にならない
- **WHEN** `opsx:refine` の直接 Skill tool_use が0回だが、`parent_skill: "opsx:refine"` のレコードが15回ある
- **THEN** Prune は `opsx:refine` を使用回数15として扱い、淘汰候補にしない

#### Scenario: 直接も parent も0回のスキル
- **WHEN** あるスキルの直接 Skill tool_use が0回で `parent_skill` 参照も0回である
- **THEN** Prune はそのスキルを淘汰候補として報告する
