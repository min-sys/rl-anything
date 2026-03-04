## 1. MEMORY 検証コンテキスト収集（audit.py）

- [x] 1.1 global memory 取得: 既存 `read_all_memory_entries()` を `tier == "global"` でフィルタして使用（新規関数不要）
- [x] 1.2 `scripts/reflect_utils.py` に `split_memory_sections(content, file_path)` を追加（`## ` 見出し単位で分割、見出しなし先頭は `_header` セクション）。audit.py と archive-memory-sync 両方から利用可能にする
- [x] 1.3 `skills/audit/scripts/audit.py` に `_extract_section_keywords(text)` を追加（ストップワード除外、2文字以下除外でキーワードリスト返却）。ストップワードは `_STOPWORDS` 定数として audit.py の先頭に定義する
- [x] 1.4 `skills/audit/scripts/audit.py` に `_find_archive_mentions(keywords, project_dir)` を追加（`openspec/changes/archive/` のディレクトリ名とキーワードをマッチ）
- [x] 1.5 `skills/audit/scripts/audit.py` に `build_memory_verification_context(project_dir)` を追加（セクション分割 → キーワード抽出 → grep → archive メンション → JSON 出力）
- [x] 1.6 global memory の PJ 固有セクション判定: PJ 名やPJ 固有キーワードを含むセクションのみを検証対象に含める

## 2. audit SKILL.md — LLM 検証ステップ

- [x] 2.1 `skills/audit/SKILL.md` に Step 1.5（Memory Semantic Verification）を追加: `build_memory_verification_context()` の出力を読み取り、各セクションを3段階判定（CONSISTENT / MISLEADING / STALE）で検証する手順を記載
- [x] 2.2 SKILL.md に判定基準チェックリストを記載（MISLEADING: キーワードが目立つ位置にあり誤解を招く、STALE: コードベースと矛盾）

## 3. archive-memory-sync（openspec-archive スキル拡張）

- [x] 3.1 `.claude/skills/openspec-archive-change/SKILL.md` の Step 5（archive 実行）の前に Step 4.5（Memory Sync）を追加: proposal.md と MEMORY を突合し、影響があれば更新ドラフトを AskUserQuestion で提示
- [x] 3.2 Memory Sync ステップに「影響なし → スキップ」「更新あり → ドラフト提示 → 承認/スキップ」のフローを記載

## 4. テスト

- [x] 4.1 `scripts/tests/test_audit_memory_verification.py` に `_split_memory_sections` のテスト追加（セクション分割、見出しなし先頭の `_header` 処理、空ファイル）
- [x] 4.2 `scripts/tests/test_audit_memory_verification.py` に `_extract_section_keywords` のテスト追加（ストップワード除外、短い単語除外、日本語キーワード保持）
- [x] 4.3 `scripts/tests/test_audit_memory_verification.py` に `_find_archive_mentions` のテスト追加（マッチあり、マッチなし、archive ディレクトリなし）
- [x] 4.4 `scripts/tests/test_audit_memory_verification.py` に `build_memory_verification_context` のテスト追加（正常系、MEMORY なし、読み取りエラー時スキップ）
- [x] 4.5 `scripts/tests/test_reflect_utils.py` に `split_memory_sections` のテスト追加（セクション分割、見出しなし先頭、空コンテンツ）
- [x] 4.6 全テスト実行して既存テストが壊れていないことを確認

## 5. バージョン更新

- [x] 5.1 CHANGELOG.md にエントリ追加
- [x] 5.2 `.claude-plugin/plugin.json` のバージョンを 0.15.5 → 0.15.6 に更新
