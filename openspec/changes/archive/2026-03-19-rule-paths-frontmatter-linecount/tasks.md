Closes: #31

## 0. パス抽出の共通モジュール化

- [x] 0.1 `skills/audit/scripts/audit.py` の `_extract_paths_outside_codeblocks()` を `scripts/lib/path_extractor.py` に抽出し、`audit.py` から import に変更

## 1. frontmatter コンテンツ行数取得関数

- [x] 1.1 `scripts/lib/frontmatter.py` に `count_content_lines(content: str) -> int` を追加。YAML frontmatter（`---` 区切り）を除外したコンテンツ部分の行数を返す
- [x] 1.2 `scripts/tests/test_frontmatter.py` に `count_content_lines` のテストを追加（frontmatter あり/なし/のみ/閉じられていない/閉じ後空行 の5パターン）

## 2. line_limit.py の frontmatter 除外対応

- [x] 2.1 `scripts/lib/line_limit.py` の `check_line_limit()` を変更：ルールファイル（`.claude/rules/`）の場合のみ `count_content_lines()` でカウントする
- [x] 2.2 `scripts/lib/line_limit.py` の `suggest_separation()` を変更：ルールファイルの `excess_lines` を frontmatter 除外のコンテンツ行数で算出する
- [x] 2.3 `scripts/tests/test_line_limit.py` にfrontmatter 付きルールのテストケースを追加（frontmatter あり制限内/超過、frontmatter なしの既存テストが引き続きパスすること）

## 3. audit.py の frontmatter 除外対応

- [x] 3.1 `skills/audit/scripts/audit.py` の `check_line_limits()` でルールファイルの行数を `count_content_lines()` でカウントするよう変更
- [x] 3.2 `skills/audit/scripts/tests/test_collect_issues.py` に frontmatter 付きルールの行数チェックテストを追加

## 4. paths frontmatter 提案機能

- [x] 4.0 `suggest_paths_frontmatter()` で `path_extractor.py` を使う実装
- [x] 4.1 `scripts/reflect_utils.py` に `PathsSuggestion` dataclass と `suggest_paths_frontmatter(message: str, project_root: Path) -> Optional[PathsSuggestion]` を追加。`PATHS_SUGGESTION_MIN_FILES` 定数を定義し、`path_extractor.py` を使ってファイルパスパターンを抽出しグロブパターンに変換
- [x] 4.2 `scripts/tests/test_reflect_utils.py` に `suggest_paths_frontmatter` のテストを追加（8件以上：パスあり/なし/単一ファイル/共通拡張子パターン/混合ディレクトリ/混合拡張子/深いネスト/拡張子なし）

## 5. paths 提案の統合

- [x] 5.1 `skills/reflect/scripts/reflect.py` で correction 反映後に `suggest_paths_frontmatter()` を呼び出し、提案があれば表示する（`globs:` 代替の注記を含む）
- [x] 5.2 `skills/genetic-prompt-optimizer/scripts/optimize.py` で最適化後に paths 提案を表示する（`corrections` の `message` フィールドを入力）
- [x] 5.3 `skills/evolve/scripts/remediation.py` の `generate_proposals()` で `rule_candidate` issue に `paths_suggestion` フィールドを付加する

## 6. 検証

- [x] 6.1 全テストスイートの実行（`python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v`）でリグレッションがないことを確認（1604 passed）
- [x] 6.2 frontmatter 付きルールファイル（実環境の `.claude/rules/` 配下）で `check_line_limit()` が正しく frontmatter 除外カウントすることを手動確認

## 7. detect_dead_globs リファクタ

- [x] 7.1 `skills/prune/scripts/prune.py` の `detect_dead_globs()` を `parse_frontmatter()` ベースにリファクタし、`paths` / `globs` 両キーを処理するよう対応
- [x] 7.2 `detect_dead_globs()` のテストを追加（`paths` のみ / `globs` のみ / 両キー存在）
