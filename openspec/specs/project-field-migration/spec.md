## ADDED Requirements

### Requirement: Migration script builds session-to-project mapping (Tier 1)
`scripts/migrate_project_field.py` は sessions.jsonl から `session_id → project_name` のマッピングを構築する MUST。同一 session_id に複数の project_name が存在する場合は最後のレコードを採用する MUST（last-wins）。`project_name` が null のレコードはスキップする MUST。

#### Scenario: Normal mapping construction
- **WHEN** sessions.jsonl に `{"session_id": "sess-001", "project_name": "atlas"}` が存在する
- **THEN** マッピングに `sess-001 → atlas` が登録される

#### Scenario: Duplicate session_id (last-wins)
- **WHEN** sessions.jsonl に同一 session_id で project_name が `"alpha"` と `"beta"` の2レコードが順に存在する
- **THEN** 最後のレコードの project_name（`"beta"`）が採用される

#### Scenario: Null project_name in sessions.jsonl
- **WHEN** sessions.jsonl に `{"session_id": "sess-002", "project_name": null}` が存在する
- **THEN** Tier 1 マッピングには `sess-002` は登録されない（Tier 2 で補完を試みる）

### Requirement: Filesystem consensus recovery (Tier 2)
Tier 1 でマッピングできなかった session_id に対し、`~/.claude/projects/` のディレクトリ構造から consensus でプロジェクト名を推定する MUST。同ディレクトリ内の他セッションが Tier 1 で project_name を持つ場合、多数決で補完する MUST。consensus が得られない場合は `null` のまま維持する MUST。

#### Scenario: Consensus recovery succeeds
- **WHEN** `~/.claude/projects/-Users-foo-bar/` 配下に session-A と session-B のファイルがある
- **AND** session-A は Tier 1 で `project_name: "bar"` にマッピング済み
- **AND** session-B は Tier 1 でマッピングなし（null project_name）
- **THEN** session-B に `project_name: "bar"` が consensus で付与される

#### Scenario: No consensus available
- **WHEN** `~/.claude/projects/-Users-foo-baz/` 配下の全セッションが Tier 1 でマッピングなし
- **THEN** これらのセッションは `project: null` のまま維持される

### Requirement: Migration script updates usage.jsonl records
マイグレーションスクリプトは usage.jsonl の各レコードに `project` フィールドを追加する MUST。既に `project` フィールドを持つレコードは上書きしない MUST（冪等性）。

#### Scenario: Record with matching session_id
- **WHEN** usage レコードの `session_id` がマッピングに存在する
- **THEN** レコードに `"project": "<mapped_project_name>"` が追加される

#### Scenario: Record without matching session_id
- **WHEN** usage レコードの `session_id` がマッピングに存在しない
- **THEN** レコードに `"project": null` が追加される

#### Scenario: Record already has project field
- **WHEN** usage レコードが既に `"project"` フィールドを持つ
- **THEN** 既存の `project` 値は変更されない

#### Scenario: Record without session_id
- **WHEN** usage レコードに `session_id` フィールドがない
- **THEN** レコードに `"project": null` が追加される

### Requirement: Migration creates backup before modification
マイグレーションスクリプトは usage.jsonl を変更する前に `usage.jsonl.bak` としてバックアップを作成する MUST。バックアップが既に存在する場合は上書きする MUST。

#### Scenario: Backup creation
- **WHEN** マイグレーションスクリプトが実行される
- **THEN** `usage.jsonl.bak` が作成され、元の内容と同一である

### Requirement: Dry-run mode
`--dry-run` オプション指定時は usage.jsonl を変更せず、マッピング結果のサマリのみを stdout に出力する MUST。

#### Scenario: Dry-run output
- **WHEN** `--dry-run` で実行される
- **THEN** 「total: N, mapped: M, unmapped: K, already_has_project: L」のサマリが出力され、usage.jsonl は変更されない
