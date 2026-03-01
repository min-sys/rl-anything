## 1. SKILL.md 更新

- [x] 1.1 genetic-prompt-optimizer/SKILL.md の frontmatter `name` を `optimize` に変更
- [x] 1.2 genetic-prompt-optimizer/SKILL.md の instructions を Claude への実行指示形式に書き換え（引数パース → スクリプト実行 → 結果表示）
- [x] 1.3 rl-loop-orchestrator/SKILL.md の instructions を Claude への実行指示形式に書き換え
- [ ] 1.4 `/optimize --dry-run` で SKILL.md が正しく読み込まれることを確認

## 2. README.md 更新

- [x] 2.1 Before（課題）セクションを追加: スキル/ルールの手動改善の問題点を記述
- [x] 2.2 What（概要）セクションを追加: 遺伝的アルゴリズムによる自動最適化の説明
- [x] 2.3 After（効果）セクションを追加: スラッシュコマンドUXと定量的品質管理の効果
- [x] 2.4 クイックスタートをスラッシュコマンド形式（`/optimize`, `/rl-loop`）に更新
- [x] 2.5 詳細リファレンスセクションに `python3 <PLUGIN_DIR>/...` 形式のコマンドを移動

## 3. CLAUDE.md 同期

- [x] 3.1 CLAUDE.md のクイックスタートセクションをスラッシュコマンド形式に更新
- [x] 3.2 CLAUDE.md のコンポーネント表・適応度関数・テストセクションは既存内容を維持

## 4. 検証

- [ ] 4.1 `/optimize --target <テスト対象> --dry-run` が正常に動作することを確認
- [ ] 4.2 `/rl-loop --target <テスト対象> --dry-run` が正常に動作することを確認
- [x] 4.3 README.md と CLAUDE.md のクイックスタートでコマンド形式・引数が一致していることを確認
