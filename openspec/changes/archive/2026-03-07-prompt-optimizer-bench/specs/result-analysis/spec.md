## ADDED Requirements

### Requirement: 結果を統計的にまとめる

ベンチマーク結果から手法ごとの統計サマリを生成しなければならない（SHALL）。

各メトリクスについて平均・標準偏差・信頼区間（95%）を算出する。

#### Scenario: サマリ表の出力

- **WHEN** `python analysis/summarize.py results/run_001.json` を実行する
- **THEN** 以下の形式でサマリ表を出力する:

```
Strategy         score_imp  survival  complete  cost
─────────────    ─────────  ────────  ────────  ────
baseline_ga      +0.02±0.03  0.10     0.45      9
self_refine      +0.08±0.02  0.60     0.95      15
gepa_lite        +0.12±0.04  0.55     0.90      18
```

### Requirement: レーダーチャートで可視化する

4メトリクスをレーダーチャートで可視化できなければならない（SHALL）。コスト指標は逆数にして「コスト効率」として表示する。

#### Scenario: レーダーチャート生成

- **WHEN** `python analysis/visualize.py results/run_001.json --output chart.png` を実行する
- **THEN** 全手法を重ねたレーダーチャートを PNG で出力する

### Requirement: ターゲットサイズ別の分析ができる

ターゲットスキルのサイズ（短/中/長）ごとに結果を分解して分析できなければならない（SHALL）。

#### Scenario: サイズ別サマリ

- **WHEN** `--group-by size` オプションを指定する
- **THEN** 短（〜20行）、中（〜50行）、長（〜100行）ごとにサマリを出力する

### Requirement: JSON 形式で結果を出力する

全ての分析結果を JSON 形式でも出力できなければならない（SHALL）。プログラムからの利用や rl-anything への還元を可能にする。

#### Scenario: JSON 出力

- **WHEN** `--format json` オプションを指定する
- **THEN** サマリ・統計値を JSON 形式で出力する
