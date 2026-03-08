## 1. Principle Extraction (`principles.py`)

- [x] 1.1 `scripts/rl/fitness/principles.py` を作成 — `extract_principles(project_dir, refresh=False)` の骨格実装
- [x] 1.2 CLAUDE.md + Rules の読み込みと `claude -p --model haiku` での原則抽出プロンプト実装（品質スコア specificity/testability を同一呼び出しで算出）
- [x] 1.3 シード原則 5 件のデフォルト搭載（`SEED_PRINCIPLES` 定数）
- [x] 1.4 `.claude/principles.json` へのキャッシュ保存・読み込み実装（`--refresh` フラグ対応）
- [x] 1.5 キャッシュ陳腐化検出 — CLAUDE.md + Rules の SHA-256 ハッシュを `source_hash` として保存、ロード時に比較
- [x] 1.6 ユーザー定義原則（`user_defined: true`）の `--refresh` 時マージ保持
- [x] 1.7 低品質原則の除外 — `min_principle_quality` (0.3) 未満の原則を `excluded_low_quality` に分離
- [x] 1.8 LLM 呼び出し失敗時の graceful fallback（シード原則返却 + stderr 警告）
- [x] 1.9 単体テスト — キャッシュ動作、マージ保持、シード原則、品質スコア、陳腐化検出、エラーハンドリング

## 2. Constitutional Evaluation (`constitutional.py`)

- [x] 2.1 `scripts/rl/fitness/constitutional.py` を作成 — `compute_constitutional_score(project_dir)` の骨格実装
- [x] 2.2 Coherence Coverage ゲート実装 — `coverage < 0.5` で `None` + `skip_reason` 返却
- [x] 2.3 レイヤー単位バッチ LLM 評価ループ実装（1レイヤー=1 LLM call、`claude -p --model haiku`）
- [x] 2.4 LLM レスポンスバリデーション — JSON パース失敗時1回リトライ、スコア clamp [0.0, 1.0]、タイムアウト時スキップ
- [x] 2.5 スコア集計 — `per_principle[i] = mean(layer_scores[i])`, `per_layer[j] = mean(principle_scores[j])`, `overall = mean(per_principle)`
- [x] 2.6 評価結果キャッシュ — `.claude/constitutional_cache.json` にレイヤーハッシュと紐づけて保存
- [x] 2.7 Graceful degradation — 一部レイヤー失敗時のスキップ、全失敗時の None 返却
- [x] 2.8 コスト追跡 — `estimated_cost_usd` と `llm_calls_count` の算出
- [x] 2.9 単体テスト — Coverage ゲート、バッチ評価、集計、バリデーション、キャッシュ、graceful degradation、コスト追跡

## 3. Chaos Testing (`chaos.py`)

- [x] 3.1 `scripts/rl/fitness/chaos.py` を作成 — `compute_chaos_score(project_dir)` の骨格実装
- [x] 3.2 `THRESHOLDS` dict 定義 — `critical_delta: 0.10`, `spof_delta: 0.15`, `low_delta: 0.02`
- [x] 3.3 仮想除去ロジック — Rules/Skills を個別に空として扱い Coherence Score を再計算
- [x] 3.4 ΔScore 算出と `importance_ranking` 生成（name, layer, delta_score, criticality）
- [x] 3.5 `robustness_score` 算出 — `max(0.0, 1.0 - (max_delta_score / max(baseline_coherence, 0.01)))`
- [x] 3.6 single_point_of_failure 検出（ΔScore >= `THRESHOLDS["spof_delta"]`）
- [x] 3.7 単体テスト — 仮想除去の安全性、ランキング生成、堅牢性スコア、baseline=0 エッジケース

## 4. Environment Fitness 3層ブレンド

- [x] 4.1 `environment.py` を修正 — `_load_sibling("constitutional")` で Constitutional Score を取得
- [x] 4.2 3層ブレンドの重み付けロジック実装（coherence 0.25 + telemetry 0.45 + constitutional 0.30）
- [x] 4.3 フォールバック分岐 — Constitutional 不可時の既存 2層比率維持、Coverage ゲート skip_reason の伝播
- [x] 4.4 返却 dict の sources リストに "constitutional" を追加
- [x] 4.5 単体テスト — 3層/2層/1層の各パターン、重み付け値の検証、Coverage ゲートフォールバック

## 5. Audit 統合

- [x] 5.1 audit SKILL.md に `--constitutional-score` オプションの説明を追加
- [x] 5.2 audit.py に `--constitutional-score` オプション追加と "## Constitutional Score" セクション生成
- [x] 5.3 Constitutional Score セクション内に原則別スコアと推定コストを表示
- [x] 5.4 "### Chaos Testing (Robustness)" サブセクション — robustness_score + 重要度ランキング上位 5 件
- [x] 5.5 SPOF WARNING マーカー表示（ΔScore >= `THRESHOLDS["spof_delta"]` の要素）
- [x] 5.6 LLM 失敗時のフォールバック表示（「LLM 評価に失敗しました」）
- [x] 5.7 セクション順序制御 — Environment Fitness → Constitutional → Coherence → Telemetry

## 6. 統合テスト・ドキュメント

- [x] 6.1 統合テスト — `audit --constitutional-score --coherence-score --telemetry-score` の全オプション併用
- [x] 6.2 既存テストの regression 確認 — `python3 -m pytest scripts/rl/tests/ -v`
- [x] 6.3 CLAUDE.md の適応度関数セクションに Constitutional Score の説明を追加
