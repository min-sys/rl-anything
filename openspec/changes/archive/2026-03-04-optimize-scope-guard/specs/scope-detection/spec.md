## ADDED Requirements

### Requirement: Scope auto-detection from file path

optimize.py はターゲットスキルのファイルパスから scope を自動判定する。`~/.claude/skills/` 配下のファイルは `global`、それ以外は `project` と判定する。

#### Scenario: Global skill detection

- **WHEN** ターゲットパスが `~/.claude/skills/commit/SKILL.md` である
- **THEN** scope は `global` と判定される

#### Scenario: Project skill detection

- **WHEN** ターゲットパスが `/path/to/project/.claude/skills/my-skill/SKILL.md` である
- **THEN** scope は `project` と判定される

#### Scenario: Plugin skill detection

- **WHEN** ターゲットパスがプラグインディレクトリ（`~/.claude/rl-anything/skills/` 等）配下である
- **THEN** scope は `global` と判定される

### Requirement: Scope display in startup message

optimize.py は実行開始時にターゲットの scope を表示する。

#### Scenario: Global skill notification

- **WHEN** scope が `global` のターゲットで最適化を開始する
- **THEN** 「汎用評価モードで最適化します（プロジェクト固有のコンテキストは使用しません）」と表示される

#### Scenario: Project skill notification

- **WHEN** scope が `project` のターゲットで最適化を開始する
- **THEN** scope に関する特別な通知は表示されない（既存動作）

### Requirement: Scope label in SKILL.md target selection

SKILL.md のターゲット選択指示において、候補スキルに scope ラベルを表示する。

#### Scenario: Target list with scope labels

- **WHEN** LLM がターゲット候補をユーザーに提示する
- **THEN** 各候補に `[global]` または `[project]` ラベルが併記される
