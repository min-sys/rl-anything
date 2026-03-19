## Why

rl-anything がルールを生成・最適化する際、適用対象が特定ファイルパターンに限定できるケースでも `paths` frontmatter を提案していない。また、現在の行数制限チェックは frontmatter を含めた全体行数でカウントしており、`paths` や `description` 等の frontmatter を追加すると本文が3行でも制限超過になる。これにより `paths` frontmatter 活用へのインセンティブが阻害されている。Closes: #31

## What Changes

- ルール生成・最適化時（reflect / optimize / remediation）に、ルールの適用対象が特定ファイルパターンに限定可能な場合は `paths` frontmatter を自動提案する
- `line_limit.py` の `check_line_limit()` と `suggest_separation()` を frontmatter 除外のコンテンツ行数でカウントするよう変更
- `audit.py` の `check_line_limits()` も同様に frontmatter 除外カウントに統一
- `frontmatter.py` に frontmatter 除外のコンテンツ行数取得ユーティリティを追加

## Capabilities

### New Capabilities
- `paths-frontmatter-suggestion`: ルール生成・最適化時に `paths` frontmatter パターンを自動提案する機能

### Modified Capabilities
- `line-limit`: 行数カウントを frontmatter 除外のコンテンツ部分のみに変更

## Impact

- `scripts/lib/line_limit.py`: `check_line_limit()`, `suggest_separation()` のカウントロジック変更
- `scripts/lib/frontmatter.py`: コンテンツ行数取得関数追加
- `skills/audit/scripts/audit.py`: `check_line_limits()` のカウントロジック変更
- `scripts/reflect_utils.py`: paths 提案ロジック追加
- `skills/reflect/scripts/reflect.py`: paths 提案の表示
- `skills/genetic-prompt-optimizer/scripts/optimize.py`: 最適化後の paths 提案
- `skills/evolve/scripts/remediation.py`: remediation での paths 提案
- `skills/prune/scripts/prune.py`: `detect_dead_globs()` を `parse_frontmatter()` ベースにリファクタ、`paths` / `globs` 両キー対応
- `scripts/lib/path_extractor.py`: `audit.py` の `_extract_paths_outside_codeblocks()` を共有モジュールとして抽出
- 既存テスト（`test_line_limit.py`, `test_collect_issues.py`, `test_remediation.py`）の期待値更新
