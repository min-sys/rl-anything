Related: #17

## 1. CLAUDE.md に Compaction Instructions セクション追加

- [x] 1.1 CLAUDE.md に `## Compaction Instructions` セクションを追加（完了タスク/スキル実行結果/変更ファイル/最後の指示の4項目）

## 2. save_state.py: 作業コンテキスト収集・保存

- [x] 2.1 モジュール先頭に定数定義: `_MAX_UNCOMMITTED_FILES=30`, `_MAX_RECENT_COMMITS=5`, `_GIT_TIMEOUT_SECONDS=2`
- [x] 2.2 `_collect_work_context()` 関数を追加: `git log --oneline -5` + `git status --short` を subprocess で取得（個別 timeout `_GIT_TIMEOUT_SECONDS`、合計 3.5s 超過で残りコマンド skip）
- [x] 2.3 `handle_pre_compact()` の checkpoint に `work_context` フィールドを追加
- [x] 2.4 git コマンド失敗時のフォールバック処理（空リスト/空文字列）

## 3. restore_state.py: 作業コンテキスト復元

- [x] 3.1 `_format_work_context_summary()` 関数を追加: committed（完了）と uncommitted（作業中）を分離したサマリー生成
- [x] 3.2 `handle_session_start()` で work_context 付き checkpoint の復元時にサマリーを stdout 出力
- [x] 3.3 work_context なし checkpoint の後方互換性を維持

## 4. テスト追加

- [x] 4.1 save_state の work_context 保存テスト（正常系・git 失敗系・上限超過系）
- [x] 4.2 restore_state の work_context 復元テスト（正常系・フィールドなし後方互換系）

## 5. 既存テスト pass 確認

- [x] 5.1 `python3 -m pytest hooks/ -v` で既存テストが pass することを確認
