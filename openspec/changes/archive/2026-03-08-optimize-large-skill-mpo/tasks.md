## 0. Strategy Router（手法自動選択）

- [x] 0.1 `strategy_router.py` モジュールを新規作成: `select_strategy(file_lines)` 関数（< 200行 → self_refine、200行超 → budget_mpo）
- [x] 0.2 `_run_self_refine()` メソッド: 批評→部分修正ループ（最大3回反復）の統合
- [x] 0.3 strategy-router のユニットテスト追加（閾値境界値テスト）

## 1. 適応的粒度制御（Adaptive Granularity）

- [x] 1.1 `granularity.py` モジュールを新規作成: `determine_split_level(file_lines)` 関数（3段階: none/h2_h3/h2_only）
- [x] 1.2 `Section` データクラス定義（id, heading, lines, parent_id, depth）
- [x] 1.3 `split_sections(content, level)` 関数: Markdown を見出しレベルに応じてセクション分割
- [x] 1.4 `merge_small_sections(sections, min_lines=10)` 関数: 小セクションを親に統合
- [x] 1.5 粒度制御のユニットテスト追加（短/中/長ファイルでのセクション数検証）

## 2. Budget-Aware セクション選択（Thompson Sampling）

- [x] 2.1 `bandit_selector.py` モジュールを新規作成: `BanditSectionSelector` クラス
- [x] 2.2 Thompson Sampling 実装: `Beta(alpha, beta)` の初期化、サンプリング、top-K 選択
- [x] 2.3 `update(section_id, improved)` メソッド: 最適化結果に基づく分布更新
- [x] 2.4 Leave-One-Out 重要度推定: `estimate_importance(sections, evaluator)` 関数（N+1コール）
- [x] 2.5 LOO スコアを Thompson Sampling の事前情報（alpha 初期値）に変換するロジック
- [x] 2.6 `--budget N` CLI 引数追加（高価モデルのコール数上限）
- [x] 2.7 Thompson Sampling のユニットテスト追加（選択分布の更新、top-K の偏り検証）

## 3. モデルカスケード（FrugalGPT）

- [x] 3.1 `model_cascade.py` モジュールを新規作成: `ModelCascade` クラス
- [x] 3.2 3段カスケード実装: Tier 1（重要度推定）/ Tier 2（最適化生成）/ Tier 3（最終評価）
- [x] 3.3 モデル名の設定ファイル対応（`cascade_config.yaml` or 環境変数）
- [x] 3.4 `claude -p` のモデル指定ラッパー（`--model` フラグ or `CLAUDE_MODEL` 環境変数）
- [x] 3.5 `--cascade` CLI フラグ追加（カスケード有効化）
- [x] 3.6 カスケード無効時は従来通り単一モデルで動作することの回帰テスト

## 4. 早期停止ルール（Early Stopping）

- [x] 4.1 セクション単位の停止条件を定義: `EarlyStopRule` データクラス
- [x] 4.2 4つの停止条件実装: 品質到達 / プラトー検出（連続3回改善なし）/ バジェット上限 / 収穫逓減（marginal_gain < 0.01）。累積コスト上限（`--budget` で指定された高価モデルコール数に達したら全セクション停止）を含む
- [x] 4.3 `should_stop(section_id, history)` メソッド: 停止判定
- [x] 4.4 停止理由のログ出力（どの条件で停止したか）
- [x] 4.5 早期停止のユニットテスト追加

## 5. ファイル並行最適化（Parallel File Optimization）

- [x] 5.1 references/ ディレクトリの自動検出とファイルリスト化
- [x] 5.2 `ThreadPoolExecutor` による並行 MPO 実行
- [x] 5.3 `--parallel N` CLI 引数追加（並行数制御）
- [x] 5.4 SKILL.md の最適化順序制御（references/ 完了後に実行）
- [x] 5.5 De-dup consolidation パス: 並行最適化後の矛盾検出・解消
- [x] 5.6 並行実行のユニットテスト追加（モック使用）

## 6. optimize.py 統合

- [x] 6.1 `GeneticOptimizer` に strategy-router を組み込み: `_select_strategy()` + `_run_self_refine()` + `_run_budget_aware()`。`Individual` に `section_id: Optional[str]` フィールドを追加し、budget_mpo パスでセクション追跡を可能にする
- [x] 6.2 Phase 0-3 パイプラインの統合: router → granularity → importance → bandit + optimize → early stop + consolidation。evaluate() は `Callable[[str], float]` インターフェースとし、project-specific-fitness の execution-based evaluation と共通化する
- [x] 6.3 Prefix Caching 対応: 評価プロンプトの固定部分を先頭に配置
- [x] 6.4 SKILL.md に新オプション（`--budget`, `--cascade`, `--parallel`）の説明追加
- [x] 6.5 回帰確認（short_rule → self_refine パス、long_skill → budget_mpo パスが正しく選択されること）

## 7. 統合テスト

- [x] 7.1 atlas-browser 規模（1,000行超）のモックスキルを作成
- [x] 7.2 `--dry-run --budget 30` での統合テスト（全フェーズ通過の確認）
- [x] 7.3 コール数カウンタの実装とアサーション（budget 以内に収まること）
- [x] 7.4 粒度制御 + バンディット選択の組み合わせテスト
- [x] 7.5 カスケード + 早期停止の組み合わせテスト
- [ ] 7.6 実環境での atlas-browser 最適化実行（手動、結果を #13 にフィードバック）

closes #13
関連 Issue: #12, #8
