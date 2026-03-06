## 1. audit.py に構造化データ出力を追加

- [x] 1.1 `collect_issues(project_dir)` 関数を audit.py に追加。既存の `check_line_limits`、`build_memory_health_section` 内部データ、`detect_duplicates_simple` の結果を `{"type", "file", "detail", "source"}` 形式の issue リストとして返す
- [x] 1.2 `collect_issues` のユニットテストを追加（violations、stale_refs、near_limits、duplicates の各ケース）

## 2. remediation.py の作成 — 分類エンジン

- [x] 2.1 `skills/evolve/scripts/remediation.py` を作成。`confidence_score` と `impact_scope` の算出ロジックを実装する（ファイルパスから impact_scope を判定、超過量や問題タイプから confidence_score を算出）
- [x] 2.2 `classify_issues(issues)` 関数を実装。confidence_score と impact_scope の閾値ベースで auto_fixable / proposable / manual_required に動的分類する
- [x] 2.3 分類ロジックのユニットテストを追加（CLAUDE.md の stale ref → proposable 格上げ、1行超過 → auto_fixable 格下げ、大幅超過 → manual_required 格上げ 等）

## 3. remediation.py — 修正アクション

- [x] 3.1 `generate_rationale(issue, category)` 関数を実装。各修正アクションに対する修正理由テキストを生成する
- [x] 3.2 `fix_stale_references(issues)` 関数を実装。対象ファイルから陳腐化参照の行を削除する。修正前の内容をメモリに保持する（ロールバック用）
- [x] 3.3 `generate_proposals(issues)` 関数を実装。行数制限違反に対する reference 切り出し案、肥大化警告に対するセクション分割案を rationale 付きで生成する

## 4. remediation.py — 検証エンジン

- [x] 4.1 `verify_fix(fixed_file, original_issue)` 関数を実装。修正されたファイルに対して該当する検出関数を再実行し、元の問題の解消を確認する
- [x] 4.2 `check_regression(fixed_file, original_content)` 関数を実装。見出し構造の保持、参照リンクの有効性、Markdown フォーマットの整合性を検証する
- [x] 4.3 `rollback_fix(fixed_file, original_content)` 関数を実装。regression 検出時に修正前の内容に復元し、問題を manual_required に格上げする
- [x] 4.4 検証エンジンのユニットテストを追加（fix verification 成功/失敗、regression 検出 → ロールバック）

## 5. remediation.py — テレメトリ記録

- [x] 5.1 `record_outcome(issue, category, action, result, user_decision, rationale)` 関数を実装。`~/.claude/rl-anything/remediation-outcomes.jsonl` に結果を追記する。dry-run 時は記録しない
- [x] 5.2 テレメトリ記録のユニットテストを追加（正常記録、dry-run スキップ）

## 6. evolve パイプラインへの統合

- [x] 6.1 `evolve.py` の `run_evolve()` に Remediation フェーズ（audit の後）を追加。`collect_issues()` → `classify_issues()` → 結果を `result["phases"]["remediation"]` に格納。`dry_run=True` の場合は分類結果のみ格納し、修正アクションは実行しない
- [x] 6.2 `SKILL.md` に Step 7.5（Remediation フェーズ）のフロー記述を追加。confidence-based 分類、rationale 付き一括承認、個別承認、regression check、ロールバック、テレメトリ記録を記載

## 7. 動作確認

- [x] 7.1 `python3 -m pytest` で全テストが通ることを確認
- [x] 7.2 `--dry-run` モードで evolve を実行し、Remediation フェーズの分類結果（confidence_score、impact_scope 含む）が正しく出力されることを確認
