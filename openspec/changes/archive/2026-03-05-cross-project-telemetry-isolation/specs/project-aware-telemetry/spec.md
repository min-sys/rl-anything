## ADDED Requirements

### Requirement: observe hook records project identifier
observe hook（hooks/observe.py）は usage.jsonl および errors.jsonl の全レコードに `project` フィールドを記録する MUST。値は `CLAUDE_PROJECT_DIR` 環境変数の末尾ディレクトリ名（`common.project_name_from_dir()` を使用）とする。`CLAUDE_PROJECT_DIR` が未設定の場合は `null` とする。

#### Scenario: Normal project recording
- **WHEN** observe hook が PJ ディレクトリ `/Users/foo/atlas-breeaders` で Skill ツール呼び出しを処理する
- **THEN** usage.jsonl に追記されるレコードの `project` フィールドは `"atlas-breeaders"` である

#### Scenario: CLAUDE_PROJECT_DIR unset
- **WHEN** `CLAUDE_PROJECT_DIR` 環境変数が未設定の状態で observe hook が実行される
- **THEN** レコードの `project` フィールドは `null` である

#### Scenario: CLAUDE_PROJECT_DIR is empty string
- **WHEN** `CLAUDE_PROJECT_DIR` 環境変数が空文字列の状態で observe hook が実行される
- **THEN** レコードの `project` フィールドは `null` として扱われる MUST

### Requirement: discover filters by project
discover の `detect_behavior_patterns()` は `project_root` 引数が指定された場合、該当プロジェクトのレコードのみを集計する MUST。`project` が `null` のレコードはデフォルトで除外する MUST。

#### Scenario: Project-scoped discover
- **WHEN** `detect_behavior_patterns(project_root=Path("/Users/foo/atlas-breeaders"))` が呼ばれる
- **THEN** `project == "atlas-breeaders"` のレコードのみがカウントされ、他 PJ のパターンは候補に含まれない

#### Scenario: Include unknown project records
- **WHEN** `detect_behavior_patterns(project_root=Path("/Users/foo/atlas-breeaders"), include_unknown=True)` が呼ばれる
- **THEN** `project == "atlas-breeaders"` のレコードに加え、`project` が `null` のレコードも集計に含まれる

#### Scenario: Legacy records without project field
- **WHEN** usage.jsonl に `project` フィールドを持たないレコード（既存データ）が存在する
- **THEN** project フィルタ指定時、それらのレコードは集計から除外される

### Requirement: error patterns filter by project
discover の `detect_error_patterns()` は `project_root` 引数が指定された場合、該当プロジェクトの errors.jsonl レコードのみを集計する MUST。

#### Scenario: Project-scoped error detection
- **WHEN** `detect_error_patterns(project_root=Path("/Users/foo/atlas-breeaders"))` が呼ばれる
- **THEN** `project == "atlas-breeaders"` のエラーレコードのみがカウントされる

### Requirement: evolve passes project context to discover
evolve.py は `--project-dir` 引数を discover の全検出関数に `project_root` として伝播する MUST。

#### Scenario: evolve with project-dir
- **WHEN** `evolve.py --project-dir /Users/foo/atlas-breeaders` が実行される
- **THEN** discover の `detect_behavior_patterns()` および `detect_error_patterns()` に `project_root` が渡され、PJ スコープでフィルタリングされる

### Requirement: audit filters by project
audit.py は usage 集計時に `project_root` が指定された場合、該当プロジェクトのレコードのみを集計する MUST。`project_root` 未指定時は全レコードを対象とする（グローバル集計）。

#### Scenario: Project-scoped audit
- **WHEN** audit が `project_root=Path("/Users/foo/atlas-breeaders")` で実行される
- **THEN** `project == "atlas-breeaders"` の usage レコードのみが集計される

#### Scenario: Global audit
- **WHEN** audit が `project_root` 未指定で実行される
- **THEN** 全 project のレコードが集計対象となる（`--include-unknown` なしでも `null` レコードを含む）
