Related: #21

## 0. Config & Loader

- [x] 0.1 `scripts/lib/pipeline_reflector.py` に `DEFAULT_SELF_EVOLUTION_CONFIG` 定数と `load_self_evolution_config()` を実装（`trigger_engine.py` の `load_trigger_config()` パターン準拠）。D6 閾値一覧の全定数をデフォルト値として定義

## 1. Outcome 記録の拡張

- [x] 1.1 remediation.py の record_outcome() に extended metadata（fix_detail, verify_result, duration_ms, result="fix_failed"/"rejected" 区分）を追加
- [x] 1.2 既存テストを拡張し、新フィールドの記録を検証

## 2. Pipeline Reflector モジュール

- [x] 2.1 `scripts/lib/pipeline_reflector.py` を新規作成 — remediation-outcomes.jsonl 読み込み + issue_type 別集計（precision, approval_rate, false_positive_rate）
- [x] 2.2 False positive 検出ロジック実装（high-confidence rejection + systematic rejection パターン）
- [x] 2.3 自然言語診断生成（false positive dominant / healthy の2パターン）
- [x] 2.4 データ不足時のスキップ処理（`MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件要件）
- [x] 2.5 unit テスト作成（集計、false positive 検出、診断生成、データ不足）

## 3. Confidence Calibration

- [x] 3.1 pipeline_reflector.py に EWA キャリブレーションロジック追加（`calibrated = α * observed_approval_rate + (1 - α) * current_confidence` where `α = min(sample_size / CALIBRATION_SAMPLE_THRESHOLD, MAX_CALIBRATION_ALPHA)`）
- [x] 3.2 `confidence-calibration.json` の読み書き処理実装（alpha フィールド含む）
- [x] 3.3 管理図チェック（μ ± 2σ 範囲外の delta に risk_level: "high" 付与）
- [x] 3.4 回帰チェック（変更後 confidence で既存 outcomes を再分類し回帰検出）
- [x] 3.5 remediation.py の `compute_confidence_score()` に calibration 参照ロジック追加
- [x] 3.6 unit テスト作成（キャリブレーション算出、管理図チェック、回帰検出、calibration 適用）

## 4. Adaptive Pipeline Config

- [x] 4.1 pipeline_reflector.py に調整提案生成ロジック追加（confidence delta proposal + risk_level 判定）
- [x] 4.2 `pipeline-proposals.jsonl` の記録処理実装（pending/approved/rejected status 管理）
- [x] 4.3 unit テスト作成（提案生成、risk_level 判定、persistence）

## 5. Audit Pipeline Health セクション

- [x] 5.1 audit.py に `--pipeline-health` オプション追加
- [x] 5.2 Pipeline Health セクション生成ロジック実装（issue_type 別テーブル + DEGRADED マーカー）。閾値は `APPROVAL_RATE_DEGRADED_THRESHOLD`（デフォルト: 0.7）を使用
- [x] 5.3 セクション順序の統合（既存スコアセクションの後に配置）
- [x] 5.4 unit テスト作成（十分データ、不足データ、degraded 表示、LLM 不使用確認）

## 6. Self-Evolution トリガー

- [x] 6.1 trigger_engine.py に `_evaluate_self_evolution()` 追加（`FALSE_POSITIVE_RATE_THRESHOLD`（デフォルト: 0.3）閾値 + サンプル数 `MIN_OUTCOMES_PER_TYPE`（デフォルト: 10）件要件）
- [x] 6.2 trigger_engine.py に `_evaluate_approval_rate_decline()` 追加（直近 `DECLINE_SAMPLE_SIZE`（デフォルト: 10）件 vs 前 `DECLINE_SAMPLE_SIZE` 件の `APPROVAL_RATE_DECLINE_THRESHOLD`（デフォルト: 0.2）低下検出）
- [x] 6.3 self_evolution 用クールダウン `SELF_EVOLUTION_COOLDOWN_HOURS`（デフォルト: 72h）設定
- [x] 6.4 unit テスト作成（閾値到達、未到達、クールダウン、承認率低下）

## 7. Evolve パイプライン統合

- [x] 7.1 evolve.py の Compile ステージに self-evolution を Phase 6 として追加（trajectory analysis → calibration 提案 → ユーザー確認）
- [x] 7.2 evolve-state.json に self_evolution 関連の状態フィールド追加（last_calibration_timestamp, calibration_history）
- [x] 7.3 dry-run 対応（分析・表示はするが状態ファイル書き込みなし）
- [x] 7.4 統合テスト — evolve 全フェーズを通した self-evolution 動作確認
