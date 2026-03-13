Related: #26

## 1. Global Rule 候補生成（tool_usage_analyzer 拡張）

- [ ] 1.1 `tool_usage_analyzer.py` に `generate_rule_candidates(builtin_replaceable, existing_rules_dir)` を追加。builtin_replaceable リストから rule 候補を生成、既存ルールとの重複排除、3行以内制約を実装
- [ ] 1.2 `generate_rule_candidates()` のテストを追加（正常系、重複排除、空入力、行数制限）

## 2. Hook テンプレート生成（tool_usage_analyzer 拡張）

- [ ] 2.1 `tool_usage_analyzer.py` に `generate_hook_template(builtin_replaceable, output_dir)` を追加。PreToolUse hook のシェルスクリプトを生成（stdin JSON → jq でコマンド先頭語検査 → block/pass）
- [ ] 2.2 `generate_hook_template()` のテストを追加（スクリプト内容、実行権限、出力パス）
- [ ] 2.3 settings.json 登録案のテキスト生成関数 `format_settings_diff(hook_path, existing_settings)` を追加

## 3. Discover 統合

- [ ] 3.1 `discover.py` の `run_discover()` で tool_usage_patterns に `rule_candidates` と `hook_candidates` を追加出力
- [ ] 3.2 discover 統合テストを追加（rule_candidates/hook_candidates が tool_usage_patterns に含まれることを検証）

## 4. Remediation Global Scope 対応

- [ ] 4.1 `remediation.py` の `classify_issue()` で global scope + confidence >= PROPOSABLE_CONFIDENCE を `proposable` に昇格するロジックを追加
- [ ] 4.2 `compute_confidence_score()` に `tool_usage_rule_candidate`（0.85）と `tool_usage_hook_candidate`（0.75）の静的 confidence を追加
- [ ] 4.3 `generate_rationale()` に `tool_usage_rule_candidate` と `tool_usage_hook_candidate` のテンプレートを追加
- [ ] 4.4 classify_issue の global scope 昇格テスト、confidence_score テスト、rationale テストを追加

## 5. FIX_DISPATCH / VERIFY_DISPATCH 拡張

- [ ] 5.1 `fix_global_rule(issue)` を実装（`~/.claude/rules/` にファイル書き込み、ディレクトリ自動作成）
- [ ] 5.2 `fix_hook_scaffold(issue)` を実装（hook スクリプト生成 + settings.json 差分表示）
- [ ] 5.3 `VERIFY_DISPATCH` に rule ファイル存在確認 + 行数検証を追加
- [ ] 5.4 FIX_DISPATCH/VERIFY_DISPATCH のテストを追加（書き込み、検証、エラーケース）

## 6. Evolve 統合・E2E

- [ ] 6.1 evolve の discover フェーズ表示に rule_candidates/hook_candidates セクションを追加
- [ ] 6.2 discover → remediation の issue 変換ロジックを追加（tool_usage_patterns → issue リスト変換）
- [ ] 6.3 E2E テスト：discover 検出 → remediation 分類 → proposable 提案の一連フロー

## 7. Bootstrap スキル

- [ ] 7.1 `skills/bootstrap/recommended-globals.json` にカタログ定義を作成（初期エントリ: D9 テーブルの 8 件）
- [ ] 7.2 `scripts/lib/bootstrap.py` を実装: カタログ読み込み、既存設定との衝突検出（rules 同名チェック + hooks 同一 matcher チェック）、テンプレート展開
- [ ] 7.3 `skills/bootstrap/SKILL.md` を作成: カタログ表示 → ユーザー選択 → 衝突検出 → Write/Edit ツールで適用のフロー
- [ ] 7.4 bootstrap.py のテストを追加（カタログ読み込み、衝突検出、テンプレート展開）

## 8. Candidate Tracking（evolve 統合）

- [ ] 8.1 `skills/evolve/scripts/candidate_tracker.py` を実装: `~/.claude/rules/` と settings.json hooks を走査し、カタログ未登録の設定を検出。プロジェクト固有キーワードフィルタ含む。`PROVEN_THRESHOLD`, `TESTING_MINIMUM`, `PROJECT_SPECIFIC_PATTERNS` をモジュール定数として定義
- [ ] 8.2 テレメトリ効果測定: corrections.jsonl/usage.jsonl から候補ルール/hook の参照回数を集計し、"testing" / "proven" 状態を判定
- [ ] 8.3 evolve Diagnose ステージに candidate_tracker 呼び出しを追加、結果を `evolve-state.json` の `global_candidates` に保存
- [ ] 8.4 evolve レポートに「カタログ昇格候補」セクションを追加（proven 候補のみ diff 形式で表示）
- [ ] 8.5 candidate_tracker のテストを追加（検出、フィルタ、効果測定、状態永続化）
