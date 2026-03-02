## 1. バックフィルスクリプト実装

- [x] 1.1 `skills/backfill/scripts/backfill.py` を作成（`sys.path` でプラグインルートを追加し `hooks/common.py` を import、CLI 引数パース）
- [x] 1.2 プロジェクトディレクトリ → `~/.claude/projects/` パスの解決ロジックを実装
- [x] 1.3 トランスクリプト JSONL パーサーを実装（`type: "assistant"` → `tool_use` ブロック抽出）
- [x] 1.4 Skill ツール呼び出しの抽出・usage.jsonl 書き出し（`source: "backfill"` 付与）
- [x] 1.5 Agent ツール呼び出しの抽出・usage.jsonl 書き出し（`Agent:{subagent_type}` 形式、prompt 200文字切り詰め）
- [x] 1.6 重複防止ロジックを実装（既存 JSONL の session_id + source=backfill をチェック）
- [x] 1.7 サマリ JSON 出力（sessions_processed, skill_calls, agent_calls, errors, skipped_sessions）
- [x] 1.8 `--force` フラグの実装（既存バックフィルレコード削除→再処理）

## 2. スキル定義

- [x] 2.1 `skills/backfill/SKILL.md` を作成（`/rl-anything:backfill` スキル定義）

## 3. テスト

- [x] 3.1 `skills/backfill/scripts/tests/test_backfill.py` にトランスクリプトパーサーのテスト追加
- [x] 3.2 Skill/Agent 抽出のテスト追加
- [x] 3.3 重複防止のテスト追加
- [x] 3.4 サマリ出力のテスト追加
- [x] 3.5 既存テスト全パス確認
- [x] 3.6 バックフィル後に evolve.py --dry-run でデータ十分性チェックが通ることを確認

## 4. バージョンアップ

- [x] 4.1 plugin.json を 0.2.5 にバンプ
- [x] 4.2 CHANGELOG.md に 0.2.5 エントリ追加
