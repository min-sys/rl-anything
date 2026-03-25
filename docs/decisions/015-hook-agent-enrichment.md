# ADR-015: Hook Event & Agent Enrichment (CC v2.1.69-v2.1.78)

Date: 2026-03-18
Status: Accepted

## Context

rl-anything v1.7.0 の observe hooks は 7 イベントを処理していたが、Claude Code v2.1.69〜v2.1.78 で追加された以下の機能が未活用だった:

- hook event payload の `agent_id`, `agent_type`, `worktree` フィールド（v2.1.69〜v2.1.77）
- `InstructionsLoaded` イベント（v2.1.77）
- `StopFailure` イベント（v2.1.78）
- Agent frontmatter の `effort`/`maxTurns`/`disallowedTools`（v2.1.78）
- `${CLAUDE_PLUGIN_DATA}` 環境変数（v2.1.78）

これらの未活用により、テレメトリの粒度不足・エージェントコスト制御不足・公式永続パス未活用が課題となっていた。

## Decision

- **agent_id 取得**: observe.py で event payload の `agent_id` フィールドを使用し usage.jsonl に記録。tool_input からの擬似 ID 生成は正規フィールドがあるため不採用
- **worktree 記録**: `common.py` に `extract_worktree_info(event)` ヘルパーを追加。`name` と `branch` のみ抽出（`path`/`original_repo_dir` はプライバシー情報を含むため除外）。非 worktree セッションではキー省略
- **InstructionsLoaded hook**: 軽量な検知のみ。sessions.jsonl に記録。flag file（`{DATA_DIR}/tmp/instructions_loaded_{session_id}`）で重複防止、stale TTL 24h で残存対策
- **StopFailure hook**: API エラーによるセッション中断を errors.jsonl に記録（`type:"api_error"`）。既存の session_summary.py とは責務が異なるため新規スクリプト
- **rl-scorer の maxTurns/disallowedTools**: `maxTurns: 15` でコスト上限設定。`disallowedTools: [Edit, Write, Bash]` で採点エージェントのコード変更を禁止。Agent は除外（サブエージェント起動に必要）
- **DATA_DIR の CLAUDE_PLUGIN_DATA フォールバック**: `${CLAUDE_PLUGIN_DATA}` 優先、未設定時は `~/.claude/rl-anything/` にフォールバック。既存データの一括マイグレーションは行わない（段階的移行）
- **plugin validate 統合**: README.md のテストセクションに `claude plugin validate` を追加（CI は未構築のため将来対応）

## Alternatives Considered

- **agent_id を tool_input のハッシュで擬似生成**: CC v2.1.69 で正式な `agent_id` が追加されたため不採用
- **worktree オブジェクト全量コピー**: フルパスによるプライバシー情報混入リスクがあるため不採用
- **worktree を boolean フラグのみ記録**: branch 情報が分析に有用なため不採用
- **InstructionsLoaded の環境変数フラグ管理**: hook は別プロセスで実行されるため環境変数を共有できず不採用
- **InstructionsLoaded を sessions.jsonl 冪等チェックで重複防止**: ファイル読み込みコスト大 + レースコンディションリスクで不採用
- **StopFailure を session_summary.py に統合**: 正常終了と異常終了は責務が異なるため不採用
- **disallowedTools に Agent を含める**: rl-scorer 自身がサブエージェントを起動するため不可
- **DATA_DIR の即時全量マイグレーション**: データ量が大きくコストが高いため不採用

## Consequences

**良い影響:**
- サブエージェント単位の追跡が可能になり、テレメトリ粒度が向上
- worktree 利用パターンの分析基盤が整った
- InstructionsLoaded により CLAUDE.md/rules 変更の検知トリガーが確立
- StopFailure により API エラー終了がテレメトリに記録され、障害分析が可能に
- rl-scorer の maxTurns/disallowedTools によりコスト制御と安全性が向上
- CLAUDE_PLUGIN_DATA 対応により plugin update 時のデータ永続性が改善

**悪い影響:**
- 新フィールドはすべて optional のため、既存テレメトリとの混在期間が発生（後方互換は維持）
- InstructionsLoaded が高頻度発火する可能性（dedup ガードで緩和）
- CLAUDE_PLUGIN_DATA 未設定の環境（CC v2.1.78 未満）ではフォールバックパスが使われ、段階的移行が必要
