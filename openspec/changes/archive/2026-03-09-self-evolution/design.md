Related: #21

## Context

現在の evolve パイプライン（Diagnose → Compile → Housekeeping）は環境の6レイヤーを診断・修正するが、パイプライン自身の改善は行わない。remediation-outcomes.jsonl に修正結果を記録しているものの、そのデータを活用して confidence_score の精度向上やパス順序の最適化を行う仕組みがない。

Gap 2 Phase 3（全層 Compile）完了により、全レイヤーの FIX_DISPATCH/VERIFY_DISPATCH が整備済み。この基盤の上に、パイプライン自身のメタ改善ループを構築する。

**既存資産**:
- `remediation-outcomes.jsonl` — 修正結果（success/skipped/rejected + confidence_score + issue_type）
- `evolve-state.json` — 実行履歴 + trigger_history
- `remediation.py` の `compute_confidence_score()` — 静的な閾値ベース
- `trigger_engine.py` — 4条件のトリガー評価

**Data Flow**:
```
pipeline-trajectory-analysis（分析・集計）
  → confidence-calibration（calibrated confidence 算出）
    → adaptive-pipeline-config（提案ラッピング + risk assessment）
```

## Goals / Non-Goals

**Goals:**
- evolve 実行履歴から false positive（高 confidence だが reject された修正）と false negative（低 confidence だが実際は安全な修正）を検出する
- confidence_score の算出パラメータを実績データで自動キャリブレーションする提案を生成する
- パイプラインの健全性メトリクス（precision, recall, approval_rate）を audit レポートに表示する
- false positive 蓄積時に self-evolution を自動トリガーする

**Non-Goals:**
- confidence_score の自動適用（提案のみ、人間承認が必須）
- E3 Interleaved Multi-Layer Optimization（Phase 5 Graduated Autonomy の領域）
- E9 Market-Based Allocation（運用データ蓄積後の将来課題）
- remediation の fix 関数自体の自動生成
- Low recall 検出の corrections.jsonl 統合（D1 のスコープ外。corrections.jsonl 統合は future iteration で対応）

## Decisions

### D1: Trajectory Analysis は remediation-outcomes.jsonl のみを入力とする

**選択肢**:
- A) sessions.jsonl + usage.jsonl + corrections.jsonl + remediation-outcomes.jsonl の全テレメトリを分析
- B) remediation-outcomes.jsonl のみを分析

**決定**: B を採用。

**理由**: self-evolution のスコープは「パイプライン自身の改善」であり、remediation-outcomes.jsonl がパイプラインの直接的な実績データ。全テレメトリの分析は E1 Reflective Trajectory の完全実装に相当し、スコープが広すぎる。段階的に拡張可能。

### D2: Confidence キャリブレーションは EWA（指数加重平均）方式

**選択肢**:
- A) Linear Delta 方式: `calibrated = current * approval_rate + (1 - approval_rate) * base` — ad-hoc、sample size 未考慮
- B) EWA 方式: `calibrated = α * observed_approval_rate + (1 - α) * current_confidence` where `α = min(sample_size / CALIBRATION_SAMPLE_THRESHOLD, MAX_CALIBRATION_ALPHA)` (defaults: `CALIBRATION_SAMPLE_THRESHOLD`=30, `MAX_CALIBRATION_ALPHA`=0.7)

**決定**: B を採用。

**理由**: Linear Delta は sample size を考慮しないため、少数データで過剰に振れる。EWA は小サンプル時に α が小さく prior（current_confidence）に寄り、データ蓄積で observed に収束する。scikit-learn docs の Platt/isotonic は 1000+ samples 向けであり、少数データには EWA が適切。統計ライブラリ依存なし。

```python
# EWA 方式の例
# stale_ref: current_confidence=0.95, observed_approval_rate=0.70, sample_size=15
# α = min(15 / 30, 0.7) = 0.5
# calibrated = 0.5 * 0.70 + 0.5 * 0.95 = 0.825
```

### D3: Pipeline Health メトリクスは audit の既存フレームワーク内

**選択肢**:
- A) 独立した `/rl-anything:pipeline-health` コマンドを新設
- B) audit レポートの新セクションとして追加

**決定**: B を採用。

**理由**: audit は既に Coherence/Telemetry/Constitutional の3スコアセクションを持つ。Pipeline Health を4つ目のセクションとして追加するのが自然。新コマンド増加を避ける。

### D4: Self-evolution フェーズは Compile ステージ内の Phase 6

