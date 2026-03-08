## 1. telemetry_query.py 時間範囲クエリ拡張

- [x] 1.1 query_usage() / query_errors() / query_sessions() に `since` / `until` パラメータを追加（DuckDB + Python フォールバック両対応）
- [x] 1.2 時間範囲クエリの単体テスト（DuckDB モック + Python フォールバック両方）
- [x] 1.3 `query_corrections()` 新規作成（`project_path` から末尾名抽出による project フィルタ正規化 + since/until 対応）
- [x] 1.4 `query_workflows()` 新規作成（since/until 対応、Phase 1 では project フィルタなし — workflows.jsonl に project フィールドがないため全 PJ 横断集計）
- [x] 1.5 query_corrections() / query_workflows() の単体テスト（project_path 正規化、時間範囲フィルタ）

## 2. telemetry.py コアスコア関数

- [x] 2.1 `scripts/rl/fitness/telemetry.py` 骨格作成（THRESHOLDS / WEIGHTS 定数、coherence.py と同パターン）
- [x] 2.2 `score_utilization()` 実装（Skill 利用率 + Shannon entropy 正規化）
- [x] 2.3 `score_effectiveness()` 実装（エラー減少率 + 修正トレンド + ワークフロー完走率）
- [x] 2.4 `score_implicit_reward()` 実装（Skill 成功率推定 + 繰り返し利用率）
- [x] 2.5 `compute_telemetry_score()` 統合（3軸ブレンド + data_sufficiency 判定）
- [x] 2.6 argparse CLI モード（`python3 telemetry.py <project_dir> [--days N]` — `--fitness` フラグでは使用しない）

## 3. environment.py 統合 fitness

- [x] 3.1 `scripts/rl/fitness/environment.py` 作成（coherence + telemetry ブレンド）
- [x] 3.2 argparse CLI モード（`python3 environment.py <project_dir> [--days N]` — `--fitness` フラグでは使用しない）

## 4. audit スキル統合

- [x] 4.1 `skills/audit/SKILL.md` に `--telemetry-score` オプション説明を追加
- [x] 4.2 audit 実行スクリプトに Telemetry Score セクション表示を実装
- [x] 4.3 `--coherence-score --telemetry-score` 同時指定時の Environment Fitness 表示を実装
- [x] 4.4 data_sufficiency=False 時の警告メッセージ表示

## 5. テスト

- [x] 5.1 telemetry.py の各スコア関数の単体テスト（テスト用 JSONL ファイル注入）
- [x] 5.2 environment.py の統合テスト（data_sufficiency true/false 両ケース）
- [x] 5.3 audit 統合の動作確認テスト

## 6. ドキュメント・仕上げ

- [x] 6.1 README.md の適応度関数セクションに telemetry / environment を追記
- [x] 6.2 CLAUDE.md の Fitness 関連説明を更新
