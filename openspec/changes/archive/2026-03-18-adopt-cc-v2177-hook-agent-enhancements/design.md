## Context

rl-anything v1.7.0 の observe hooks は PostToolUse / SubagentStop / PreCompact / SessionStart / Stop / UserPromptSubmit の 7 イベントを処理している。Claude Code v2.1.69〜v2.1.78 で以下の機能が追加されたが、未活用:

- hook event payload に `agent_id`, `agent_type`, `worktree` フィールド追加（v2.1.69〜v2.1.77）
- `InstructionsLoaded` イベント新設（v2.1.77）
- `StopFailure` イベント新設 — APIエラー時に発火（v2.1.78）
- プラグインエージェント frontmatter に `effort`/`maxTurns`/`disallowedTools` 対応（v2.1.78）
- `${CLAUDE_PLUGIN_DATA}` 環境変数 — plugin update で保持される永続ストレージ（v2.1.78）

現状:
- `observe.py` の Agent 記録は `subagent_type`（tool_input 由来）のみ。event 由来の `agent_id`/`agent_type` は未取得
- `subagent_observe.py` は既に `agent_id`/`agent_type` を event から取得済み（対応不要）
- `worktree` フィールドは全 hook で未取得
- `InstructionsLoaded` / `StopFailure` イベントは hooks.json に未定義
- `agents/rl-scorer.md` は `model: haiku` のみ。maxTurns/disallowedTools 未設定
- `DATA_DIR` は `~/.claude/rl-anything/` にハードコード。CLAUDE_PLUGIN_DATA 未参照
- Agent `resume` パラメータはスキル/エージェント定義で使用箇所なし（対応不要）

## Goals / Non-Goals

**Goals:**
- observe.py の Agent 記録に event 由来の `agent_id` を追加し、サブエージェント単位の追跡を可能にする
- worktree セッション情報をテレメトリに記録し、worktree 利用パターンの分析基盤を作る
- InstructionsLoaded hook で CLAUDE.md/rules 変更の検知ポイントを確立する
- `claude plugin validate` を開発フローに統合する

**Non-Goals:**
- telemetry_query.py の agent_id/worktree クエリ対応（データ蓄積後に別 change で対応）
- Agent resume → SendMessage 移行（使用箇所なし、対応不要）
- HTTP hooks 化（中期検討項目、本 change のスコープ外）
- 既存テレメトリデータの CLAUDE_PLUGIN_DATA への一括マイグレーション（フォールバックで段階移行）

## Decisions

### D1: observe.py の agent_id 取得元
event payload の `agent_id` フィールドを使用する。tool_input にはないため。
usage.jsonl の Agent レコードに `agent_id` フィールドを追加する。

**代替案**: tool_input から subagent_type + prompt のハッシュで擬似 ID を生成する案。
→ 不採用: CC v2.1.69 で event payload に正式な `agent_id` が追加されたため、正規フィールドを使うのが確実。

### D2: worktree フィールドの記録方式
event payload の `worktree` オブジェクトから `name` と `branch` のみを抽出して記録する。
`path` や `original_repo_dir` はフルパスを含むためテレメトリには記録しない。
全 hook に共通で適用するため、`common.py` に `extract_worktree_info(event)` ヘルパーを追加する。
usage.jsonl / errors.jsonl / subagents.jsonl の各レコードに `worktree` フィールドを追加（None 時はキー省略）。

**代替案 A**: worktree オブジェクト全量コピー。→ 不採用: `path`/`original_repo_dir` にフルパスが入り、テレメトリにプライバシー情報が混入するリスク。
**代替案 B**: worktree を boolean フラグのみ記録。→ 不採用: branch 情報が分析に有用（feature branch vs main の使用パターン）。

### D3: InstructionsLoaded hook の処理内容
軽量な検知のみ行う。CLAUDE.md/rules のロードイベントを `sessions.jsonl` に記録し、
trigger_engine の将来的な coherence check トリガーに使える形にする。
新規スクリプト `hooks/instructions_loaded.py` を作成する。

