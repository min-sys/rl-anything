Related: #21

## Why

現在の evolve パイプライン（Diagnose → Compile → Housekeeping）は **ユーザーの環境** を改善するが、**パイプライン自身** は改善しない。evolve が検出した問題パターンやユーザーの accept/reject 履歴から「次回はどう診断・修正すべきか」を学習する仕組みがなく、同じ誤検出や不適切な提案を繰り返す。Gap 2 Phase 3（全層 Compile）が完了した今、パイプラインの自己改善に取り組むべきタイミングである。

## What Changes

- **Reflective Trajectory Analysis**: evolve 実行履歴（remediation-outcomes.jsonl + accept/reject）を分析し、パイプラインの弱点を自然言語で診断する（E1 パターン）
- **Adaptive Pipeline Configuration**: 診断結果に基づいて evolve のパラメータ（閾値、パス順序、重み）を自動調整する提案を生成する（E7 + E8 パターン）
- **Reconciliation Feedback Loop**: remediation の fix 成功率・false positive 率を追跡し、confidence_score の算出ロジックを自動キャリブレーションする（E2 パターン）
- **Pipeline Health Dashboard**: evolve 自身の健全性メトリクス（精度、再現率、ユーザー承認率）を audit レポートに追加

## Capabilities

### New Capabilities
- `pipeline-trajectory-analysis`: evolve 実行履歴を反省し、パイプラインの弱点・改善ポイントを自然言語で診断する
- `adaptive-pipeline-config`: 診断結果に基づいてパイプラインパラメータ（閾値・順序・重み）の調整提案を生成する
- `confidence-calibration`: remediation outcomes の実績データから confidence_score 算出ロジックを自動キャリブレーションする

### Modified Capabilities
- `remediation-engine`: outcome 記録フォーマットを拡張し、fix 成功/失敗の詳細メタデータを追加
- `audit-report`: パイプライン健全性セクションを追加（精度・承認率・false positive 率）
- `evolve-trigger-engine`: self-evolution トリガー条件を追加（承認率低下・false positive 蓄積時）
- `compile-stage`: self-evolution フェーズを Phase 6 として追加（trajectory analysis → calibration 提案 → ユーザー確認）

## Impact

- `skills/evolve/scripts/evolve.py` — self-evolution フェーズの追加
- `skills/evolve/scripts/remediation.py` — outcome 記録の拡張 + confidence キャリブレーション
- `skills/audit/scripts/audit.py` — pipeline health セクション追加
- `scripts/lib/trigger_engine.py` — self-evolution トリガー追加
- 新規: `scripts/lib/pipeline_reflector.py` — トラジェクトリ分析 + パラメータ調整提案
- 依存: `remediation-outcomes.jsonl`（既存）、`evolve-state.json`（既存）
