## 1. マイグレーションスクリプト作成

- [x] 1.1 `build_session_mapping()` — sessions.jsonl から session_id → project_name マッピング構築（last-wins dedup、null project_name スキップ）
- [x] 1.2 `build_fs_recovery()` — `~/.claude/projects/` ディレクトリ走査 → session_id が属するディレクトリを特定し、Tier 1 マッピング済みセッションから consensus で project_name を推定
- [x] 1.3 `build_project_mapping()` — Tier 1 + Tier 2 を合成した最終マッピングを返す
- [x] 1.4 `migrate_usage()` — usage.jsonl の各レコードに project フィールドを追加（既存 project は上書きしない = 冪等）、全レコード書き戻し
- [x] 1.5 バックアップ機能（`shutil.copy2` → `usage.jsonl.bak`）
- [x] 1.6 CLI エントリポイント（`python3 scripts/migrate_project_field.py [--dry-run]`、`--dry-run` はサマリ出力のみ）

## 2. テスト

- [x] 2.1 `build_session_mapping()` のテスト（正常、last-wins dedup、null project_name スキップ、空ファイル）
- [x] 2.2 `build_fs_recovery()` のテスト（consensus 成功、consensus なし、ディレクトリ不在）
- [x] 2.3 `build_project_mapping()` のテスト（Tier 1 + Tier 2 合成、Tier 2 は Tier 1 を上書きしない）
- [x] 2.4 `migrate_usage()` のテスト（マッピングあり、なし、既存 project 保持、session_id なし）
- [x] 2.5 dry-run モードのテスト（ファイル未変更の確認）
- [x] 2.6 バックアップ作成のテスト

## 3. 実行・検証

- [x] 3.1 `--dry-run` で実データのマッピング結果を確認
- [x] 3.2 本番実行（バックアップ確認後）
- [x] 3.3 実行後の usage.jsonl を検証（project フィールドの存在、カバレッジ確認）
