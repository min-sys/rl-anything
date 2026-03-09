## ADDED Requirements

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

### Requirement: optimize.py は共通モジュールを使用する

`optimize.py` は行数定数と行数チェックロジックを `scripts/lib/line_limit.py` から import しなければならない（MUST）。ローカルに `MAX_SKILL_LINES` / `MAX_RULE_LINES` を定義してはならない（MUST NOT）。

#### Scenario: import パスの確認
- **WHEN** optimize.py のソースコードを確認する
- **THEN** `scripts.lib.line_limit` からの import が存在する

#### Scenario: ローカル定数の除去
- **WHEN** optimize.py 内を `MAX_SKILL_LINES` または `MAX_RULE_LINES` の代入文で検索する
- **THEN** 一致する箇所が存在しない

### Requirement: run-loop.py は共通モジュールを使用する

`run-loop.py` は行数定数と行数チェックロジックを `scripts/lib/line_limit.py` から import しなければならない（MUST）。ローカルに `MAX_SKILL_LINES` / `MAX_RULE_LINES` / `_check_line_limit()` を定義してはならない（MUST NOT）。

#### Scenario: import パスの確認
- **WHEN** run-loop.py のソースコードを確認する
- **THEN** `scripts.lib.line_limit` からの import が存在する

#### Scenario: ローカル定義の除去
- **WHEN** run-loop.py 内を `MAX_SKILL_LINES` または `MAX_RULE_LINES` の代入文、または `def _check_line_limit` で検索する
- **THEN** 一致する箇所が存在しない

### Requirement: discover.py は共通定数を使用する

`discover.py` は行数定数を `scripts/lib/line_limit.py` から import しなければならない（MUST）。

#### Scenario: import パスの確認
- **WHEN** discover.py のソースコードを確認する
- **THEN** `scripts.lib.line_limit` からの import が存在する

#### Scenario: ローカル定数の除去
- **WHEN** discover.py 内を `MAX_SKILL_LINES` または `MAX_RULE_LINES` の代入文で検索する
- **THEN** 一致する箇所が存在しない
