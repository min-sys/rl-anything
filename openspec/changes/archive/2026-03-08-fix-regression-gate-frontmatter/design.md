Closes: #20

## Context

`_regression_gate()` は現在4つのチェック（空コンテンツ、行数制限、禁止パターン、pitfallパターン）を実装しているが、構造的メタデータの保持検証がない。LLM パッチが YAML frontmatter を削除しても gate を通過し、スキルが壊れた状態で適用される。

元コンテンツの frontmatter 有無は `run()` メソッド内で `original_content` として保持されているが、`_regression_gate()` からは参照できない。

## Goals / Non-Goals

**Goals:**
- 元スキルに frontmatter がある場合、パッチ後も frontmatter が存在することを gate で保証する
- 既存の gate チェックと同じパターン（`(bool, reason)` タプル返却）に統一

**Non-Goals:**
- frontmatter の内容（キーの一致等）の検証は行わない（LLM が意図的に変更する可能性がある）
- frontmatter なしスキルに frontmatter を追加する機能

## Decisions

### 1. インスタンス変数による元コンテンツ参照

`run()` 内で `self.original_content = original_content` を設定し、`_regression_gate()` は `self.original_content` を参照する。gate メソッドのシグネチャは変更しない。

**理由**: 既存の gate メソッドがインスタンス状態を多用（`self._check_line_limit`、`self.FORBIDDEN_PATTERNS` 等）しており、インスタンス変数での状態共有と一貫。テスト時は `optimizer.original_content = "---\n..."` で直接設定可能。

**代替案 1**: `_regression_gate(content, original_content=None)` にオプショナル引数を追加 → 他の gate チェックがすべてインスタンス状態を参照しているため一貫性に欠ける。不採用。
**代替案 2**: 別メソッド `_check_frontmatter_preserved()` を追加 → gate の一元管理が崩れるため不採用。

### 2. frontmatter 検出は `---` 先頭行のみ

元コンテンツが `---` で始まるかどうかだけを判定し、パッチ後も同様に `---` で始まることを要求する。

**理由**: YAML パースは不要。Claude Code スキルの frontmatter は常に `---` で始まる慣習であり、シンプルな文字列チェックで十分。

### 3. 既存ユーティリティとの関係

`scripts/lib/frontmatter.py` はファイルパスベース（`Path` 引数）で frontmatter を解析するユーティリティだが、gate はインメモリの content 文字列を検査するため直接文字列チェックが適切。同じ `startswith("---")` パターンで一貫（frontmatter.py:26, evaluator.py:74）。

### 4. bloat_control.py との関係

`validate_artifact()` はステートレスな単体検証（original 不要）。frontmatter チェックは before/after 比較が必要なため、`_regression_gate()` に限定する。

## Risks / Trade-offs

- [元コンテンツに `---` があるがfrontmatterでないケース] → スキルファイルでは実質発生しない。許容範囲
- [LLM が frontmatter を意図的に書き換えるケース] → 内容チェックはしないため、キーの変更は許容される。存在のみ保証
