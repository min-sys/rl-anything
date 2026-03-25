## 1. Issue Schema 拡張

- [x] 1.1 `scripts/lib/issue_schema.py` に `SKILL_TRIAGE_CREATE`, `SKILL_TRIAGE_UPDATE`, `SKILL_TRIAGE_SPLIT`, `SKILL_TRIAGE_MERGE` 定数と `make_skill_triage_issue()` factory 関数を追加。`SKILL_TRIAGE_SPLIT` は既存 `SPLIT_CANDIDATE`（reorganize 行数ベース）とは別定数（D7）
- [x] 1.2 issue_schema のテスト追加（各 action type の issue 生成を検証）

## 2. Trigger Eval Generator

- [x] 2.1 `scripts/lib/trigger_eval_generator.py` を新規作成: `generate_eval_set()` 関数（sessions.jsonl + usage.jsonl → evals.json）
- [x] 2.2 should_trigger クエリ抽出ロジック実装（スキル使用セッションの user_prompts から抽出、マルチプロンプト対応: トリガーワード一致度優先選択、フォールバック先頭優先）
- [x] 2.3 should_not_trigger クエリ生成ロジック実装（near-miss `confidence_weight: 1.0` + unrelated `confidence_weight: 0.6` の2ソース、near-miss 優先採用）
- [x] 2.4 eval set バランス調整ロジック実装（MIN_EVAL_QUERIES=3, TARGET_EVAL_QUERIES=10, サンプリング）
- [x] 2.5 ファイル出力実装（`~/.claude/rl-anything/eval-sets/<skill-name>.json`）
- [x] 2.6 trigger_eval_generator のテスト追加（正常系 + データ不足 + バランス調整 + フォーマット互換性）

## 3. Skill Triage Engine

- [x] 3.1 `scripts/lib/skill_triage.py` を新規作成: `triage_skill()` 関数（単一スキル判定）
- [x] 3.2 CREATE 判定ロジック実装（missed_skill 高 + 既存スキルなし）
- [x] 3.3 UPDATE 判定ロジック実装（missed_skill 高 + 既存スキルあり + near-miss）
- [x] 3.4 SPLIT 判定ロジック実装（`skill_triggers.py` トリガーワードでグループ化 → Jaccard 距離階層クラスタリング、`CLUSTER_DISTANCE_THRESHOLD=0.70`、`SPLIT_CATEGORY_THRESHOLD=3`）。issue type は `SKILL_TRIAGE_SPLIT`（D7: reorganize の `SPLIT_CANDIDATE` とは別）
- [x] 3.5 MERGE 判定ロジック実装（2スキル間の should_trigger クエリ Jaccard 類似度、`MERGE_OVERLAP_THRESHOLD=0.40`）。`similarity.py` の `jaccard_coefficient()` 再利用。結果は prune `merge_proposals` と統合、`source: "triage"` で区別（D8）
- [x] 3.6 confidence スコアリング実装（D10 計算式: `BASE_CONFIDENCE` + `session_bonus` + `evidence_bonus`。定数: `SESSION_BONUS_RATE=0.05`, `EVIDENCE_BONUS_RATE=0.03`, `MAX_SESSION_BONUS=0.25`, `MAX_EVIDENCE_BONUS=0.10`）
- [x] 3.7 `triage_all_skills()` 関数実装（全スキル一括判定 + アクション別グループ化）
- [x] 3.8 skill-creator 連携提案生成（UPDATE 判定時の eval set パス + コマンド例）
- [x] 3.9 skill_triage のテスト追加（5択判定の各パターン + confidence + batch + graceful degradation）

## 4. Evolve 統合

- [x] 4.1 `skills/evolve/scripts/evolve.py` の Diagnose ステージに triage 呼び出しを追加（discover の後、audit の前）
- [x] 4.2 triage 結果を `collect_issues()` に統合（issue_schema 経由）
- [x] 4.3 triage 結果を evolve レポートに表示（アクション別サマリー + skill-creator 提案）
- [x] 4.4 データ不足時の graceful degradation 実装（triage スキップ + warning 出力）
- [x] 4.5 evolve 統合のテスト追加（triage 結果が phases に含まれること、データ不足時のスキップ）

## 5. Discover 強化

- [x] 5.1 `detect_missed_skills()` の結果に `eval_set_path` / `eval_set_status` フィールドを追加
- [x] 5.2 discover のテスト更新（新フィールドの検証）

## 6. 統合テスト・ドキュメント

- [x] 6.1 全モジュール統合テスト（evolve Diagnose → triage → issue → report の E2E フロー）
- [x] 6.2 CLAUDE.md 更新（skill triage の説明追加）
- [x] 6.3 MEMORY.md にプロジェクト構造エントリ追加
