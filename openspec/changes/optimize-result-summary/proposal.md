## Why

`/optimize` の accept/reject 確認時に、スコアだけ表示されてユーザーが判断材料を得られない。ベースラインとの差分・各世代のスコア推移・変更ハイライトがないため、十分な情報なしに accept/reject を判断することになり、フィードバックの質が低下する。evolve-fitness の改善精度にも影響する。

## What Changes

- optimize.py の結果表示に以下の詳細サマリを追加:
  - 対象スキル名とファイルパス
  - ベースライン（元スキル）のスコア
  - 各世代のベスト/平均スコア推移テーブル
  - 最良バリエーションの変更サマリ（追加/削除/変更行数、主な変更点の要約）
  - CoT 評価の各基準スコア（clarity, completeness, structure, practicality）
- SKILL.md の accept/reject 確認ステップで、上記サマリ表示を必須化

## Capabilities

### New Capabilities
- `optimize-result-summary`: 最適化結果の詳細サマリ生成（diff 要約、スコア推移、CoT 内訳）

### Modified Capabilities

## Impact

- `skills/genetic-prompt-optimizer/scripts/optimize.py`: 結果出力ロジック拡張
- `skills/genetic-prompt-optimizer/SKILL.md`: accept/reject 確認フロー更新
- 関連 Issue: #7
