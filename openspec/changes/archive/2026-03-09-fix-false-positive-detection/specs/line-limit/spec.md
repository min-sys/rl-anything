## ADDED Requirements

### Requirement: プロジェクトルールの行数制限を分離する

`check_line_limit()` は、プロジェクト固有ルールファイル（`<project>/.claude/rules/`）に対して `MAX_PROJECT_RULE_LINES`（5行）を適用しなければならない（MUST）。グローバルルールファイル（`~/.claude/rules/`）に対しては従来通り `MAX_RULE_LINES`（3行）を適用する。

#### Scenario: プロジェクトルールは5行まで許容
- **WHEN** `target_path` が `my-project/.claude/rules/rule.md` で content が4行
- **THEN** `check_line_limit()` は `True` を返す

#### Scenario: グローバルルールは3行制限を維持
- **WHEN** `target_path` が `/Users/user/.claude/rules/rule.md` で content が4行
- **THEN** `check_line_limit()` は `False` を返す

## MODIFIED Requirements

### Requirement: 行数制限チェックの共通モジュール

`scripts/lib/line_limit.py` に行数制限チェックの共通実装を提供しなければならない（MUST）。定数 `MAX_SKILL_LINES`（500）、`MAX_RULE_LINES`（3）、`MAX_PROJECT_RULE_LINES`（5）を Single Source of Truth として定義する。

#### Scenario: 共通関数のインターフェース
- **WHEN** `check_line_limit(target_path, content)` を呼び出す
- **THEN** コンテンツの行数がファイル種別に応じた上限以下なら `True`、超過なら `False` を返す

#### Scenario: ルールファイルの判定（グローバル）
- **WHEN** `target_path` に `.claude/rules/` が含まれ、かつ `str(Path.home())` がパスに含まれる
- **THEN** `MAX_RULE_LINES`（3）を上限として判定する

#### Scenario: ルールファイルの判定（プロジェクト）
- **WHEN** `target_path` に `.claude/rules/` が含まれ、かつ `str(Path.home())` がパスに含まれない
- **THEN** `MAX_PROJECT_RULE_LINES`（5）を上限として判定する

#### Scenario: スキルファイルの判定
- **WHEN** `target_path` に `.claude/rules/` が含まれない
- **THEN** `MAX_SKILL_LINES`（500）を上限として判定する

#### Scenario: 超過時の警告出力
- **WHEN** 行数が上限を超過する
- **THEN** stderr に `行数超過: {lines}/{max_lines}行（{file_type}制限）` の警告を出力する
