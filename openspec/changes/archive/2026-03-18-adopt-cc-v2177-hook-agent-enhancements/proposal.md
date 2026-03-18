## Why

Claude Code v2.1.69〜v2.1.78 で hook event の情報量拡充（agent_id/agent_type/worktree フィールド追加、InstructionsLoaded/StopFailure イベント）、Agent frontmatter の拡張（effort/maxTurns/disallowedTools）、プラグイン永続ストレージ（`${CLAUDE_PLUGIN_DATA}`）が追加された。rl-anything の observe hooks・エージェント定義・データ保存先がこれらに未対応のため、テレメトリの粒度不足・エージェントコスト制御不足・公式永続パス未活用が残っている。

## What Changes

### Hook event 新フィールドの活用（v2.1.69〜v2.1.77）
- `observe.py` / `subagent_observe.py` で hook event payload の `agent_id`, `agent_type` を読み取り、usage.jsonl に記録
- `observe.py` で `worktree` フィールド（name, path, branch, original_repo_dir）を読み取り、worktree セッションの追跡を可能にする
- `hooks.json` に `InstructionsLoaded` イベントを追加し、CLAUDE.md / rules 変更時の診断トリガーとして活用

### StopFailure hook（v2.1.78）
- `hooks.json` に `StopFailure` イベントを追加し、APIエラー（rate limit, 認証失敗等）によるセッション中断をテレメトリに記録

### Agent frontmatter 拡張（v2.1.78）
- `agents/rl-scorer.md` に `maxTurns` と `disallowedTools` を追加し、コスト制御と不要ツール呼び出し抑制を実現

### CLAUDE_PLUGIN_DATA 対応準備（v2.1.78）
- `hooks/common.py` の `DATA_DIR` を `${CLAUDE_PLUGIN_DATA}` 優先のフォールバック構成に変更し、公式永続パスへの段階的移行を可能にする

### plugin validate の開発フロー統合（v2.1.77）
- `claude plugin validate` をテスト手順・README に追加し、frontmatter / hooks.json の記述ミスを早期検出

## Capabilities

### New Capabilities
- `hook-event-enrichment`: observe hooks が agent_id/agent_type/worktree フィールドを読み取り、テレメトリに記録する
- `instructions-loaded-hook`: InstructionsLoaded イベントで CLAUDE.md/rules 変更検知トリガーを提供する
- `stop-failure-hook`: StopFailure イベントで API エラー終了をテレメトリに記録する
- `agent-cost-control`: rl-scorer に maxTurns/disallowedTools を設定しコスト制御する
- `plugin-data-migration`: DATA_DIR を CLAUDE_PLUGIN_DATA 優先フォールバックに変更する
- `plugin-validate-integration`: claude plugin validate を開発・テストフローに統合する

### Modified Capabilities
(なし — Agent resume は使用箇所なし、対応不要)

## Impact

- `hooks/observe.py` — event payload パース拡張
- `hooks/subagent_observe.py` — agent_id/agent_type 記録追加
- `hooks/hooks.json` — InstructionsLoaded + StopFailure エントリ追加
- `hooks/common.py` — DATA_DIR の CLAUDE_PLUGIN_DATA フォールバック対応
- `agents/rl-scorer.md` — maxTurns/disallowedTools frontmatter 追加
- `README.md` / `CLAUDE.md` — plugin validate 手順追加
- `scripts/lib/telemetry_query.py` — agent_id/worktree フィールドのクエリ対応（任意）
