# System Architecture

> このファイルは SPEC.md から分離された詳細仕様です。
> 概要は [SPEC.md](../SPEC.md) を参照してください。

Last updated: 2026-04-07

## コンポーネント構成

```
hooks/                  ← Observe 層（14個、LLMコストゼロ）[ADR-002]
  common.py             ← scripts/lib/rl_common の re-exporter（後方互換）[ADR-019]
  observe.py            ← usage/errors/corrections 記録
  correction_detect.py  ← corrections 自動検出
  subagent_observe.py   ← subagents.jsonl 記録
  instructions_loaded.py← sessions.jsonl [ADR-015] + Growth greeting（LLMコストゼロ）
  stop_failure.py       ← API エラー記録
  permission_denied.py  ← PermissionDenied hook（CC v2.1.89）errors.jsonl に記録
  save_state.py         ← Compaction 前の作業コンテキスト保存 [ADR-013]
  post_compact.py       ← Compaction 後の作業コンテキスト復元（systemMessage 注入）
  restore_state.py      ← セッション開始時の状態復元
  session_summary.py    ← セッションサマリー記録 + auto_trigger ゲート
  suggest_subagent_delegation.py ← subagent 委譲提案
  workflow_context.py   ← ワークフローコンテキスト記録
  file_changed.py       ← FileChanged hook（CC v2.1.83）CLAUDE.md/SKILL.md/rules 変更検知

bin/                    ← bareコマンド CLI（13個）[ADR-019]
  rl-evolve, rl-audit, rl-discover, rl-prune, rl-reorganize
  rl-reflect, rl-handover, rl-optimize, rl-loop
  rl-backfill, rl-backfill-analyze, rl-backfill-reclassify, rl-audit-aggregate

skills/                 ← スキル定義（22個）
  evolve/               ← 3ステージ自律進化パイプライン
  discover/             ← パターン検出 + スキル候補生成
  reflect/              ← 修正フィードバック反映
  audit/                ← 環境健康診断
  optimize/             ← 直接パッチ最適化
  agent-brushup/        ← エージェント品質診断
  second-opinion/       ← Claude Agent セカンドオピニオン（codex 代替）
  handover/             ← セッション引き継ぎ + Deploy State 構造化 + SPEC.md 同期 + PreCompact 自動提案
  implement/            ← 構造化実装スキル（plan → 実装 → 計画準拠チェック → テレメトリ）

scripts/lib/            ← 共通ロジック（38 モジュール）[ADR-019]
  plugin_root.py        ← PLUGIN_ROOT 定数（depth ハードコード廃止）
  rl_common.py          ← hooks 共通ユーティリティ（DATA_DIR, classify_prompt 等）
  audit.py              ← 環境健康診断ロジック（スキル/ルール/CLAUDE.md 診断）
  discover.py           ← パターン検出 + スキル/ルール候補生成
  prune.py              ← スキル/ルール統廃合候補抽出
  reorganize.py         ← スキル分割候補検出
  remediation.py        ← confidence-based 問題分類 + 修正 + FP排除 + 原則ベース昇格
  telemetry_query.py    ← DuckDB 共通クエリ層
  layer_diagnose.py     ← 4レイヤー診断
  regression_gate.py    ← 共通 regression gate
  skill_triage.py       ← スキルライフサイクル 5択判定
  pitfall_manager.py    ← pitfall 品質ゲート + ライフサイクル
  verification_catalog.py ← 検証知見カタログ
  pipeline_reflector.py ← Self-Evolution コアモジュール
  trigger_engine.py     ← Auto-evolve trigger engine + FileChanged 評価 + userConfig マージ
  agent_quality.py      ← エージェント品質診断
  critical_instruction_extractor.py ← スキル指示の遵守保証（抽出+リフレーズ+違反検出）
  quality_engine.py     ← Skill Quality 2.0（混乱度測定+パターン推奨+スコアボード）
  instruction_patterns.py ← スキル内7パターン自動検出+context効率分析
  semantic_detector.py  ← LLM セマンティック検証（corrections偽陽性除去）
  growth_engine.py      ← NFD Growth Engine（Phase 4段階判定 + 進捗率 + PJ別キャッシュ）
  growth_journal.py     ← 結晶化イベント記録・照会 + git log backfill
  growth_narrative.py   ← 環境プロファイル（性格特性5種）+ 成長ストーリー生成
  （他 15 モジュール: frontmatter, growth_level, skill_evolve, skill_triggers 等）

scripts/rl/fitness/     ← 適応度関数（8個組み込み + config.py で閾値集約）
  config.py             ← 全モジュール共有閾値 + BASE_WEIGHTS
  coherence.py          ← 環境 Coherence Score（4軸）
  telemetry.py          ← テレメトリ駆動 Score（3軸）
  constitutional.py     ← 原則ベース LLM Judge + /cso security 軸
  chaos.py              ← 仮想除去ロバストネス
  environment.py        ← 動的重み統合（_normalize_weights + skill_quality 4軸目）
  skill_quality.py      ← ルールベース構造品質
  principles.py         ← PJ固有原則抽出 + キャッシュ
  plugin.py             ← プラグイン統合 fitness
```

## データフロー

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
      → instruction compliance (corrections × critical指示 → 違反検出 → pitfall学習)
      → growth_engine (Phase判定 → growth-state.json キャッシュ)
        → growth_journal (結晶化イベント記録)
        → growth_narrative (環境プロファイル + 成長ストーリー)
  → InstructionsLoaded hook (growth-state.json → Growth greeting stdout)
```
