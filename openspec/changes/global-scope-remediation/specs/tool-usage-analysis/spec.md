## MODIFIED Requirements

### Requirement: discover 統合
`run_discover()` の結果に `tool_usage_patterns` キーとしてツール利用分析結果を含める（MUST）。
`--tool-usage` フラグで有効化する（MUST）。デフォルトは無効。
tool_usage_patterns に `rule_candidates` と `hook_candidates` を含める（MUST）。

#### Scenario: フラグ有効時の結果統合
- **WHEN** `run_discover(tool_usage=True)` が呼ばれる
- **THEN** 結果辞書に `tool_usage_patterns` キーが含まれ、`builtin_replaceable`（ルール候補）、`repeating_patterns`（スキル候補）、`rule_candidates`（global rule 候補リスト）、`hook_candidates`（hook テンプレート候補リスト）が格納される

#### Scenario: フラグ無効時のスキップ
- **WHEN** `run_discover()` がデフォルト引数で呼ばれる
- **THEN** `tool_usage_patterns` キーは結果に含まれない

#### Scenario: セッションファイルが存在しない場合
- **WHEN** 対象プロジェクトのセッションディレクトリが存在しない
- **THEN** 空の結果を返し、エラーを発生させない（MUST）

#### Scenario: rule 候補が既存ルールと重複する場合
- **WHEN** `~/.claude/rules/` に対象コマンドのルールが既に存在する
- **THEN** その候補は `rule_candidates` に含まれない
