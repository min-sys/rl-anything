## ADDED Requirements

### Requirement: Pairwise Comparison によるエリート選択
`next_generation` でエリート個体を選択する際、絶対スコアのみでなく、トップ2候補の直接比較を実施する。

#### Scenario: トップ2候補の比較
- **WHEN** 世代内のトップ2個体のスコア差が 0.1 以内である
- **THEN** Pairwise Comparison を実行し、勝者をエリートとして選択する

#### Scenario: スコア差が十分大きい場合
- **WHEN** トップ2個体のスコア差が 0.1 を超える
- **THEN** Pairwise Comparison をスキップし、スコア最高の個体をそのまま選択する

### Requirement: 位置バイアスの緩和
Pairwise Comparison は候補 A/B の提示順を入れ替えて2回評価し、結果を統合する。

#### Scenario: 両回で同じ候補が勝つ場合
- **WHEN** A/B 順と B/A 順の両方で同じ候補が選ばれる
- **THEN** その候補を勝者とする

#### Scenario: 入替で結果が異なる場合
- **WHEN** A/B 順と B/A 順で異なる候補が選ばれる
- **THEN** 絶対スコア（CoT評価の total）が高い方をフォールバックで選択する
