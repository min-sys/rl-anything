## 1. `--model` ハードコード除去
（依存なし — 最初に着手）

- [ ] 1.1 optimize.py の `_llm_evaluate` から `--model haiku` を削除
- [ ] 1.2 optimize.py の `mutate` から `--model sonnet` を削除
- [ ] 1.3 optimize.py の `crossover` から `--model sonnet` を削除
- [ ] 1.4 run-loop.py の全 `claude -p` 呼び出しから `--model` を削除
- [ ] 1.5 既存テストが通ることを確認（`python3 -m pytest skills/ -v`）

## 2. Chain-of-Thought 評価
依存: Group 1 完了後

- [ ] 2.1 `_llm_evaluate` のプロンプトを CoT + JSON出力形式に変更
- [ ] 2.2 JSON パースロジックを実装（`json.loads` + 正規表現フォールバック）
- [ ] 2.3 CoT 評価のテストを追加（正常JSON、不正JSON、空出力のケース）

## 3. Pairwise Comparison
依存: Group 2 完了後（CoT のスコア形式に依存）

- [ ] 3.1 `pairwise_compare(a, b)` メソッドを GeneticOptimizer に追加
- [ ] 3.2 位置バイアス緩和: A/B 入替2回評価 + フォールバックロジックを実装
- [ ] 3.3 `next_generation` のエリート選択にスコア差 0.1 以内のとき pairwise を挟む処理を追加
- [ ] 3.4 pairwise comparison のテストを追加

## 4. 回帰テストゲート
依存: Group 1 完了後（Group 2,3 と並行可能）

- [ ] 4.1 `_regression_gate(content)` メソッドを追加: 空チェック・行数チェック・禁止パターンチェック（禁止パターン: `TODO`, `FIXME`, `HACK`, `XXX`）
- [ ] 4.2 `evaluate` メソッドの先頭で `_regression_gate` を呼び出し、不合格なら 0.0 を即返却
- [ ] 4.3 回帰ゲートのテストを追加（空・超過・禁止パターン・正常通過の各ケース）

## 5. 実行ベース評価
依存: Group 2 完了後（CoT のスコアと統合するため）

- [ ] 5.1 `--test-tasks` CLI 引数を argparse に追加
- [ ] 5.2 テストタスクYAMLのパーサーを実装
- [ ] 5.3 `_execution_evaluate(individual, test_tasks)` メソッドを実装: claude -p でスキル実行 → 出力評価の2段階パイプライン
- [ ] 5.4 `evaluate` メソッドに CoT × 0.4 + 実行ベース × 0.6 の加重平均ロジックを追加
- [ ] 5.5 テストタスクYAMLのサンプルファイルを作成
- [ ] 5.6 実行ベース評価のテストを追加（タイムアウト、正常実行のケース）

## 6. 失敗パターン自動蓄積（pitfall-accumulator）
依存: Group 2, 4 完了後（CoT の reason 出力と Regression Gate に依存）

- [ ] 6.1 `_record_pitfall(target_path, source, pattern, score)` メソッドを追加: `references/pitfalls.md` への追記ロジック（ディレクトリ自動作成、ヘッダー初期化、テーブル追記）
- [ ] 6.2 重複排除ロジックを実装: 既存 Pattern 文字列との比較、50 行上限の FIFO 制御
- [ ] 6.3 Regression Gate 不合格時に `_record_pitfall` を呼び出す処理を追加
- [ ] 6.4 CoT 評価完了後、スコア 0.4 未満の基準があれば `_record_pitfall` を呼び出す処理を追加
- [ ] 6.5 run-loop.py の人間却下時に `_record_pitfall` を呼び出す処理を追加
- [ ] 6.6 `_regression_gate` を拡張: pitfalls.md が存在する場合、蓄積パターンも動的チェック対象に追加
- [ ] 6.7 pitfall-accumulator のテストを追加（新規作成、追記、重複排除、行数上限、動的ゲートの各ケース）

## 7. 統合テスト
依存: Group 2-6 全て完了後

- [ ] 7.1 `--dry-run` で全評価パイプラインが動作することを確認
- [ ] 7.2 atlas-breeaders のスキルを対象にフル実行テスト（`--generations 1 --population 2`）
- [ ] 7.3 最適化実行後に `references/pitfalls.md` が生成・蓄積されていることを確認
