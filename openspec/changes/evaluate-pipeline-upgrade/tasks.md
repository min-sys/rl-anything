## 1. `--model` ハードコード除去

- [ ] 1.1 optimize.py の `_llm_evaluate` から `--model haiku` を削除
- [ ] 1.2 optimize.py の `mutate` から `--model sonnet` を削除
- [ ] 1.3 optimize.py の `crossover` から `--model sonnet` を削除
- [ ] 1.4 run-loop.py の全 `claude -p` 呼び出しから `--model` を削除
- [ ] 1.5 既存テストが通ることを確認（`python3 -m pytest skills/ -v`）

## 2. Chain-of-Thought 評価

- [ ] 2.1 `_llm_evaluate` のプロンプトを CoT + JSON出力形式に変更
- [ ] 2.2 JSON パースロジックを実装（`json.loads` + 正規表現フォールバック）
- [ ] 2.3 CoT 評価のテストを追加（正常JSON、不正JSON、空出力のケース）

## 3. Pairwise Comparison

- [ ] 3.1 `pairwise_compare(a, b)` メソッドを GeneticOptimizer に追加
- [ ] 3.2 位置バイアス緩和: A/B 入替2回評価 + フォールバックロジックを実装
- [ ] 3.3 `next_generation` のエリート選択にスコア差 0.1 以内のとき pairwise を挟む処理を追加
- [ ] 3.4 pairwise comparison のテストを追加

## 4. 回帰テストゲート

- [ ] 4.1 `_regression_gate(content)` メソッドを追加: 空チェック・行数チェック・禁止パターンチェック
- [ ] 4.2 `evaluate` メソッドの先頭で `_regression_gate` を呼び出し、不合格なら 0.0 を即返却
- [ ] 4.3 回帰ゲートのテストを追加（空・超過・禁止パターン・正常通過の各ケース）

## 5. 実行ベース評価

- [ ] 5.1 `--test-tasks` CLI 引数を argparse に追加
- [ ] 5.2 テストタスクYAMLのパーサーを実装
- [ ] 5.3 `_execution_evaluate(individual, test_tasks)` メソッドを実装: claude -p でスキル実行 → 出力評価の2段階パイプライン
- [ ] 5.4 `evaluate` メソッドに CoT × 0.4 + 実行ベース × 0.6 の加重平均ロジックを追加
- [ ] 5.5 テストタスクYAMLのサンプルファイルを作成
- [ ] 5.6 実行ベース評価のテストを追加（タイムアウト、正常実行のケース）

## 6. 統合テスト

- [ ] 6.1 `--dry-run` で全評価パイプラインが動作することを確認
- [ ] 6.2 atlas-breeaders のスキルを対象にフル実行テスト（`--generations 1 --population 2`）
