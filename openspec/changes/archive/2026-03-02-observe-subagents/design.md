## Context

rl-anything の observe hooks は現在 PostToolUse（Skill matcher）のみ。subagent の活動は Claude Code の SubagentStop イベントで取得可能（agent_type, agent_transcript_path, last_assistant_message を含む）。hooks.json のパスは `$PLUGIN_DIR` を使用しているが、公式仕様では `${CLAUDE_PLUGIN_ROOT}` が正しい。

## Goals / Non-Goals

**Goals:**
- SubagentStop で subagent の完了データを JSONL に記録する
- Agent ツール呼び出しを PostToolUse で観測し、起動パターンを記録する
- hooks.json を公式仕様 `${CLAUDE_PLUGIN_ROOT}` に修正する
- 既存の discover/evolve パイプラインが subagent データを自然に取り込めるデータ形式にする

**Non-Goals:**
- subagent の transcript 全文の保存（パスのみ記録）
- subagent 内部のツール呼び出しの個別観測（Claude Code のイベントモデルでは不可）
- discover.py の subagent パターン検出ロジック実装（将来対応）

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | SubagentStop 用に専用スクリプト `hooks/subagent_observe.py` を作成 | observe.py に混ぜると責務が拡大。フック種別ごとにファイルを分離する既存パターンを踏襲 |
| 2 | subagent データは `subagents.jsonl` に記録 | usage.jsonl / errors.jsonl と同レベルの独立ファイル。discover.py が将来読み込む入力ソースとして明確 |
| 3 | Agent ツール呼び出しは既存 observe.py に追加 | Skill と Agent は同じ PostToolUse イベント。matcher を拡張するだけで対応可能 |
| 4 | hooks.json の `$PLUGIN_DIR` → `${CLAUDE_PLUGIN_ROOT}` 一括修正 | 公式仕様への準拠。SKILL.md の `<PLUGIN_DIR>` とは異なり、hooks.json は実際にシェル環境変数として展開される |
| 5 | 共通ユーティリティ `hooks/common.py` を作成し DRY 違反を解消 | `ensure_data_dir()` / `append_jsonl()` / `DATA_DIR` が observe.py, session_summary.py, save_state.py で重複定義されている。新規 subagent_observe.py 追加のタイミングで共通化 |

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| `${CLAUDE_PLUGIN_ROOT}` が未定義の環境 | hooks.json は Claude Code プラグインシステムが読み込むため、常に定義される。テストでは環境変数をモックする |
| subagents.jsonl の肥大化（大量の subagent 実行） | last_assistant_message を 500 文字に切り詰め。transcript_path はパスのみ保存 |
| PostToolUse matcher 拡張で意図しないツールをキャプチャ | matcher を `Skill\|Agent` に限定（正規表現）。Claude Code の hooks.json matcher は正規表現をサポートしており、完全一致ではなく部分一致で評価される |