**選択肢**:
- A) evolve の新ステージ（4ステージ目）として追加
- B) Compile ステージの既存 Phase 列（Fitness Evolution = Phase 5）の後に Phase 6 として追加
- C) 独立スキルとして実装

**決定**: B を採用。

**理由**: self-evolution は evolve パイプラインのメタ改善であり、Compile ステージの「パッチ生成・修正」の延長線上にある。既存の compile-stage spec に delta spec として追加し、3ステージ構成を維持する。

### D5: モジュール配置

**選択肢**:
- A) `skills/evolve/scripts/remediation.py` を拡張 — 却下（795行で肥大、関心分離違反）
- B) `scripts/lib/pipeline_reflector.py` に新規作成 — 採用（`telemetry_query.py`/`trigger_engine.py` と同パターン、evolve + audit 共有可能）
- C) `skills/evolve/scripts/pipeline_reflector.py` に配置 — 却下（audit からの import が cross-skill 依存）

**決定**: B を採用。

**理由**: `scripts/lib/` は evolve と audit の両方から参照される共有モジュールの配置場所として確立されたパターン（`telemetry_query.py`, `trigger_engine.py`, `layer_diagnose.py` 等）。

### D6: 閾値の外部化

Self-evolution に関連する全閾値を `evolve-state.json` の `trigger_config.self_evolution` に格納し、`load_self_evolution_config()` でロードする（既存 `load_trigger_config()` パターン準拠）。

**閾値一覧**:

| 定数名 | デフォルト値 | 用途 |
|--------|-------------|------|
| `MIN_OUTCOMES_FOR_ANALYSIS` | 20 | Trajectory Analysis の最小 outcome 件数 |
| `MIN_OUTCOMES_PER_TYPE` | 10 | issue_type 別 calibration の最小件数 |
| `CALIBRATION_SAMPLE_THRESHOLD` | 30 | EWA の α 収束閾値 |
| `MAX_CALIBRATION_ALPHA` | 0.7 | EWA の α 上限 |
| `FALSE_POSITIVE_RATE_THRESHOLD` | 0.3 | false positive 警告閾値 |
| `APPROVAL_RATE_HEALTHY_THRESHOLD` | 0.8 | 健全判定の承認率閾値 |
| `APPROVAL_RATE_DEGRADED_THRESHOLD` | 0.7 | DEGRADED 判定の承認率閾値 |
| `APPROVAL_RATE_DECLINE_THRESHOLD` | 0.2 | 承認率低下トリガーの変化量閾値 |
| `SELF_EVOLUTION_COOLDOWN_HOURS` | 72 | self-evolution トリガーのクールダウン |
| `DECLINE_SAMPLE_SIZE` | 10 | 承認率低下判定のサンプルサイズ |
| `REGRESSION_FP_INCREASE_THRESHOLD` | 0.1 | 回帰検出の false positive 増加閾値 |
| `ANALYSIS_LOOKBACK_DAYS` | 30 | トリガー評価の分析対象期間（日数） |
| `SYSTEMATIC_REJECTION_THRESHOLD` | 3 | systematic rejection 判定の連続 reject 件数 |
| `MINOR_LINE_EXCESS` | 2 | 軽微な行数超過と判定する超過行数上限 |

**格納先**: `evolve-state.json`
```json
{
  "trigger_config": {
    "self_evolution": {
      "min_outcomes_for_analysis": 20,
      "calibration_sample_threshold": 30,
      "max_calibration_alpha": 0.7,
      "false_positive_rate_threshold": 0.3,
      ...
    }
  }
}
```

## Risks / Trade-offs

- **[データ不足]** → remediation-outcomes.jsonl のレコードが少ない段階では精度が低い。`MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件の outcome を要件とし、不足時はスキップ。
- **[過剰適合]** → 少数データでの EWA 調整が偏る可能性。管理図（μ ± 2σ）範囲外の Delta は警告付きで提案し、2σ 超えは manual_required に格上げ。
- **[false positive 連鎖]** → confidence 調整が新たな false positive を生む可能性。check_regression() を適用し、調整後の confidence で既存 outcomes を再評価して回帰チェック。
- **[LLM コスト]** → Trajectory Analysis の LLM 呼び出し。remediation-outcomes.jsonl の集計は Python のみ（コストゼロ）。LLM は自然言語診断生成時のみ使用し、audit --pipeline-health は集計のみで LLM 不要。
