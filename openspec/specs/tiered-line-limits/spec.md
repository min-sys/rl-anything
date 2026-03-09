## ADDED Requirements

### Requirement: project rule は global rule と異なる行数制限を持つ

`check_line_limit()` は、プロジェクト固有ルール（`<project>/.claude/rules/`）に対して `MAX_PROJECT_RULE_LINES`（5行）を適用しなければならない（MUST）。グローバルルール（`~/.claude/rules/`）には従来通り `MAX_RULE_LINES`（3行）を適用する。

#### Scenario: プロジェクトルールは5行まで許容
- **WHEN** `check_line_limit()` に `<project>/.claude/rules/my-rule.md` と4行のコンテンツを渡す
- **THEN** `True` を返す

#### Scenario: プロジェクトルールは5行超過で拒否
- **WHEN** `check_line_limit()` に `<project>/.claude/rules/my-rule.md` と6行のコンテンツを渡す
- **THEN** `False` を返す

#### Scenario: グローバルルールは従来通り3行制限
- **WHEN** `check_line_limit()` に `~/.claude/rules/global-rule.md` と4行のコンテンツを渡す
- **THEN** `False` を返す

### Requirement: CLAUDE.md は行数制限を適用しない

audit の行数チェックにおいて、CLAUDE.md は行数制限違反として報告してはならない（MUST NOT）。`CLAUDEMD_WARNING_LINES`（300行）を超える場合は warning レベルの通知を出力しなければならない（MUST）。

#### Scenario: CLAUDE.md が300行を超えても制限違反にならない
- **WHEN** CLAUDE.md が350行である
- **THEN** `collect_issues()` は `line_limit` violation として報告しない

#### Scenario: CLAUDE.md が warning 閾値を超えると warning が出る
- **WHEN** CLAUDE.md が350行であり `CLAUDEMD_WARNING_LINES = 300` を超えている
- **THEN** audit は warning レベルの通知を出力する

#### Scenario: CLAUDE.md が warning 閾値以下なら warning なし
- **WHEN** CLAUDE.md が250行である
- **THEN** audit は warning を出力しない

### Requirement: CLAUDEMD_WARNING_LINES を定数として定義する

`scripts/lib/line_limit.py` に `CLAUDEMD_WARNING_LINES = 300` を定数として定義しなければならない（MUST）。

#### Scenario: 定数が定義されている
- **WHEN** `line_limit.py` のソースコードを確認する
- **THEN** `CLAUDEMD_WARNING_LINES = 300` が定義されている

### Requirement: MAX_PROJECT_RULE_LINES を定数として定義する

`scripts/lib/line_limit.py` に `MAX_PROJECT_RULE_LINES = 5` を定数として定義しなければならない（MUST）。

#### Scenario: 定数が定義されている
- **WHEN** `line_limit.py` のソースコードを確認する
- **THEN** `MAX_PROJECT_RULE_LINES = 5` が定義されている
