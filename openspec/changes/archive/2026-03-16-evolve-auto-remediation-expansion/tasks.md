## 1. MEMORY.md 自動整理

- [x] 1.1 `fix_stale_memory()` を remediation.py に実装（MEMORY.md からポインタ行削除）
- [x] 1.2 FIX_DISPATCH に `stale_memory` → `fix_stale_memory` を登録
- [x] 1.3 `_RATIONALE_TEMPLATES` に stale_memory の auto_fixable 用テンプレート追加
- [x] 1.4 MEMORY.md near_limit issue 生成ロジックを audit.py に追加（既存 `NEAR_LIMIT_RATIO`（0.8）× MEMORY_LIMIT = 160行を再利用）
- [x] 1.5 `fix_stale_memory` と near_limit のテスト追加

## 2. スキル分割提案

- [x] 2.1 `make_split_candidate_issue()` を issue_schema.py に追加（`SPLIT_CANDIDATE_CONFIDENCE = 0.70` を issue_schema.py 先頭定数に定義）
- [x] 2.2 reorganize.py の出力に `issues` フィールド追加（split_candidates → issue_schema 変換）
- [x] 2.3 `fix_split_candidate()` を remediation.py に実装（LLM で分割案テキスト生成、ファイル変更なし）
- [x] 2.4 FIX_DISPATCH/VERIFY_DISPATCH に `split_candidate` を登録
- [x] 2.5 split_candidate のテスト追加

## 3. pitfall Cold 層自動アーカイブ + Pre-flight スクリプト化

- [x] 3.1 Cold 層定義を拡張（Graduated + Candidate → + New）、アーカイブ優先順位の実装。`CAP_EXCEEDED_CONFIDENCE = 0.90`（pitfall_manager.py）、`PREFLIGHT_MATURITY_RATIO = 0.50`（pitfall_manager.py）を定数定義
- [x] 3.2 pitfall_hygiene() の返却値に `issues` + `preflight_candidates` フィールド追加
- [x] 3.3 `fix_pitfall_archive()` を remediation.py に実装（Cold 層→pitfalls-archive.md 移動、優先順位順）
- [x] 3.4 FIX_DISPATCH に `cap_exceeded`/`line_guard` → `fix_pitfall_archive` を登録
- [x] 3.5 VERIFY_DISPATCH に `_verify_pitfall_archive` を登録
- [x] 3.6 Pre-flight スクリプト化候補検出を pitfall_hygiene() に追加（成熟条件判定 + suggest_preflight_script() 連携）
- [x] 3.7 `preflight_scriptification` issue の FIX_DISPATCH + VERIFY_DISPATCH 登録（proposable、テンプレート表示のみ）
- [x] 3.8 pitfall archive + Pre-flight のテスト追加

## 4. 重複統合の proposable 昇格

- [x] 4.1 `compute_confidence_score()` で `duplicate` の confidence を similarity ベースに変更。`DUPLICATE_PROPOSABLE_SIMILARITY = 0.75`、`DUPLICATE_PROPOSABLE_CONFIDENCE = 0.60`（remediation.py 先頭定数）を定義
- [x] 4.2 `generate_proposals()` の duplicate セクションで LLM 統合案テキスト生成を追加
- [x] 4.3 duplicate 昇格のテスト追加

## 5. verify 廃止 + archive 軽量チェック

- [x] 5.1 openspec-archive-change SKILL.md にタスク完了率チェック手順を追加（`ARCHIVE_COMPLETION_THRESHOLD = 0.80` を SKILL.md 内定数として定義、80% 未満で警告）
- [x] 5.2 openspec-verify-change SKILL.md を削除
- [x] 5.3 ファネル分析から verify フェーズを除外（evolve SKILL.md の Analytics セクション修正）
- [x] 5.4 CLAUDE.md からverify-change の記載を除外

## 6. 統合テスト + ドキュメント

- [x] 6.1 evolve dry-run で新 issue type が正しく分類・表示されることを確認
- [x] 6.2 evolve 通常実行で auto_fixable が正しく修正されることを確認
- [x] 6.3 MEMORY.md の該当エントリ更新
