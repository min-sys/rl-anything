## Why

`cross-project-telemetry-isolation` で observe hook に `project` フィールドを追加し、discover/audit が project 単位でフィルタリングできるようになった。しかし既存の usage.jsonl（1,922件）には `project` フィールドがなく、全てが `null`（unknown）扱いとなる。2層リカバリ（sessions.jsonl + `~/.claude/projects/` consensus）により 99.7%（1,916/1,922）のレコードに `project` を付与可能。

## What Changes

- `scripts/migrate_project_field.py` を新規作成: 2層リカバリで `session_id → project_name` マッピングを構築し、usage.jsonl の各レコードに `project` フィールドを追記するワンショットスクリプト
  - Tier 1: sessions.jsonl（last-wins dedup）→ 89% カバレッジ
  - Tier 2: `~/.claude/projects/` の consensus（同ディレクトリ内の他セッションから多数決で補完）→ +10.7%
- マッピングできないレコード（session_id なし、両層でマッチなし）は `project: null` のまま維持
- 実行前にバックアップ（`usage.jsonl.bak`）を自動作成
- `--dry-run` オプションでマッピング結果のサマリのみ表示（変更なし）

## Capabilities

### New Capabilities
- `project-field-migration`: 2層リカバリ（sessions.jsonl + filesystem consensus）で既存 usage.jsonl レコードに project フィールドを一括付与するワンショットマイグレーション

### Modified Capabilities

## Impact

- **scripts/migrate_project_field.py**: 新規作成。依存: `json`, `shutil`（標準ライブラリのみ）
- **~/.claude/rl-anything/usage.jsonl**: 既存レコードに `project` フィールドが追記される（破壊的変更。バックアップで復旧可能）
- **~/.claude/rl-anything/sessions.jsonl**: 読み取りのみ（変更なし）
