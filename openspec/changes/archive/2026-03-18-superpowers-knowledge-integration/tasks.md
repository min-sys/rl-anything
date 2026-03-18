## 1. 合理化防止テーブル生成（pitfall_manager 拡張）

- [x] 1.1 `scripts/lib/pitfall_manager.py` に合理化パターン検出関数 `detect_rationalization_patterns(corrections)` を追加。RATIONALIZATION_* 定数は `scripts/lib/skill_evolve.py` に配置（ROOT_CAUSE_JACCARD_THRESHOLD 等の既存定数と同居）。RATIONALIZATION_SKIP_KEYWORDS でスキップキーワードを定義
- [x] 1.2 `generate_rationalization_table(corrections, usage, errors)` を追加。corrections のスキップパターンをテレメトリ（手戻り率、エラー率）と突合してテーブル生成
- [x] 1.3 既存 pitfall との Jaccard 重複チェックを統合。重複時は既存 pitfall にテレメトリデータをエンリッチ
- [x] 1.4 `pitfall_hygiene()` に合理化テーブル生成を統合。data_insufficient ガード付き
- [x] 1.5 テスト追加: detect_rationalization_patterns / generate_rationalization_table の単体テスト + 既存 pitfall 重複時のエンリッチテスト

## 2. CSO チェック軸（skill_quality fitness 拡張）

- [x] 2.1 CSO 定数を定義: `CSO_SUMMARY_THRESHOLD = 0.5`, `CSO_TRIGGER_BONUS = 0.1`, `CSO_MAX_TRIGGER_BONUS = 0.3`, `CSO_ACTION_BONUS = 0.1`, `CSO_MAX_DESCRIPTION_LENGTH = 1024`, `CSO_LENGTH_PENALTY = -0.1`, `CSO_WEIGHT`（skill_quality 内の重み）
- [x] 2.2 `scripts/rl/fitness/skill_quality.py` 内に `check_cso_compliance(skill_path)` 関数を追加。description vs 本文の Jaccard 類似度、トリガーワード有無、行動促進形式、長さ制限をチェック
- [x] 2.3 skill_quality.py の既存 7 軸（headings/frontmatter/examples/ng_ok/line_length/arguments/workflow）に CSO を 8 軸目として統合。メインスコアリングループで呼び出し
- [x] 2.4 テスト追加: 要約ペナルティ / トリガー語ボーナス / 行動促進ボーナスの各ケース + description なしスキルのフォールバック

## 3. 証拠提示義務パターン（verification_catalog 拡張）

- [x] 3.1 `scripts/lib/verification_catalog.py` の VERIFICATION_CATALOG に `evidence-before-claims` パターンを追加。content_patterns に検出キーワード定義
- [x] 3.2 `detect_evidence_verification(project_dir: Path) -> Dict[str, Any]` 関数を追加（既存 detect 関数の `fn(project_dir: Path)` シグネチャに準拠）。corrections は内部で telemetry_query 経由で取得し、証拠要求パターン（「テスト実行して」「確認して」「動作確認」等）を検出
- [x] 3.3 既存の content-aware install check で evidence 系ルール/スキルの導入済み判定を追加
- [x] 3.4 テスト追加: パターン検出 + 導入済み判定 + EVIDENCE_MIN_PATTERNS ガードのテスト

## 4. 知見ルール追加

- [x] 4.1 `.claude/rules/verify-before-claim.md` を追加（3行以内）: 完了主張の前に検証コマンドの実行結果を提示する義務
- [x] 4.2 `.claude/rules/root-cause-first.md` を追加（3行以内）: 修正提案の前に根本原因を調査する義務

## 5. evolve パイプライン統合

- [x] 5.1 evolve の Housekeeping フェーズに合理化テーブル生成呼び出しを追加
- [x] 5.2 evolve レポートに「合理化防止テーブル」セクションを追加（テーブルが生成された場合のみ）
- [x] 5.3 discover の RECOMMENDED_ARTIFACTS に `evidence-before-claims` エントリを追加

## 6. テスト・検証

- [x] 6.1 全新規関数の pytest 通過確認（1563 passed, 0 failed）
- [x] 6.2 既存テスト（hooks/, skills/, scripts/tests/, scripts/rl/tests/）の regression なし確認
- [x] 6.3 `claude plugin validate` の通過確認（marketplace.json の既存 schema 警告のみ、今回の変更に無関係）
