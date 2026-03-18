## 1. common.py ヘルパー・定数追加

- [x] 1.1 `common.py` に `extract_worktree_info(event: dict) -> dict | None` を追加（`name`, `branch` のみ抽出、`path`/`original_repo_dir` は除外）
- [x] 1.2 `common.py` に `INSTRUCTIONS_LOADED_FLAG_PREFIX = "instructions_loaded_"` と `STALE_FLAG_TTL_HOURS = 24` 定数を追加
- [x] 1.3 テスト追加: worktree あり/なし/不完全の event で正しく動作することを確認

## 2. observe.py の hook event enrichment

- [x] 2.1 Agent 記録に `event.get("agent_id", "")` を追加
- [x] 2.2 Skill / Agent 両方の usage 記録で worktree 情報を追加（`extract_worktree_info` 使用、None 時はキー省略）
- [x] 2.3 error 記録にも worktree 情報を追加
- [x] 2.4 テスト追加: agent_id / worktree 付き event で正しく記録されることを確認

## 3. subagent_observe.py の worktree 対応

- [x] 3.1 subagents.jsonl レコードに worktree 情報を追加（`extract_worktree_info` 使用）
- [x] 3.2 テスト追加: worktree 付き SubagentStop event で正しく記録されることを確認

## 4. InstructionsLoaded hook

- [x] 4.1 `hooks/instructions_loaded.py` を新規作成（sessions.jsonl に `type: "instructions_loaded"` を記録、フラグファイルで dedup、stale TTL ガード、サイレント失敗）
- [x] 4.2 `hooks/hooks.json` に `InstructionsLoaded` エントリを追加
- [x] 4.3 `hooks/session_summary.py` にフラグファイル cleanup を追加
- [x] 4.4 テスト追加: 初回記録・2回目スキップの動作確認

## 5. plugin validate 統合

- [x] 5.1 README.md のテストセクションに `claude plugin validate` を追記
- [x] 5.2 CLAUDE.md のテストセクションに `claude plugin validate` を追記

## 6. StopFailure hook（v2.1.78）

- [x] 6.1 `hooks/stop_failure.py` を新規作成（errors.jsonl に `type: "api_error"` + `error_type`/`error_message` を記録、worktree 情報付与）
- [x] 6.2 `hooks/hooks.json` に `StopFailure` エントリを追加
- [x] 6.3 テスト追加: rate_limit / auth_failure イベントで正しく記録されることを確認

## 7. rl-scorer Agent frontmatter 拡張（v2.1.78）

- [x] 7.1 `agents/rl-scorer.md` の frontmatter に `maxTurns: 15` を追加
- [x] 7.2 `agents/rl-scorer.md` の frontmatter に `disallowedTools: [Edit, Write, Bash]` を追加

## 8. DATA_DIR の CLAUDE_PLUGIN_DATA フォールバック（v2.1.78）

- [x] 8.1 `hooks/common.py` の `DATA_DIR` を `os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".claude" / "rl-anything"` に変更
- [x] 8.2 テスト追加: CLAUDE_PLUGIN_DATA 設定時にそちらが優先されることを確認
- [x] 8.3 テスト追加: CLAUDE_PLUGIN_DATA 未設定時に従来パスにフォールバックすることを確認

## 9. 検証

- [x] 9.1 既存テスト全通し（`python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v`）— 1518 passed
- [x] 9.2 `claude plugin validate` でプラグイン全体の整合性を確認 — marketplace.json の既存問題（$schema/description unrecognized keys）のみ。今回の変更に起因するエラーなし
