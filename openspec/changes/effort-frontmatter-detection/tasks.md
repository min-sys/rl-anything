## 1. Core モジュール

- [x] 1.1 `scripts/lib/effort_detector.py` 新規作成 — `infer_effort_level()` + `detect_missing_effort_frontmatter()`
- [x] 1.2 `scripts/lib/issue_schema.py` に `MISSING_EFFORT_CANDIDATE` 定数 + `MEC_*` detail フィールド + `make_missing_effort_issue()` factory 追加

## 2. パイプライン統合

- [x] 2.1 `skills/audit/scripts/audit.py` の `collect_issues()` に effort 未設定検出を追加
- [x] 2.2 `skills/evolve/scripts/remediation.py` に `fix_missing_effort()` + `_verify_missing_effort()` 追加
- [x] 2.3 `FIX_DISPATCH` / `VERIFY_DISPATCH` に `MISSING_EFFORT_CANDIDATE` エントリ登録

## 3. テスト

- [x] 3.1 `scripts/tests/test_effort_frontmatter.py` 新規作成 — TestInferEffortLevel (7テスト) + TestDetectMissingEffortFrontmatter (5テスト) + TestFixMissingEffort (2テスト) + TestMakeEffortIssue (1テスト)
- [ ] 3.2 全テストスイート回帰テスト実行

## 4. ドキュメント

- [ ] 4.1 CLAUDE.md に effort_detector モジュール情報追記
- [ ] 4.2 CHANGELOG 追記
- [ ] 4.3 MEMORY.md に change エントリ追加
