## ADDED Requirements

### Requirement: Global rule 候補の生成
`generate_rule_candidates()` は builtin_replaceable の検出結果から `~/.claude/rules/` 向けの rule 候補を生成する（MUST）。各候補は `{filename, content, target_command, alternative_tool, occurrence_count}` 形式で返す（MUST）。

#### Scenario: builtin_replaceable パターンから rule 候補を生成
- **WHEN** builtin_replaceable に `grep → Grep` が 10 回検出されている
- **THEN** `{filename: "avoid-bash-grep.md", content: "# Bash grep 禁止\ngrep の代わりに Grep ツールを使用する。パイプ内での使用は除外。", target_command: "grep", alternative_tool: "Grep", occurrence_count: 10}` が返される

#### Scenario: 既存ルールとの重複排除
- **WHEN** `~/.claude/rules/avoid-bash-grep.md` が既に存在する
- **THEN** `grep` に関する rule 候補は生成されない

#### Scenario: 複数コマンドの一括生成
- **WHEN** builtin_replaceable に `grep → Grep`（10回）、`cat → Read`（5回）、`find → Glob`（3回）が検出されている
- **THEN** 全コマンドのマッピングを含む 1 件の統合 rule 候補が返される。ファイル名は `avoid-bash-builtin.md`、content は 3 行以内で全マッピングを含む

#### Scenario: rule コンテンツの行数制限
- **WHEN** rule 候補が生成される
- **THEN** content は3行以内である（MUST）（rules-style.md 準拠）

#### Scenario: builtin_replaceable が空の場合
- **WHEN** builtin_replaceable の検出結果が空
- **THEN** 空のリストが返される
