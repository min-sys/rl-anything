## Why

`/optimize` の mutation で生成された個体は文字数が大幅に減少する傾向（2491文字 → 1000文字前後）があり、情報が欠落してスコアが低下する。結果としてオリジナルが常に最良のまま終了し、API コストだけ消費する状況になっている。mutation プロンプトが「改善」を一律に指示するだけで、変異の強度やスコープを制御できない。

## What Changes

- mutation プロンプトを改善し、「情報を保持しつつ質を上げる」方向の制約を明示
- mutation 強度パラメータ（`--mutation-strength`）を導入: `light`（微修正: 表現改善・構造整理）、`medium`（デフォルト: セクション追加/削除）、`heavy`（大幅変更: 構造再設計）
- 部分的 mutation の導入: セクション単位で変異対象を選択し、残りは保持
- 高品質スキル検出: ベースラインスコアが閾値（例: 0.85）以上の場合に「改善余地が少ない」警告を表示し、light mutation のみ適用
- crossover プロンプトも同様に情報保持の制約を追加

## Capabilities

### New Capabilities
- `mutation-strength-control`: mutation 強度パラメータと部分的 mutation ロジック
- `high-quality-detection`: 高品質スキル検出と最適化スキップ/軽量化

### Modified Capabilities

## Impact

- `skills/genetic-prompt-optimizer/scripts/optimize.py`: mutate(), crossover() メソッド変更、CLI 引数追加
- `skills/genetic-prompt-optimizer/SKILL.md`: mutation-strength オプション説明追加
- `skills/genetic-prompt-optimizer/tests/test_optimizer.py`: 新パラメータのテスト追加
- 関連 Issue: #8
