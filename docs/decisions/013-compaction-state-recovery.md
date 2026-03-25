# ADR-013: Compaction State Recovery

Date: 2026-03-09
Status: Accepted

## Context

Claude Code の auto-compact（コンテキスト95%到達時の自動圧縮）後に、完了済みタスクを未完了と誤認して再実行する等、作業状態の喪失が発生していた。既存の PreCompact/SessionStart hook は evolve パイプラインの状態のみを保存しており、ユーザーの作業コンテキスト（完了タスク・変更ファイル一覧）は保存対象外だった。Issue #17 で調査済みの対策（Layer 1: CLAUDE.md Compaction Instructions、Layer 3: Hook ベース状態保存）を実装し、コンパクション後の状態復元を堅牢にする必要があった。

upstream issue `anthropics/claude-code#14160`（auto-compact 時 custom_instructions が空になる）の制約もあった。

## Decision

- **既存 hook の拡張**: 新規ファイルではなく既存の `save_state.py` / `restore_state.py` を拡張し、checkpoint.json に `work_context` フィールドを追加（後方互換）
- **git コマンドで作業コンテキストを取得**: `git log --oneline -5`（直近5コミット）と `git status --short`（未コミット変更）の2コマンドで committed/uncommitted を分離して保存
- **restore_state で人間可読サマリーを出力**: JSON だけでなく `[rl-anything:restore_state]` プレフィックス付きの自然言語サマリーを stdout に出力し、Claude が作業状態を把握できるようにする
- **CLAUDE.md に Compaction Instructions セクションを追加**: 圧縮時にサマリーに含めるべき情報を指示（Layer 1）
- **合計 timeout ガード**: `_collect_work_context()` 内で elapsed tracking を行い、合計 3.5s 超過時に残りの git コマンドを skip（hook の 5000ms timeout 内に確実に収める）
- **定数化**: `_MAX_UNCOMMITTED_FILES=30`, `_MAX_RECENT_COMMITS=5`, `_GIT_TIMEOUT_SECONDS=2`

## Alternatives Considered

- **テレメトリ再利用**: usage.jsonl / sessions.jsonl から作業状態を推定する案。テレメトリは「何を使ったか」であり「何が完了したか」の精度が不十分なため不採用
- **TodoWrite**: Claude Code の TodoWrite ツールで管理する案。compaction 後に TodoWrite の状態自体が失われるため fragile で不採用
- **event stdin**: PreCompact イベントの stdin に conversation が含まれる将来に期待する案。スキーマ未確定のため依存不可で不採用
- **LLM による高度なコンテキスト要約**: hook は 5000ms timeout であり LLM 呼び出しは時間内に収まらないため Non-Goals

## Consequences

**良い影響:**
- コンパクション後に完了済みタスク・変更ファイルが保持され、タスクの再実行を防止できるようになった
- Layer 1（CLAUDE.md）と Layer 3（hook）の多層防御により、upstream issue #14160 の影響下でも状態保持が可能
- committed/uncommitted の分離表示により、Claude が作業の進捗状態を正確に把握できる

**悪い影響:**
- checkpoint.json のサイズが若干増加（ただし uncommitted_files 30件、recent_commits 5件の上限で制御）
- upstream #14160 により Layer 1 が無効化される可能性が残る（Layer 3 でカバー）
- git コマンド実行のオーバーヘッド（通常 100ms 以内だが、大規模リポジトリでは timeout に近づく可能性）
