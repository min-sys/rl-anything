## ADDED Requirements

### Requirement: Mutation strength parameter
`GeneticOptimizer` は `mutation_strength` パラメータ（`light`, `medium`, `heavy`）を受け取り、mutation プロンプトの変異スコープを制御する。デフォルトは `medium`。

#### Scenario: Light mutation preserves content
- **WHEN** `mutation_strength="light"` で mutate を実行する
- **THEN** mutation プロンプトに「内容を変えず、表現のみ改善」の指示が含まれる

#### Scenario: Medium mutation with information preservation
- **WHEN** `mutation_strength="medium"` で mutate を実行する
- **THEN** mutation プロンプトに「元のスキルの情報量を維持または増加させること」の制約が含まれる

#### Scenario: Heavy mutation allows restructuring
- **WHEN** `mutation_strength="heavy"` で mutate を実行する
- **THEN** mutation プロンプトに「構造を大胆に再設計してよい」の指示が含まれる

### Requirement: Information preservation constraint
全ての mutation 強度で、mutation プロンプトに元のスキルの行数 ±20%（heavy は ±50%）の制約を含める。

#### Scenario: Mutation output within line budget
- **WHEN** 元のスキルが100行で `mutation_strength="medium"` の場合
- **THEN** mutation プロンプトに「80〜120行以内に収めること」の制約が含まれる

### Requirement: Section-based partial mutation
`mutate()` はスキルをセクション（`##` 見出し）単位で分割し、ランダムに1-2セクションのみ mutation 対象として選択する。

#### Scenario: Only selected sections are mutated
- **WHEN** スキルに5つのセクションがあり mutate を実行する
- **THEN** 1-2セクションのみが変更され、残りのセクションは元のまま保持される

### Requirement: CLI argument
`--mutation-strength` CLI 引数で `light`, `medium`, `heavy` を指定可能にする。

#### Scenario: CLI with light strength
- **WHEN** `optimize.py --target path --mutation-strength light` を実行する
- **THEN** `GeneticOptimizer` が `mutation_strength="light"` で初期化される
