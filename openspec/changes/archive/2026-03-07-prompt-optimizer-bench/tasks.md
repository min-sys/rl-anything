## 1. リポジトリ初期構築

- [x] 1.1 matsukaze-minden に `prompt-optimizer-bench` リポジトリを作成（README, .gitignore, pyproject.toml）
- [x] 1.2 ディレクトリ構成を作成（strategies/, tasks/, analysis/, results/）
- [x] 1.3 `BaseStrategy` ABC と `MutationContext`, `MutationResult`, `EvaluationResult` のデータクラスを定義
- [x] 1.4 Strategy の自動検出機構（strategies/ ディレクトリスキャン）を実装

## 2. Phase 1 Strategy 実装

- [x] 2.1 `BaselineGAStrategy` を実装（rl-anything の現行 optimize.py の mutation/crossover/evaluate をポート）
- [x] 2.2 `SelfRefineStrategy` を実装（批評→部分修正ループ、最大3回反復）
- [x] 2.3 `GEPALiteStrategy` を実装（診断→指示付き変異、MutationContext 活用）

## 3. 評価フレームワーク

- [x] 3.1 共通 evaluator を実装（LLM CoT 比較評価、before/after diff 含む）
- [x] 3.2 変異完全性チェッカーを実装（frontmatter 存在、セクション数比較、末尾切れ検知）
- [x] 3.3 テストタスク評価を実装（YAML 定義のタスクを `claude -p` で実行→出力品質を評価）
- [x] 3.4 4メトリクス（score_improvement, survival_rate, completeness, llm_cost）の集約ロジックを実装

## 4. ベンチマークランナー

- [x] 4.1 CLI runner（`--strategies`, `--targets`, `--trials`, `--output`）を実装
- [x] 4.2 YAML 設定ファイルのロードを実装
- [x] 4.3 ドライランモード（`--dry-run`）を実装
- [x] 4.4 進捗表示（`[strategy] [target] [trial N/M]`）を実装
- [x] 4.5 中断・再開機能（既存結果のスキップ）を実装

## 5. テストデータ準備

- [x] 5.1 短いスキル（〜20行 rule 系）をターゲットとして用意
- [x] 5.2 中くらいのスキル（〜50行）をターゲットとして用意
- [x] 5.3 長いスキル（〜100行、optimize 相当）をターゲットとして用意
- [x] 5.4 各ターゲットのテストタスク YAML を作成（3-5タスク/スキル）

## 6. 結果分析

- [x] 6.1 統計サマリ生成（平均・標準偏差・95%信頼区間）を実装
- [x] 6.2 レーダーチャート可視化を実装（matplotlib）
- [x] 6.3 ターゲットサイズ別グルーピング分析を実装
- [x] 6.4 JSON 出力オプションを実装

## 7. Phase 1 ベンチマーク実行・レポート

- [x] 7.1 Phase 1 の3手法でベンチマークを実行（5 trials）
- [x] 7.2 結果を分析し、比較レポートを作成
- [x] 7.3 rl-anything issue #12 に結果をフィードバック

## 8. Phase 2 Strategy 追加（Phase 1 結果後）

- [ ] 8.1 `TextGradStrategy` を実装（textgrad ライブラリのラッパー）
- [ ] 8.2 `DSPyStrategy` を実装（DSPy MIPROv2 のラッパー）
- [ ] 8.3 Phase 2 手法を含めたベンチマーク再実行・レポート更新
