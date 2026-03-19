Related: #34

## Why

ワークフロースキル（verify, archive 等）の汎用ステップに、プロジェクト固有のドメインチェックポイントを自動提案する機能が不足している。issue #34 のフィードバックでは、コード変更→CDK定義更新→dev/prodデプロイという一連の流れで「prodデプロイ忘れ」「アーカイブ時のデプロイ確認漏れ」が発生した。現在の `evolve-skill` はスキル単体の自己進化パターン（Pre-flight, pitfalls.md）を提案するが、**プロジェクトのワークフローパターンを分析してドメイン固有チェックポイントを注入する**能力は持っていない。

## What Changes

- **ワークフローチェックポイント検出エンジン**: テレメトリ（workflows.jsonl, corrections.jsonl, errors.jsonl）からワークフロースキルの失敗・修正パターンを分析し、不足しているチェックポイントを特定する
- **チェックポイントテンプレートカタログ**: ドメイン固有チェックポイント（インフラデプロイ確認、データマイグレーション確認、外部API影響確認等）のテンプレート集
- **evolve-skill への統合**: `assess_single_skill()` にワークフロースキル判定 + チェックポイント提案軸を追加
- **discover への統合**: `run_discover()` でワークフローギャップ（チェックポイント不足パターン）を検出・レポート

## Capabilities

### New Capabilities
- `workflow-checkpoint-detection`: ワークフロースキルのチェックポイント不足を検出し、ドメイン固有チェックポイントを提案する機能
- `checkpoint-template-catalog`: ドメイン固有チェックポイントテンプレートのカタログ管理
- `workflow-gap-discovery`: ワークフローギャップ検出を discover に統合（ワークフロースキル走査 + チェックポイント不足レポート）

### Modified Capabilities
- `skill-evolve-assessment`: ワークフロースキル判定軸 + チェックポイント提案を追加

## Impact

- **変更対象コード**: `scripts/lib/skill_evolve.py`, `scripts/lib/verification_catalog.py`（or 新モジュール）, `skills/discover/scripts/discover.py`, `skills/evolve/scripts/evolve.py`, `skills/evolve/scripts/remediation.py`
- **新規モジュール**: `scripts/lib/workflow_checkpoint.py`（チェックポイント検出エンジン + テンプレートカタログ）
- **データソース**: workflows.jsonl, corrections.jsonl, errors.jsonl（既存テレメトリ）
- **issue_schema**: 新定数 `WORKFLOW_CHECKPOINT_CANDIDATE` + factory 関数追加
