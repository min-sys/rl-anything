## 1. Mitigation Trend（対策効果トレンド）

- [x] 1.1 evolve-state.json に tool_usage_snapshot フィールドを追加（save_evolve_state 拡張）
- [x] 1.2 evolve レポート生成時に前回 snapshot との差分を算出するユーティリティ関数を実装
- [x] 1.3 SKILL.md Step 10.2 のレポートテンプレートにトレンド表示（↑↓→ 件数差・増減率%・pp差）を追加
- [x] 1.4 初回実行時（snapshot なし）の「前回データなし」表示を実装
- [x] 1.5 テスト: snapshot 保存・読込・差分算出・初回表示・ratio型トレンド

## 2. Remediation auto_fixable 拡張

- [x] 2.1 classify_issue の line_limit 判定を修正: 絶対行数差ベース。excess == 1 → confidence 0.95 で auto_fixable 昇格
- [x] 2.2 FIX_DISPATCH に line_limit_violation の fix 関数を追加（LLM 1パス圧縮）。失敗時フォールバック（proposable 降格 + エラー記録）を含む
- [x] 2.3 VERIFY_DISPATCH の既存 _verify_line_limit_violation が fix 後に正しく検証できることを確認
- [x] 2.4 テスト: 1行超過→auto_fixable 分類、2行超過→proposable 維持、LLM失敗→proposable降格

## 3. Reference Type Auto-fix

- [x] 3.0a `update_frontmatter()` を `scripts/lib/frontmatter.py` に追加（既存 parse_frontmatter のパースロジックを再利用、frontmatter 更新・書き戻し対応）
- [x] 3.0b `untagged_reference_candidates` を audit の `collect_issues()` に統合（issue structure: `{type: "untagged_reference_candidates", file: str, detail: {skill_name: str}, source: "detect_untagged_reference_candidates"}`)
- [x] 3.0c `compute_confidence_score` + `generate_rationale` + `generate_proposals` に `untagged_reference_candidates` エントリ追加（confidence 0.90）
- [x] 3.1 fix_untagged_reference 関数を実装（`update_frontmatter()` を使用して type: reference 追加）
- [x] 3.2 frontmatter なしの場合のハンドリング（先頭に frontmatter ブロック追加）
- [x] 3.3 FIX_DISPATCH に untagged_reference_candidates エントリを追加
- [x] 3.4 _verify_untagged_reference 検証関数を実装し VERIFY_DISPATCH に追加
- [x] 3.5 テスト: frontmatter あり/なし両パターンの fix・verify、YAMLパースエラー→fixスキップ、空ファイル→fixed=False

## 4. Fitness Bootstrap モード

- [x] 4.1 BOOTSTRAP_MIN=5 定数を fitness_evolution.py に追加
- [x] 4.2 bootstrap 分析ロジックを実装（承認率・平均スコア・スコア分布）
- [x] 4.3 status: "bootstrap" 返却と簡易分析結果の構造を定義
- [x] 4.4 evolve SKILL.md Step 8 のレポートテンプレートに bootstrap 表示を追加
- [x] 4.5 テスト: 0-4件→insufficient_data、5-29件→bootstrap、30件以上→既存動作

## 5. Bash Ratio Threshold 表示

- [x] 5.1 SKILL.md Step 10.2 の Bash 割合表示に目標閾値（≤40%）と達成/未達を追加
- [x] 5.2 BUILTIN_THRESHOLD, SLEEP_THRESHOLD もレポートに併記
- [x] 5.3 テスト: 閾値表示が正しくフォーマットされることを確認

## 6. 統合テスト・spec 同期

- [x] 6.1 evolve dry-run を実行し、全変更が正しくレポートに反映されることを確認
- [x] 6.2 openspec specs を更新（実装結果と spec の差異があれば修正）
