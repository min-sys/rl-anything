## ADDED Requirements

### Requirement: Global scope issue の proposable 昇格
remediation の `classify_issue()` において、`scope == "global"` かつ `confidence >= PROPOSABLE_CONFIDENCE` の issue を `proposable` に分類する（MUST）。`auto_fixable` にはしない（MUST）。

#### Scenario: Global scope + 高 confidence が proposable になる
- **WHEN** `tool_usage_rule_candidate` issue（scope="global", confidence=0.85）が classify_issue() に渡された
- **THEN** category = "proposable" に分類される

#### Scenario: Global scope は auto_fixable にならない
- **WHEN** `tool_usage_rule_candidate` issue（scope="global", confidence=0.95）が classify_issue() に渡された
- **THEN** category = "proposable" に分類される（confidence が高くても auto_fixable にならない）

#### Scenario: Global scope + 低 confidence は manual_required のまま
- **WHEN** `tool_usage_hook_candidate` issue（scope="global", confidence=0.3）が classify_issue() に渡された
- **THEN** category = "manual_required" に分類される

### Requirement: FIX_DISPATCH に global rule 適用アクションを追加
`FIX_DISPATCH["tool_usage_rule_candidate"]` として `fix_global_rule()` を登録する（MUST）。この関数はユーザー承認後に `~/.claude/rules/` に rule ファイルを書き込む（MUST）。

#### Scenario: rule ファイルの書き込み
- **WHEN** ユーザーが `tool_usage_rule_candidate` の修正を承認した
- **THEN** `~/.claude/rules/{filename}` に rule コンテンツが書き込まれる

#### Scenario: 書き込み先ディレクトリの自動作成
- **WHEN** `~/.claude/rules/` ディレクトリが存在しない
- **THEN** ディレクトリを作成してから rule ファイルを書き込む

### Requirement: FIX_DISPATCH に hook scaffold アクションを追加
`FIX_DISPATCH["tool_usage_hook_candidate"]` として `fix_hook_scaffold()` を登録する（MUST）。この関数は hook スクリプトを生成し、settings.json 登録案を表示する（MUST）。settings.json の自動書き換えは行わない（MUST）。

#### Scenario: hook scaffold の実行
- **WHEN** ユーザーが `tool_usage_hook_candidate` の修正を承認した
- **THEN** hook スクリプトが `~/.claude/rl-anything/hooks/` に書き込まれ、settings.json 登録案が表示される

### Requirement: VERIFY_DISPATCH に global rule 検証を追加
`VERIFY_DISPATCH["tool_usage_rule_candidate"]` として rule ファイルの存在確認と内容検証を行う（MUST）。

#### Scenario: rule 書き込み後の検証
- **WHEN** `fix_global_rule()` が実行された後に検証が行われる
- **THEN** 対象パスにファイルが存在し、内容が3行以内であることを確認する

### Requirement: Rationale 生成の拡張
`generate_rationale()` が `tool_usage_rule_candidate` と `tool_usage_hook_candidate` に対応する（MUST）。

#### Scenario: rule candidate の rationale
- **WHEN** `tool_usage_rule_candidate` issue の rationale を生成する
- **THEN** 「Bash で {command} が {count} 回使用されています。{alternative} ツールで代替可能です。global rule の追加を提案します。」のようなテキストが返される

#### Scenario: hook candidate の rationale
- **WHEN** `tool_usage_hook_candidate` issue の rationale を生成する
- **THEN** 「Bash での Built-in 代替可能コマンド使用を自動検出する PreToolUse hook の追加を提案します。」のようなテキストが返される
