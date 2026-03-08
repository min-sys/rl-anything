## 1. mutation プロンプト改善

- [x] 1.1 mutation プロンプトに情報保持制約を追加（情報量維持、行数 ±20% 制約）
- [x] 1.2 crossover プロンプトにも同様の情報保持制約を追加

## 2. mutation 強度パラメータ

- [x] 2.1 `GeneticOptimizer.__init__()` に `mutation_strength` パラメータ追加
- [x] 2.2 3段階（light/medium/heavy）ごとの mutation プロンプトテンプレート実装
- [x] 2.3 `--mutation-strength` CLI 引数追加（argparse）
- [x] 2.4 mutation 強度のユニットテスト追加

## 3. 部分的 mutation

- [x] 3.1 `mutate()` にセクション分割ロジック追加（`##` 見出しで split）
- [x] 3.2 ランダムセクション選択 + 非選択セクション保持の実装
- [x] 3.3 部分的 mutation のユニットテスト追加

## 4. 高品質スキル検出

- [x] 4.1 `HIGH_QUALITY_THRESHOLD` 定数と閾値チェックロジック追加
- [x] 4.2 高品質検出時の警告メッセージ + mutation 強度自動切り替え
- [x] 4.3 `--force` フラグと `--high-quality-threshold` CLI 引数追加
- [x] 4.4 高品質検出のユニットテスト追加

## 5. SKILL.md・テスト

- [x] 5.1 SKILL.md に mutation-strength オプション説明追加
- [x] 5.2 既存テストの回帰確認

関連 Issue: #8
