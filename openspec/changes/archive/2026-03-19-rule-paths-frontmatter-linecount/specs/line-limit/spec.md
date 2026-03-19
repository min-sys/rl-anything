Closes: #31

## MODIFIED Requirements

### Requirement: 行数制限チェックの共通モジュール

`scripts/lib/line_limit.py` に行数制限チェックの共通実装を提供しなければならない（MUST）。定数 `MAX_SKILL_LINES`（500）、`MAX_RULE_LINES`（3）、`MAX_PROJECT_RULE_LINES`（5）を Single Source of Truth として定義する。

ルールファイル（`.claude/rules/` 配下）の行数カウントは、YAML frontmatter（`---` 区切りブロック）を除外したコンテンツ部分のみで行わなければならない（MUST）。スキルファイルの行数カウントは全体行数のまま変更しない。

#### Scenario: 共通関数のインターフェース
- **WHEN** `check_line_limit(target_path, content)` を呼び出す
- **THEN** コンテンツの行数がファイル種別に応じた上限以下なら `True`、超過なら `False` を返す

#### Scenario: ルールファイルの判定（グローバル・frontmatter あり）
- **WHEN** `target_path` がグローバルルールで、`content` に5行の YAML frontmatter と3行のコンテンツがある（全体8行）
- **THEN** コンテンツ行数3行で判定し、`MAX_RULE_LINES`（3）以内なので `True` を返す

#### Scenario: ルールファイルの判定（グローバル・frontmatter なし）
- **WHEN** `target_path` がグローバルルールで、`content` に frontmatter がなく3行のコンテンツがある
- **THEN** 全体行数3行で判定し、`MAX_RULE_LINES`（3）以内なので `True` を返す

#### Scenario: ルールファイルの判定（プロジェクト・frontmatter あり）
- **WHEN** `target_path` がプロジェクトルールで、`content` に4行の YAML frontmatter と5行のコンテンツがある（全体9行）
- **THEN** コンテンツ行数5行で判定し、`MAX_PROJECT_RULE_LINES`（5）以内なので `True` を返す

#### Scenario: ルールファイルの判定（frontmatter ありで超過）
- **WHEN** `target_path` がグローバルルールで、`content` に5行の YAML frontmatter と4行のコンテンツがある（全体9行）
- **THEN** コンテンツ行数4行で判定し、`MAX_RULE_LINES`（3）を超過するので `False` を返す

#### Scenario: スキルファイルの判定（frontmatter は除外しない）
- **WHEN** `target_path` がスキルファイルで、`content` に frontmatter を含む全体行数が500行以下
- **THEN** 全体行数で判定し `True` を返す（frontmatter 除外は行わない）

#### Scenario: 超過時の警告出力
- **WHEN** 行数が上限を超過する
- **THEN** stderr に `行数超過: {lines}/{max_lines}行（{file_type}制限）` の警告を出力する

## ADDED Requirements

### Requirement: frontmatter 除外のコンテンツ行数取得関数

`scripts/lib/frontmatter.py` に `count_content_lines(content: str) -> int` を提供しなければならない（MUST）。YAML frontmatter（`---` で始まり `---` で閉じるブロック）を除外した本文部分の行数を返す。

#### Scenario: frontmatter ありのコンテンツ

- **WHEN** `content` が `---\npaths:\n  - "**/*.py"\n---\n# Rule Title\nLine 1\nLine 2` である
- **THEN** `3` を返す（`# Rule Title`, `Line 1`, `Line 2` の3行）

#### Scenario: frontmatter なしのコンテンツ

- **WHEN** `content` が `# Rule Title\nLine 1\nLine 2` である
- **THEN** `3` を返す（全体行数と同じ）

#### Scenario: frontmatter のみ（コンテンツなし）

- **WHEN** `content` が `---\npaths:\n  - "**/*.py"\n---` で、閉じ `---` の後にコンテンツがない
- **THEN** `0` を返す

#### Scenario: 閉じられていない frontmatter

- **WHEN** `content` が `---\npaths:` で始まるが閉じ `---` がない
- **THEN** 全体行数を返す（不正な frontmatter は frontmatter として扱わない）

#### Scenario: 閉じ `---` 後の空行を含むコンテンツ

- **WHEN** `content` が `---\npaths:\n  - "**/*.py"\n---\n\n# Rule Title\nLine 1` である（閉じ `---` の直後に空行がある）
- **THEN** `3` を返す（空行を含めてコンテンツとしてカウントする：空行 + `# Rule Title` + `Line 1`）

### Requirement: audit の行数チェックがルールの frontmatter を除外する

`audit.py` の `check_line_limits()` はルールファイルの行数を `count_content_lines()` でカウントしなければならない（MUST）。

#### Scenario: frontmatter 付きルールの行数チェック

- **WHEN** `check_line_limits()` がルールファイルを検査し、そのファイルに YAML frontmatter がある
- **THEN** frontmatter を除外したコンテンツ行数で制限と比較する

#### Scenario: スキルファイルの行数チェック（変更なし）

- **WHEN** `check_line_limits()` がスキルファイルを検査する
- **THEN** 全体行数で制限と比較する（従来通り）

### Requirement: suggest_separation が frontmatter 除外行数で判定する

`line_limit.py` の `suggest_separation()` はルールファイルの行数超過判定を frontmatter 除外のコンテンツ行数で行わなければならない（MUST）。`excess_lines` もコンテンツ行数ベースで算出する。

#### Scenario: frontmatter 付きルールの分離提案

- **WHEN** グローバルルールに5行の frontmatter と5行のコンテンツがある（全体10行）
- **THEN** コンテンツ行数5行で判定し、超過2行（5 - MAX_RULE_LINES=3）として `SeparationProposal` を返す

#### Scenario: frontmatter のおかげで制限内

- **WHEN** グローバルルールに4行の frontmatter と3行のコンテンツがある（全体7行）
- **THEN** コンテンツ行数3行で判定し、制限内なので `None` を返す
