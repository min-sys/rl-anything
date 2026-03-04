## 1. audit — Memory Health セクション

- [x] 1.1 `skills/audit/scripts/audit.py` に定数 `NEAR_LIMIT_RATIO = 0.8` を追加
- [x] 1.2 `build_memory_health_section(artifacts, project_dir)` を追加（auto-memory 探索に `reflect_utils.read_auto_memory()` 使用、陳腐化参照検出 + 肥大化警告 + 改善提案 + 読み取りエラー時スキップ）
- [x] 1.3 `generate_report()` に `project_dir: Optional[Path] = None` パラメータ追加し、Memory Health セクションを Line Limit Violations の直後に挿入
- [x] 1.4 `run_audit()` から `generate_report()` に `project_dir=proj` を渡す

## 2. reflect — Memory Update Candidates

- [x] 2.1 `skills/reflect/scripts/reflect.py` に定数 `MIN_KEYWORD_MATCH = 3` と `_MEMORY_STOP_WORDS` を追加
- [x] 2.2 `find_memory_update_candidates(corrections, project_root)` を追加（`similarity.tokenize()` 再利用、ストップワード除外、duplicate_found 除外）
- [x] 2.3 `build_output()` に `memory_update_candidates` フィールドを追加
- [x] 2.4 `skills/reflect/SKILL.md` に Step 7.5（MEMORY 更新候補の表示）を追加

## 3. テスト

- [x] 3.1 `scripts/tests/test_audit_quality_trends.py` に Memory Health テスト追加（陳腐化検出、肥大化警告、問題なし、コードブロック除外、レポート統合）
- [x] 3.2 `skills/reflect/scripts/tests/test_reflect.py` に memory_update_candidates テスト追加（マッチ検出、マッチなし、duplicate除外、3語未満除外）
- [x] 3.3 全テスト実行して既存テストが壊れていないことを確認

## 4. バージョン更新

- [x] 4.1 CHANGELOG.md にエントリ追加
- [x] 4.2 `.claude-plugin/plugin.json` のバージョンを 0.15.4 → 0.15.5 に更新
