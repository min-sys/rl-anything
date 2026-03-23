# SPEC.md — rl-anything

Last updated: 2026-03-24 by /spec-keeper update (feat/gstack-pattern-adoption)

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
| セッション管理 | handover | 作業状態を構造化ノートに書き出し、SPEC.md 同期、別セッションへ引き継ぎ |

### コンポーネント構成

```
hooks/                  ← Observe 層（7個、LLMコストゼロ）[ADR-002]
  common.py             ← PROMPT_CATEGORIES, classify_prompt
  observe.py            ← usage/errors/corrections 記録
  subagent_observe.py   ← subagents.jsonl 記録
  instructions_loaded.py← sessions.jsonl [ADR-015]
  stop_failure.py       ← API エラー記録
  save_state.py         ← Compaction 前の作業コンテキスト保存 [ADR-013]
  restore_state.py      ← セッション開始時の状態復元

skills/                 ← スキル定義（19個）
  evolve/               ← 3ステージ自律進化パイプライン
  discover/             ← パターン検出 + スキル候補生成
  reflect/              ← 修正フィードバック反映
  audit/                ← 環境健康診断
  optimize/             ← 直接パッチ最適化
  agent-brushup/        ← エージェント品質診断
  handover/             ← セッション引き継ぎ + SPEC.md 同期 + PreCompact 自動提案

scripts/lib/            ← 共通ロジック（25+ モジュール）
  telemetry_query.py    ← DuckDB 共通クエリ層
  layer_diagnose.py     ← 4レイヤー診断
  remediation.py        ← confidence-based 問題分類 + 修正 + FP排除 + 原則ベース昇格
  regression_gate.py    ← 共通 regression gate
  skill_triage.py       ← スキルライフサイクル 5択判定
  pitfall_manager.py    ← pitfall 品質ゲート + ライフサイクル
  verification_catalog.py ← 検証知見カタログ
  pipeline_reflector.py ← Self-Evolution コアモジュール
  trigger_engine.py     ← Auto-evolve trigger engine
  agent_quality.py      ← エージェント品質診断

scripts/rl/fitness/     ← 適応度関数（7個組み込み + config.py で閾値集約）
  config.py             ← 全モジュール共有閾値 + BASE_WEIGHTS
  coherence.py          ← 環境 Coherence Score（4軸）
  telemetry.py          ← テレメトリ駆動 Score（3軸）
  constitutional.py     ← 原則ベース LLM Judge + /cso security 軸
  chaos.py              ← 仮想除去ロバストネス
  environment.py        ← 動的重み統合（_normalize_weights + skill_quality 4軸目）
```

### データフロー

```
ユーザー操作
  → Observe hooks (自動記録、LLMコストゼロ)
    → usage.jsonl / errors.jsonl / corrections.jsonl / sessions.jsonl
      → discover (パターン検出)
      → evolve (Diagnose → Compile → Housekeeping)
        → remediation (問題分類 → 修正 → 検証)
      → reflect (corrections → rules/CLAUDE.md 反映)
      → audit (環境健康診断)
      → optimize (直接パッチ → regression gate)
```

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
| `/rl-anything:handover` | セッション作業状態の構造化ノート書き出し | low |
| `/rl-anything:version` | バージョン・ステータス表示 | low |
| `/rl-anything:feedback` | フィードバック送信 | low |

### 適応度関数

組み込み7個: `default`, `skill_quality`, `coherence`, `telemetry`, `constitutional`（+ /cso security軸）, `chaos`, `environment`（動的重み、`config.py` で閾値集約）
PJ固有: `scripts/rl/fitness/{name}.py` に配置 → `--fitness {name}`

## Key Design Decisions

全18件。詳細は [docs/decisions/](docs/decisions/) を参照。

- **配布・観測**: Plugin 配布 ([001](docs/decisions/001-plugin-distribution-model.md)), hooks+JSONL ([002](docs/decisions/002-observe-hooks-jsonl-architecture.md)), hook enrichment ([015](docs/decisions/015-hook-agent-enrichment.md))
- **パイプライン**: GA廃止→直接パッチ ([003](docs/decisions/003-direct-patch-over-genetic-algorithm.md)), 全レイヤー診断/Compile ([007](docs/decisions/007-all-layer-diagnose-adapter-pattern.md), [008](docs/decisions/008-all-layer-compile-dispatch-pattern.md)), 3ステージ簡素化 ([009](docs/decisions/009-simplify-pipeline-3-stage.md)), スキル自己進化 ([016](docs/decisions/016-skill-self-evolution-pattern.md), [017](docs/decisions/017-evolve-skill-independent-command.md))
- **評価・スコアリング**: Coherence 4軸 ([004](docs/decisions/004-coherence-score-4-axes.md)), Telemetry ([005](docs/decisions/005-telemetry-score-architecture.md)), Constitutional Judge ([006](docs/decisions/006-constitutional-eval-llm-judge.md)), CoT除去 ([018](docs/decisions/018-evaluate-pipeline-cot-removal.md))
- **運用・自動化**: Auto trigger ([010](docs/decisions/010-auto-evolve-trigger-engine.md), [011](docs/decisions/011-auto-compression-trigger.md)), Self-Evolution EWA ([012](docs/decisions/012-self-evolution-trajectory-ewa.md)), Compaction復元 ([013](docs/decisions/013-compaction-state-recovery.md)), CC v2適用 ([014](docs/decisions/014-adopt-claude-code-v2-features.md))

## Recent Changes

直近5件のみ。過去の変更は [CHANGELOG.md](CHANGELOG.md) を参照。

- 2026-03-24: gstack v0.10-v0.11 改善パターン6項目移植 — 独立検証、FP排除(12条件)、規模適応、fitness config.py集約、動的重み、/cso×fitness連携、/retro×audit cross-project、原則ベース昇格
- 2026-03-23: handover に SPEC.md 同期ステップ追加（`/spec-keeper update` を自動実行）
- 2026-03-22: v1.13.0 — 検証系スキルのテレメトリ非依存昇格
- 2026-03-22: v1.12.0 — handover スキル追加 + OpenSpec→gstack 移行 Phase 1-2
- 2026-03-20: agent-brushup スキル追加（品質診断 + upstream 監視）

## Current Limitations / Known Issues

- Subagents レイヤーの観測・測定・進化は未着手（roadmap 参照）
- CLAUDE.md レイヤーの進化は reflect 反映のみ（自動修正なし）
- openspec/specs/ は機能仕様のみ（ADR 変換対象なし）。ディレクトリはアーカイブとして残存
- audit の CLAUDE.md line_limit_violation は warning_only

## Next

- gstack 改善移植の残り: Agent 3 の cross-project audit を evolve パイプラインに統合（PR #38 で基盤完了、evolve 内での呼び出し統合は次 PR）
- Subagents レイヤーの進化メカニズム（roadmap Phase 3）
- 6レイヤー全体の自律進化ループ完成（roadmap To-be）