重複防止は `{DATA_DIR}/tmp/instructions_loaded_{session_id}` flag file で行う。
定数: `INSTRUCTIONS_LOADED_FLAG_PREFIX = "instructions_loaded_"`, `STALE_FLAG_TTL_HOURS = 24`（common.py に配置）。
起動時に flag file の mtime を確認し、`STALE_FLAG_TTL_HOURS` 以上古ければ stale として削除してから処理する（クラッシュ時の残存対策）。
エラー時はサイレント失敗（stderr にログ出力、セッションをブロックしない）。既存 hook パターンに準拠。

**代替案 A**: 環境変数でセッション内フラグ管理。→ 不採用: hook は別プロセスで実行されるため環境変数を共有できない。
**代替案 B**: sessions.jsonl を読んで冪等チェック。→ 不採用: ファイル読み込みコストが大きく、レースコンディションのリスクがある。

### D4: plugin validate の統合箇所
README.md のテストセクションに `claude plugin validate` コマンドを追加する。
CI/pre-commit への統合は将来対応（rl-anything は CI 未構築）。

**代替案 A**: pre-commit hook として自動実行。→ 不採用: rl-anything は pre-commit フレームワーク未導入。導入コストに見合わない。
**代替案 B**: GitHub Actions CI に組み込み。→ 不採用: CI 未構築。将来的に CI 構築時に検討。

### D5: StopFailure hook の処理内容
APIエラーによるセッション中断を `errors.jsonl` に記録する。
新規スクリプト `hooks/stop_failure.py` を作成する。
event payload から `error_type`（rate_limit/auth_failure 等）と `error_message` を抽出して記録。
worktree 情報がある場合は同様に付与する。

**代替案**: 既存の `session_summary.py` に統合。→ 不採用: Stop と StopFailure は異なるイベントで、session_summary は正常終了のサマリー生成に特化しており、責務が異なる。

### D6: rl-scorer の maxTurns / disallowedTools
`maxTurns: 15` を設定し、採点が暴走した場合のコスト上限を設ける。
`disallowedTools` に `Edit`, `Write`, `Bash` を設定し、採点エージェントがコードを変更しないことを保証する。
`effort` は未設定（デフォルトのまま）。haiku モデルでは効果が限定的なため。

**代替案 A**: maxTurns を設定しない。→ 不採用: rl-scorer は 3 サブエージェントを起動するため、異常時のコスト増大リスクがある。
**代替案 B**: disallowedTools に Agent も含める。→ 不採用: rl-scorer 自身が 3 サブエージェントを Agent tool で起動するため不可。

### D7: DATA_DIR の CLAUDE_PLUGIN_DATA フォールバック
`common.py` の `DATA_DIR` を以下の優先順で解決する:
1. `${CLAUDE_PLUGIN_DATA}` 環境変数（設定されていれば）
2. `~/.claude/rl-anything/`（従来のフォールバック）

既存データの移行は行わない。新規データは CLAUDE_PLUGIN_DATA に書き込まれ、
読み取り時は両ディレクトリを確認する必要がある箇所は telemetry_query.py 等だが、
Non-Goals のため本 change では対応しない。

**代替案**: 即時全量マイグレーション。→ 不採用: データ量が大きく、マイグレーションスクリプト+テストのコストが高い。段階的移行で十分。

## Risks / Trade-offs

- [worktree フィールドが null の場合] → 非 worktree セッションでは `worktree` キーを省略して JSONL サイズを抑える
- [InstructionsLoaded が高頻度発火する可能性] → session 内で最初の 1 回のみ記録する dedup ガード追加
- [flag file のクラッシュ時残存] → 起動時に mtime ベースの stale 検出（STALE_FLAG_TTL_HOURS=24）で自動削除
- [後方互換] → 新フィールドはすべて optional。既存の telemetry_query / discover / audit は未知フィールドを無視するため影響なし
- [CLAUDE_PLUGIN_DATA 未設定の環境] → フォールバックで従来パスを使用。CC v2.1.78 未満でも動作する
- [rl-scorer disallowedTools] → Agent tool を禁止するとサブエージェント起動が不可能になるため除外が必須
