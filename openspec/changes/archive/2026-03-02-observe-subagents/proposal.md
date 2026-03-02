## Why

現状の observe hooks は Skill ツール呼び出しのみを観測しており、subagent（Agent ツール）の活動は記録されない。atlas-breeaders のように gamer agent が並列でゲーム評価を行うプロジェクトでは、subagent の行動パターン・エラー・成果がデータとして蓄積されず、Discover/Optimize フェーズの改善対象から除外されてしまう。

## What Changes

- SubagentStop hook を追加し、subagent の完了時にメタデータ（agent_type, 実行結果サマリ）を記録
- PostToolUse hook の matcher を拡張し、Agent ツール呼び出しも観測対象に追加
- hooks.json の `$PLUGIN_DIR` を公式の `${CLAUDE_PLUGIN_ROOT}` に修正（既知の技術的負債）

## Capabilities

### New Capabilities
- `subagent-observe`: SubagentStop イベントで subagent の活動を記録する。agent_type, transcript_path, last_assistant_message をキャプチャし、既存の JSONL データストアに追記
- `agent-tool-observe`: PostToolUse で Agent ツール呼び出しを観測し、subagent の起動パターンを記録

### Modified Capabilities
- `observe`: hooks.json のコマンドパスを `${CLAUDE_PLUGIN_ROOT}` に修正

## Impact

- `hooks/observe.py`: Agent ツール呼び出しの記録ロジック追加
- `hooks.json`: SubagentStop エントリ追加、`$PLUGIN_DIR` → `${CLAUDE_PLUGIN_ROOT}` 修正
- `scripts/discover.py`: subagent パターン検出の入力ソース追加（将来対応）
- 新規ファイル: `hooks/subagent_observe.py`
