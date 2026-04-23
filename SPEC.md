# SPEC.md — rl-anything

Last updated: 2026-04-23 by /spec-keeper update

## Overview

Claude Code Plugin。スキル/ルールの **自律進化パイプライン**、**修正フィードバックループ**、**直接パッチ最適化** を提供する。AI がセッション中に蓄積した使用データ・エラー・修正パターンを基に、スキル/ルール/メモリ/CLAUDE.md を自律的に改善する。

対象ユーザー: Claude Code を日常的に使い、スキル/ルール環境を継続的に改善したい開発者。

## Tech Stack

- **言語**: Python 3 (hooks, scripts), Markdown (skills, rules)
- **配布**: Claude Code Plugin (`claude plugin install`)
- **テレメトリ**: JSONL ファイル (usage/errors/corrections/sessions/workflows.jsonl)
- **クエリ**: DuckDB (JSONL→SQL、未インストール時は Python フォールバック)
- **テスト**: pytest
- **CI**: `claude plugin validate`

## System Architecture

### 4つの柱

| 柱 | スキル | 説明 |
|----|--------|------|
| 自律進化 | evolve, discover, reorganize, prune, audit | Observe → Diagnose → Compile → Housekeeping → Report の3ステージパイプライン ([ADR-009](docs/decisions/009-simplify-pipeline-3-stage.md)) |
| フィードバック | reflect | 修正パターン検出 → corrections.jsonl → CLAUDE.md/rules に反映 |
| 直接パッチ最適化 | optimize, rl-loop, generate-fitness, evolve-fitness | GA廃止、LLM 1パス直接パッチ ([ADR-003](docs/decisions/003-direct-patch-over-genetic-algorithm.md)) → regression gate |
| **fleet 観測・介入** | fleet (`bin/rl-fleet`) | 全 PJ 横断で env_score / 導入状況を単一コマンドで可視化、Phase 分け実装（Phase 1: `status`）([ADR-022](docs/decisions/022-fleet-observation-plus-intervention.md)) |
| エージェント管理 | agent-brushup | エージェント定義の品質診断・改善提案・upstream 監視 |
| セカンドオピニオン | second-opinion | Claude Agent による cold-read 独立見解（codex 代替、3モード） |
| セッション管理 | handover | 作業状態を構造化ノートに書き出し（ローカルファイル or GitHub Issue）、SPEC.md 同期、別セッションへ引き継ぎ |
| 仕様管理 | spec-keeper | SPEC.md + ADR の管理、Progressive Disclosure L1/L2 自動昇格 |
| 哲学原則レビュー | philosophy-review | Claude Code native セッション履歴を Judge LLM で評価し、`category: "philosophy"` 原則の違反例を corrections.jsonl に注入 ([ADR-020](docs/decisions/020-philosophy-seed-distribution.md)) |
| **成長可視化 (NFD)** | audit --growth | NFD 論文ベースの Spiral Development Model — 4フェーズ自動判定 + Lv.1-10 レベルシステム + 環境プロファイル（5 traits）+ 成長ストーリー |
| 後片付け | cleanup | PR マージ・デプロイ後の痕跡（マージ済みブランチ / remote refs / 一時 worktree / 一時ディレクトリ / 関連 Issue close 候補 / PR Test plan 残件）を候補提示→`AskUserQuestion` 個別承認→実行で安全処理。一時ディレクトリ default prefix は `rl-anything-` のみに限定 ([ADR-021](docs/decisions/021-cleanup-tmp-dir-prefix-safety.md))、`CLAUDE_PLUGIN_OPTION_cleanup_tmp_prefixes` / userConfig で拡張可能 |

「4本目の柱」は fleet 観測・介入としての rl-anything 拡張。per-PJ 自己進化から fleet 自己進化への昇格（[ADR-022](docs/decisions/022-fleet-observation-plus-intervention.md)）。

Observe hooks (14個, LLMコストゼロ) → テレメトリ JSONL → evolve/discover/reflect/audit → remediation → 自動改善。
スキル24個、共通ロジック42モジュール（fleet 含む）、bin/ コマンド15個（`rl-fleet` 追加）、適応度関数8個組み込み（`default` / `skill_quality` / `coherence` / `telemetry` / `constitutional` / `chaos` / `environment` / `plugin`）。

コンポーネント構成・データフローの詳細は [spec/architecture.md](spec/architecture.md) を参照。

## API / Interface Spec

スキルコマンド一覧・適応度関数の詳細は [spec/api.md](spec/api.md) を参照。

主要コマンド: `/rl-anything:evolve`（日次）, `/rl-anything:audit`（診断）, `/rl-anything:reflect`（フィードバック反映）, `/rl-anything:optimize <skill>`（直接パッチ）

