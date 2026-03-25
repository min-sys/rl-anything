# ADR-012: Self-Evolution with Trajectory Analysis and EWA Calibration

Date: 2026-03-09
Status: Accepted

## Context

evolve パイプライン（Diagnose / Compile / Housekeeping）はユーザーの環境を改善するが、パイプライン自身の改善は行っていなかった。remediation-outcomes.jsonl に修正結果を記録しているものの、そのデータを活用して confidence_score の精度向上やパス順序の最適化を行う仕組みがなく、同じ誤検出や不適切な提案を繰り返す状態だった。全層 Compile（Gap 2 Phase 3）完了により FIX_DISPATCH/VERIFY_DISPATCH が整備済みで、パイプライン自身のメタ改善ループを構築する基盤が整った。

## Decision

- **Trajectory Analysis は remediation-outcomes.jsonl のみを入力とする**: 全テレメトリ（sessions/usage/corrections）の分析はスコープが広すぎるため、パイプラインの直接的な実績データに限定。段階的に拡張可能
- **Confidence キャリブレーションに EWA（指数加重平均）方式を採用**: `calibrated = alpha * observed_approval_rate + (1 - alpha) * current_confidence` where `alpha = min(sample_size / 30, 0.7)`。小サンプル時は prior（current_confidence）に寄り、データ蓄積で observed に収束。統計ライブラリ依存なし
- **Pipeline Health メトリクスは audit レポートの新セクションとして追加**: 独立コマンドではなく既存の audit フレームワーク内に統合。remediation-outcomes.jsonl の集計のみで LLM 不使用
- **Self-evolution フェーズは Compile ステージ内の Phase 6 として追加**: 3ステージ構成を維持しつつ、既存 Phase 列（Fitness Evolution = Phase 5）の後に配置
- **モジュールは `scripts/lib/pipeline_reflector.py` に新規作成**: `scripts/lib/` は evolve と audit の両方から参照される共有モジュールの確立されたパターン
- **14の閾値定数を `evolve-state.json` の `trigger_config.self_evolution` に外部化**: MIN_OUTCOMES_FOR_ANALYSIS=20, CALIBRATION_SAMPLE_THRESHOLD=30, MAX_CALIBRATION_ALPHA=0.7, FALSE_POSITIVE_RATE_THRESHOLD=0.3, APPROVAL_RATE_HEALTHY_THRESHOLD=0.8 等
- **false positive 蓄積時と承認率低下時に self-evolution を自動トリガー**: trigger_engine に self-evolution 条件を追加（72h クールダウン）

## Alternatives Considered

- **Linear Delta 方式（`calibrated = current * approval_rate + (1 - approval_rate) * base`）**: sample size を考慮しないため少数データで過剰に振れる。EWA は小サンプル時に alpha が小さく安定するため採用
- **Platt scaling / Isotonic regression（scikit-learn）**: 1000+ サンプル向けであり、少数データの evolve には不適切。統計ライブラリ依存も避けたい
- **独立した `/pipeline-health` コマンドを新設**: audit が既に3スコアセクションを持ち、新コマンド増加を避けるため audit セクション追加を選択
- **evolve の4ステージ目として追加**: self-evolution は Compile の延長線上にあり、3ステージ構成を維持するため Phase 6 として統合
- **`remediation.py` を拡張**: 795行で肥大化しており関心分離違反のため却下
- **`skills/evolve/scripts/` に配置**: audit からの import が cross-skill 依存になるため `scripts/lib/` を選択

## Consequences

**良い影響:**
- パイプラインが実績データから学習し、confidence_score の精度が運用とともに向上する
- false positive の自動検出と閾値キャリブレーションにより、不適切な提案の繰り返しが減少する
- Pipeline Health メトリクス（precision, approval_rate, false positive rate）により、パイプラインの健全性が可視化される
- 管理図（mu +/- 2sigma）で過剰な調整を検出し、回帰チェックで安全性を担保

**悪い影響:**
- remediation-outcomes.jsonl のレコードが少ない段階（MIN_OUTCOMES_FOR_ANALYSIS=20 未満）では機能しない
- 少数データでの EWA 調整が偏る可能性がある（管理図範囲外の Delta は manual_required に格上げして緩和）
- confidence 調整が新たな false positive を生む連鎖リスクがある（check_regression() で調整後の confidence による再評価を実施して緩和）
