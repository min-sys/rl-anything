## ADDED Requirements

### Requirement: Generic evaluation mode for global skills

global スキルの最適化時、`claude -p` の実行ディレクトリをユーザーのホームディレクトリに変更し、プロジェクト固有の CLAUDE.md がコンテキストに含まれないようにする。

#### Scenario: LLM evaluation without project context

- **WHEN** scope が `global` のスキルを `_llm_evaluate()` で評価する
- **THEN** `claude -p` の `cwd` がユーザーのホームディレクトリ（`Path.home()`）に設定される

#### Scenario: Mutation without project context

- **WHEN** scope が `global` のスキルで `mutate()` を実行する
- **THEN** `claude -p` の `cwd` がユーザーのホームディレクトリに設定される

#### Scenario: Crossover without project context

- **WHEN** scope が `global` のスキルで `crossover()` を実行する
- **THEN** `claude -p` の `cwd` がユーザーのホームディレクトリに設定される

#### Scenario: Project skill uses current directory

- **WHEN** scope が `project` のスキルで最適化を実行する
- **THEN** `claude -p` の `cwd` は変更されない（現在のプロジェクトディレクトリのまま）

### Requirement: Workflow hints availability in generic mode

global スキルの汎用評価モードでも、ワークフロー分析ヒントは利用可能であること。

#### Scenario: Workflow hints loaded via plugin path

- **WHEN** scope が `global` で `cwd` がホームに変更されている
- **THEN** ワークフローヒントは `__file__` ベースのパスから正常に読み込まれる