## Key Design Decisions

全22件。カテゴリ別要約は [spec/architecture.md#key-design-decisions-カテゴリ別サマリ](spec/architecture.md#key-design-decisions-カテゴリ別サマリ)、原文は [docs/decisions/](docs/decisions/) を参照。

## Recent Changes

直近5件のみ。過去の変更は [CHANGELOG.md](CHANGELOG.md) を参照。

- 2026-04-23: **fleet Phase 1 — `bin/rl-fleet status` CLI** — 全 PJ 横断の健康状態可視化を「4 本目の柱」として追加（[ADR-022](docs/decisions/022-fleet-observation-plus-intervention.md)）。`scripts/lib/fleet.py` に 5 コア関数（`enumerate_projects` / `classify_project` ハイブリッド 3 値判定 / `run_audit_subprocess` TIMEOUT/ERROR 区別 / `format_status_table` / `resolve_auto_memory_dir`）+ `collect_fleet_status` 並列化（`ThreadPoolExecutor(max_workers=2)`）+ fleet-run 履歴追記。post-review で HIGH 2 + MED 3 件の edge case 修正（duplicate basename cache 衝突ガード / argv `--` 分離 / subprocess grandchildren kill / CLAUDE_PLUGIN_DATA 動的解決 / symlink 除外）。33 unit tests（closes #68 Phase 1, PR #83）
- 2026-04-22: **cleanup: tmp prefix userConfig 化** — `manifest.userConfig` に `cleanup_tmp_prefixes` (string, カンマ区切り, default `"rl-anything-"`) を追加。`scripts/lib/cleanup_scanner.py::parse_prefix_config` で list 化（trim / 空要素除去 / 重複排除 / `None` 許容）。SKILL.md 実行時に `[cleanup] tmp scan scope: [...]` を宣言表示し、scanner 側 `_DEFAULT_TMP_EXCLUDE_PATTERNS` の defense-in-depth は常時有効（closes #71）
- 2026-04-22: **audit: DATA_DIR を rl_common に統一（fleet blocker 解消）** — `scripts/lib/audit.py` の DATA_DIR 独自解決を廃止し `rl_common` の共通実装に統一。fleet 構想 (#68) で前提となる PJ 間データ境界の一貫性を確保。リグレッションテスト 108 行追加（refs #68）
- 2026-04-22: **cleanup スキル新設 + tmp prefix 安全設計** — `/rl-anything:cleanup` を追加し、PR マージ/デプロイ後の後片付け 6 カテゴリを候補提示→個別承認→実行で処理。同 PR の dogfood で wide prefix が Claude Code runtime (`/tmp/claude-<uid>`) / MCP bridge (`/tmp/claude-mcp-*`) を削除候補化する critical バグを検出し、default prefix を `rl-anything-` のみに narrow + scanner に `_DEFAULT_TMP_EXCLUDE_PATTERNS` の安全ネットを追加 ([ADR-021](docs/decisions/021-cleanup-tmp-dir-prefix-safety.md))。24 tests (closes #69, refs #71)
- 2026-04-17: **Stop hook を rl-scorer/second-opinion agent に追加** — CC v2.1.116 で agent frontmatter `hooks:` が `--agent` 経由でも発火するようになったため、`subagent_observe.py` を Stop フックとして agent 定義に追加。main-thread 起動時もテレメトリが記録される

## Current Limitations / Known Issues

- Subagents レイヤーの観測・測定・進化は未着手（roadmap 参照）
- CLAUDE.md レイヤーの進化は reflect 反映のみ（自動修正なし）
- openspec/specs/ は機能仕様のみ（ADR 変換対象なし）。ディレクトリはアーカイブとして残存
- audit の CLAUDE.md line_limit_violation は warning_only

## Next

- fleet Phase 2: `bin/rl-fleet audit-all [--parallel N]` + global rules (`~/.claude/rules/*.md`) × PJ CLAUDE.md の名前衝突検出（意味的矛盾は Phase 4+）
- fleet Phase 3: `reflect-all` / `evolve-all` を dry-run default + `--apply` で実装、`rollback <ts>` + PJ 単位 opt-in マーカー必須（[ADR-022](docs/decisions/022-fleet-observation-plus-intervention.md)）
- fleet perf 最適化: Phase 1 実測 12.9s / 7 PJ（設計目標 3s）。`growth-state-<slug>.json` 直読みキャッシュ経路を Phase 2 で検討
- `audit.py` duckdb `usage.jsonl` クエリの `Conversion Error: Malformed JSON` 根本修正（fleet が AUDIT_ERROR として surface する既存バグ）
- Subagents レイヤーの進化メカニズム（roadmap Phase 3）
- 6レイヤー全体の自律進化ループ完成（roadmap To-be）
