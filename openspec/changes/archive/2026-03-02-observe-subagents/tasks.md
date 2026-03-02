## 1. hooks.json の修正

- [x] 1.1 hooks.json の全 `$PLUGIN_DIR` を `${CLAUDE_PLUGIN_ROOT}` に置換
- [x] 1.2 PostToolUse の matcher を `Skill` → `Skill|Agent` に変更
- [x] 1.3 SubagentStop エントリを追加（`${CLAUDE_PLUGIN_ROOT}/hooks/subagent_observe.py`）

## 2. 共通ユーティリティ作成 & SubagentStop フック実装

> タスク 2.x はタスク 1.x（hooks.json 修正）完了後に実施する

- [x] 2.0 `hooks/common.py` を作成（`ensure_data_dir()`, `append_jsonl()`, `DATA_DIR` を observe.py / session_summary.py / save_state.py から抽出・集約）
- [x] 2.1 `hooks/subagent_observe.py` を作成（stdin から SubagentStop イベント JSON を読み取り、`hooks/common.py` を import）
- [x] 2.2 agent_type, agent_id, last_assistant_message（500文字切り詰め）, agent_transcript_path, session_id, timestamp を subagents.jsonl に追記
- [x] 2.3 書き込み失敗時のサイレント失敗（stderr 出力のみ）

## 3. Agent ツール観測の追加

> タスク 3.x はタスク 2.0（common.py 作成）完了後に実施する

- [x] 3.1 `hooks/observe.py` を `hooks/common.py` の import に切り替え、Agent ツール呼び出しの記録ロジックを追加
- [x] 3.2 skill_name を `Agent:{subagent_type}` 形式で usage.jsonl に記録
- [x] 3.3 prompt を 200 文字に切り詰めて記録

## 4. テスト

- [x] 4.1 `hooks/tests/test_hooks.py` に SubagentStop フックのテスト追加
- [x] 4.2 Agent ツール呼び出しの observe テスト追加
- [x] 4.3 既存テスト全パス確認

## 5. バージョンアップ

- [x] 5.1 plugin.json を 0.2.4 にバンプ
- [x] 5.2 CHANGELOG.md に 0.2.4 エントリ追加
