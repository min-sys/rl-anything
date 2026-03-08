## ADDED Requirements

### Requirement: Chaos Score computation via virtual ablation
`chaos.py` の `compute_chaos_score()` は各構成要素を仮想的に除去（ファイル内容を空として扱う）して Coherence Score を再計算し、ΔScore（除去時のスコア低下量）から環境の堅牢性を測定しなければならない（MUST）。実ファイルを変更してはならない（MUST NOT）。

#### Scenario: Rule 除去の影響測定
- **WHEN** 5 つの Rules が存在し、Rule A を仮想除去して Coherence Score を再計算する
- **THEN** ΔScore（ベースラインとの差分）が算出され、Rule A の重要度ランキングに反映される

#### Scenario: 実ファイルの安全性
- **WHEN** `compute_chaos_score()` を実行する
- **THEN** `.claude/rules/` 配下のファイルは一切変更されない

### Requirement: Importance ranking
`compute_chaos_score()` は全構成要素の ΔScore を降順でランキングし、返却 dict に `importance_ranking` として含めなければならない（MUST）。各エントリに `name`, `layer`, `delta_score`, `criticality`（critical/important/low のいずれか）を含めなければならない（MUST）。criticality の判定は `THRESHOLDS` dict を参照する:
- `delta_score >= THRESHOLDS["critical_delta"]` (0.10) → critical
- `THRESHOLDS["low_delta"]` (0.02) <= `delta_score` < `THRESHOLDS["critical_delta"]` → important
- `delta_score < THRESHOLDS["low_delta"]` (0.02) → low

```python
THRESHOLDS = {
    "critical_delta": 0.10,   # ΔScore >= 0.10 → critical
    "spof_delta": 0.15,       # ΔScore >= 0.15 → SPOF WARNING
    "low_delta": 0.02,        # ΔScore < 0.02 → low（prune 候補）
}
```

#### Scenario: 重要度ランキングの生成
- **WHEN** Rules 5件 + Skills 10件の仮想除去が完了する
- **THEN** 15件の ΔScore がランキングされ、ΔScore >= 0.10 の要素が critical と判定される

#### Scenario: 影響のない構成要素の判定
- **WHEN** 仮想除去しても ΔScore が 0.02 未満の構成要素がある
- **THEN** criticality が low と判定され、prune 候補として表示される

### Requirement: Robustness score
堅牢性スコアは `max(0.0, 1.0 - (max_delta_score / max(baseline_coherence, 0.01)))` として算出しなければならない（MUST）。単一構成要素の除去で大幅にスコアが低下する環境は堅牢性が低いと判定する。

#### Scenario: 高い堅牢性
- **WHEN** 全構成要素の ΔScore が 0.05 以下
- **THEN** robustness_score が 0.9 以上になる

#### Scenario: 低い堅牢性（単一障害点あり）
- **WHEN** 1 つの構成要素の ΔScore が 0.3
- **THEN** robustness_score が低くなり、single_point_of_failure として警告される

#### Scenario: Baseline coherence = 0
- **WHEN** ベースライン Coherence Score が 0.0
- **THEN** `max(baseline, 0.01)` により 0 除算が回避され、robustness_score が 0.0 になる

#### Scenario: ΔScore > baseline
- **WHEN** 仮想除去により ΔScore がベースライン Coherence を超える
- **THEN** `max(0.0, ...)` により robustness_score が 0.0 にクランプされる

### Requirement: Chaos testing scope
仮想除去の対象は Rules と Skills のみとしなければならない（MUST）。CLAUDE.md と Memory は除去対象外とする（CLAUDE.md は環境の基盤であり除去テストの意味がない）。

#### Scenario: 対象レイヤーの限定
- **WHEN** `compute_chaos_score()` を実行する
- **THEN** Rules と Skills のみが仮想除去され、CLAUDE.md と Memory の除去テストは実行されない
