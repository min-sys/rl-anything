# SPEC.md — rl-anything

Last updated: 2026-03-27 by /spec-keeper update (v1.19.0)

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

### 3つの柱

| 柱 | スキル | 説明 |
|----|--------|------|
| 自律進化 | evolve, discover, reorganize, prune, audit | Observe → Diagnose → Compile → Housekeeping → Report の3ステージパイプライン ([ADR-009](docs/decisions/009-simplify-pipeline-3-stage.md)) |
| フィードバック | reflect | 修正パターン検出 → corrections.jsonl → CLAUDE.md/rules に反映 |
| 直接パッチ最適化 | optimize, rl-loop, generate-fitness, evolve-fitness | GA廃止、LLM 1パス直接パッチ ([ADR-003](docs/decisions/003-direct-patch-over-genetic-algorithm.md)) → regression gate |
| エージェント管理 | agent-brushup | エージェント定義の品質診断・改善提案・upstream 監視 |
| セカンドオピニオン | second-opinion | Claude Agent による cold-read 独立見解（codex 代替、3モード） |
| セッション管理 | handover | 作業状態を構造化ノートに書き出し（ローカルファイル or GitHub Issue）、SPEC.md 同期、別セッションへ引き継ぎ |
| 仕様管理 | spec-keeper | SPEC.md + ADR の管理、Progressive Disclosure L1/L2 自動昇格 |
| **成長可視化 (NFD)** | audit --growth | NFD 論文ベースの Spiral Development Model — 4フェーズ自動判定 + Lv.1-10 レベルシステム + 環境プロファイル（5 traits）+ 成長ストーリー |

Observe hooks (11個, LLMコストゼロ) → テレメトリ JSONL → evolve/discover/reflect/audit → remediation → 自動改善。
スキル21個、共通ロジック31モジュール、適応度関数8個組み込み。

コンポーネント構成・データフローの詳細は [spec/architecture.md](spec/architecture.md) を参照。

## API / Interface Spec

### スキルコマンド

| コマンド | 説明 | effort |
|----------|------|--------|
| `/rl-anything:evolve` | 3ステージ自律進化パイプライン（日次運用） | high |
| `/rl-anything:discover` | パターン検出 + スキル/ルール候補生成 | medium |
| `/rl-anything:reflect` | corrections → CLAUDE.md/rules 反映 | medium |
| `/rl-anything:audit` | 環境健康診断レポート | medium |
| `/rl-anything:optimize <skill>` | 特定スキルの直接パッチ最適化 | high |
| `/rl-anything:rl-loop` | 自律進化ループオーケストレーター | high |
| `/rl-anything:agent-brushup` | エージェント品質診断 | medium |
| `/rl-anything:evolve-skill <skill>` | 特定スキルに自己進化パターン組み込み | medium |
| `/rl-anything:generate-fitness` | PJ固有 fitness 関数自動生成 | medium |
| `/rl-anything:evolve-fitness` | 評価関数キャリブレーション | medium |
| `/rl-anything:second-opinion` | Claude Agent セカンドオピニオン（startup/builder/general） | low |
| `/rl-anything:handover` | セッション作業状態の構造化ノート書き出し | low |
| `/rl-anything:version` | バージョン・ステータス表示 | low |
| `/rl-anything:spec-keeper` | SPEC.md + ADR 管理（init/update/adr/status） | medium |
| `/rl-anything:feedback` | フィードバック送信 | low |

### 適応度関数

組み込み8個: `default`, `skill_quality`, `coherence`, `telemetry`, `constitutional`（+ /cso security軸）, `chaos`, `environment`（動的重み）, `plugin`（プラグイン統合）。`config.py` で閾値集約
PJ固有: `scripts/rl/fitness/{name}.py` に配置 → `--fitness {name}`

## Key Design Decisions

全18件。詳細は [docs/decisions/](docs/decisions/) を参照。

- **配布・観測**: Plugin 配布 ([001](docs/decisions/001-plugin-distribution-model.md)), hooks+JSONL ([002](docs/decisions/002-observe-hooks-jsonl-architecture.md)), hook enrichment ([015](docs/decisions/015-hook-agent-enrichment.md))
- **パイプライン**: GA廃止→直接パッチ ([003](docs/decisions/003-direct-patch-over-genetic-algorithm.md)), 全レイヤー診断/Compile ([007](docs/decisions/007-all-layer-diagnose-adapter-pattern.md), [008](docs/decisions/008-all-layer-compile-dispatch-pattern.md)), 3ステージ簡素化 ([009](docs/decisions/009-simplify-pipeline-3-stage.md)), スキル自己進化 ([016](docs/decisions/016-skill-self-evolution-pattern.md), [017](docs/decisions/017-evolve-skill-independent-command.md))
- **評価・スコアリング**: Coherence 4軸 ([004](docs/decisions/004-coherence-score-4-axes.md)), Telemetry ([005](docs/decisions/005-telemetry-score-architecture.md)), Constitutional Judge ([006](docs/decisions/006-constitutional-eval-llm-judge.md)), CoT除去 ([018](docs/decisions/018-evaluate-pipeline-cot-removal.md))
- **運用・自動化**: Auto trigger ([010](docs/decisions/010-auto-evolve-trigger-engine.md), [011](docs/decisions/011-auto-compression-trigger.md)), Self-Evolution EWA ([012](docs/decisions/012-self-evolution-trajectory-ewa.md)), Compaction復元 ([013](docs/decisions/013-compaction-state-recovery.md)), CC v2適用 ([014](docs/decisions/014-adopt-claude-code-v2-features.md))

## Recent Changes

直近5件のみ。過去の変更は [CHANGELOG.md](CHANGELOG.md) を参照。

- 2026-03-27: v1.19.0 — **handover Issue モード** — `--issue` フラグで GitHub Issue として引き継ぎノートを作成可能に。GitHub リポ検出時は自動提案
- 2026-03-26: v1.18.0 — **NFD Level System** — env_score → Lv.1-10 + 称号。η計算修正、Fast Shipper trait、evolve フェーズ降格防止、audit がキャッシュ唯一権威に
- 2026-03-26: v1.17.2 — **worktree 並行開発パターン提案** — discover の RECOMMENDED_ARTIFACTS に worktree-parallel-work + deploy-lock を追加。未導入 PJ に自動提案
- 2026-03-26: v1.17.0 — spec-keeper 同梱 + Progressive Disclosure L2 レイヤー
- 2026-03-26: v1.16.0 — **NFD Living Agent Identity** — Spiral Development Model + Growth greeting + 環境プロファイル

## Current Limitations / Known Issues

- Subagents レイヤーの観測・測定・進化は未着手（roadmap 参照）
- CLAUDE.md レイヤーの進化は reflect 反映のみ（自動修正なし）
- openspec/specs/ は機能仕様のみ（ADR 変換対象なし）。ディレクトリはアーカイブとして残存
- audit の CLAUDE.md line_limit_violation は warning_only

## Next

- gstack 改善移植の残り: Agent 3 の cross-project audit を evolve パイプラインに統合（PR #38 で基盤完了、evolve 内での呼び出し統合は次 PR）
- Subagents レイヤーの進化メカニズム（roadmap Phase 3）
- 6レイヤー全体の自律進化ループ完成（roadmap To-be）
