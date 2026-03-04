## 1. frontmatter 共通化 + description 抽出

- [x] 1.0 `scripts/lib/frontmatter.py` を作成（`parse_frontmatter()` + `extract_description()`）
- [x] 1.1 `prune.py` に `extract_skill_summary()` を追加（`extract_description()` のラッパー）
- [x] 1.2 `prune.py` に `suggest_recommendation()` を追加（キーワードベース一次判定）
- [x] 1.3 `detect_zero_invocations()` の返却値に `description` と `recommendation` フィールドを付与
- [x] 1.4 `detect_decay_candidates()` の返却値に `description` と `recommendation` フィールドを付与
- [x] 1.5 `safe_global_check()` の返却値に `description` と `recommendation` フィールドを付与
- [x] 1.6 `reflect_utils._parse_rule_frontmatter()` を `frontmatter.parse_frontmatter()` に置換
- [x] 1.7 `scripts/lib/frontmatter.py` のユニットテスト（parse_frontmatter, extract_description）
- [x] 1.8 `extract_skill_summary()` と `suggest_recommendation()` のユニットテスト

## 2. SKILL.md の instructions を更新

- [x] 2.1 Step 2 に「候補スキルの SKILL.md を Read で読み取る」手順を追加
- [x] 2.2 Step 2 に推薦ラベル最終判定のチェックリストを記載（archive推奨 / keep推奨 / 要確認）
- [x] 2.3 Step 3 を2段階承認フローに変更（テキスト一覧表示 → AskUserQuestion 3択）
- [x] 2.4 Step 3 に個別選択フロー（各候補に対する AskUserQuestion 3択）のルールを記載
- [x] 2.5 description 空文字時に "(説明なし)" 表示 + SKILL.md 全文 Read で要約生成のルールを記載

## 3. テスト・検証

- [x] 3.1 prune.py の既存テストが全てパスすることを確認
- [x] 3.2 `run_prune()` の出力に description と recommendation が含まれることを手動確認
- [x] 3.3 AskUserQuestion の全 options が4つ以下であることを spec で確認
