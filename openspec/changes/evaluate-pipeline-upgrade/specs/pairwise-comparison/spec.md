## ADDED Requirements

### Requirement: Pairwise Comparison によるエリート選択
`next_generation` でエリート個体を選択する際、絶対スコアのみでなく、トップ2候補の直接比較を実施しなければならない（MUST）。

#### Scenario: トップ2候補の比較
- **WHEN** 世代内のトップ2個体のスコア差が 0.1 以内である
- **THEN** Pairwise Comparison を実行し、勝者をエリートとして選択しなければならない（MUST）

#### Scenario: スコア差が十分大きい場合
- **WHEN** トップ2個体のスコア差が 0.1 を超える
- **THEN** Pairwise Comparison をスキップし、スコア最高の個体をそのまま選択しなければならない（MUST）

### Requirement: 位置バイアスの緩和
Pairwise Comparison は候補 A/B の提示順を入れ替えて2回評価し、結果を統合しなければならない（MUST）。

#### Scenario: 両回で同じ候補が勝つ場合
- **WHEN** A/B 順と B/A 順の両方で同じ候補が選ばれる
- **THEN** その候補を勝者としなければならない（MUST）

#### Scenario: 入替で結果が異なる場合
- **WHEN** A/B 順と B/A 順で異なる候補が選ばれる
- **THEN** 絶対スコア（CoT評価の total）が高い方にフォールバックしなければならない（MUST）

### Requirement: LLM呼び出し失敗時のフォールバック
Pairwise比較のLLM呼び出しが失敗した場合、絶対スコアによる比較にフォールバックしなければならない（MUST）。

#### Scenario: LLM呼び出しがタイムアウトまたはエラーで失敗した場合
- **WHEN** Pairwise比較のLLM呼び出しがタイムアウト（120秒超）またはエラーで失敗する
- **THEN** stderr に警告を出力し、絶対スコア（CoT total）による比較にフォールバックする

#### Scenario: 2回のswap比較のうち1回のみ失敗した場合
- **WHEN** A/B 順と B/A 順の2回の比較のうち、1回のみが失敗する
- **THEN** 成功した1回の結果を採用する
