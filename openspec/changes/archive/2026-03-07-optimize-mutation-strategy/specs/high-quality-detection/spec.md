## ADDED Requirements

### Requirement: High quality baseline detection
ベースライン（Gen 0 elite）のスコアが `HIGH_QUALITY_THRESHOLD`（デフォルト 0.85）以上の場合、警告を表示し mutation 強度を自動的に `light` に切り替える。

#### Scenario: High quality skill detected
- **WHEN** ベースラインスコアが 0.90 の場合
- **THEN** 「ベースラインスコアが高いため、改善余地が限られます。mutation 強度を light に切り替えます」の警告が出力される

#### Scenario: Normal quality skill proceeds normally
- **WHEN** ベースラインスコアが 0.70 の場合
- **THEN** 警告なしで指定された mutation 強度のまま最適化が進む

### Requirement: Force flag override
`--force` フラグにより高品質検出による自動切り替えを無効化できる。

#### Scenario: Force flag overrides auto-switch
- **WHEN** ベースラインスコアが 0.90 で `--force` フラグが指定されている
- **THEN** mutation 強度は指定値のまま変更されず最適化が実行される

### Requirement: Configurable threshold
`HIGH_QUALITY_THRESHOLD` は設定ファイルまたは CLI 引数で変更可能にする。

#### Scenario: Custom threshold via CLI
- **WHEN** `--high-quality-threshold 0.90` を指定する
- **THEN** 0.90 以上のベースラインスコアでのみ高品質検出が発動する
