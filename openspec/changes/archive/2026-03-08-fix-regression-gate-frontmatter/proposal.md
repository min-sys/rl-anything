Closes: #20

## Why

`/optimize` の regression gate が、LLM パッチによる YAML frontmatter 消失を検出できない。frontmatter 付きスキルを最適化した際、LLM が frontmatter なしのパッチを返しても gate を通過してしまい、壊れたスキルが適用される。frontmatter にはスキルの name/description/allowed-tools 等の必須メタデータが含まれており、消失はスキルの機能喪失に直結する。

## What Changes

- `_regression_gate()` に frontmatter 保持チェックを追加: 元コンテンツが `---` で始まる場合、パッチ後も `---` で始まることを必須とする
- 既存の regression-gate spec にシナリオを追加

## Capabilities

### New Capabilities

（なし）

### Modified Capabilities

- `regression-gate`: frontmatter 保持チェックのシナリオを追加

## Impact

- `skills/genetic-prompt-optimizer/scripts/optimize.py` — `_regression_gate()` メソッド
- `skills/genetic-prompt-optimizer/tests/test_optimizer.py` — テスト追加
- `openspec/specs/regression-gate/spec.md` — シナリオ追加
