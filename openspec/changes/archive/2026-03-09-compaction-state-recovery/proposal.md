Related: #17

## Why

Claude Code の auto-compact（コンテキスト95%到達時の自動圧縮）後に、完了済みタスクを未完了と誤認して再実行する等、作業状態の喪失が発生している。現在の PreCompact/SessionStart hook は evolve パイプラインの状態のみを保存しており、ユーザーの作業コンテキスト（完了タスク・変更ファイル一覧）は保存対象外。Issue #17 で調査済みの対策を実装し、コンパクション後の状態復元を堅牢にする。

Roadmap の Gap 1-6 と直交する standalone レジリエンス修正。

## What Changes

- **Layer 1**: CLAUDE.md に Compaction Instructions セクションを追加し、圧縮時にサマリーに含めるべき情報を指示
- **Layer 3**: 既存の `save_state.py` / `restore_state.py` を拡張し、作業コンテキスト（committed/uncommitted の区別付き）を保存・復元する

## Capabilities

### New Capabilities
- `work-context-checkpoint`: CLAUDE.md Compaction Instructions セクション + PreCompact hook による作業コンテキスト（committed/uncommitted 区別付き）の保存と SessionStart hook による復元

### Modified Capabilities

（なし）

## Impact

- `CLAUDE.md` — Compaction Instructions セクション追加
- `hooks/save_state.py` — 作業コンテキスト保存の拡張
- `hooks/restore_state.py` — 作業コンテキスト復元の拡張
- upstream issue（`#14160` auto-compact の custom_instructions 空問題）の制約あり。Layer 1 は回避策として機能するが、完全解決は upstream 依存
