## ADDED Requirements

### Requirement: Bootstrap スキルがカタログから推奨設定を表示する
`/rl-anything:bootstrap` を実行すると、`recommended-globals.json` から推奨設定一覧をカテゴリ別（essential/recommended/optional）に表示し、各エントリの名前・説明・種別（rule/hook）を提示する。essential カテゴリはデフォルト選択済みとして表示する。

#### Scenario: 初回実行で全カテゴリが表示される
- **WHEN** ユーザーが `/rl-anything:bootstrap` を実行する
- **THEN** essential/recommended/optional の 3 カテゴリに分かれた推奨設定一覧が表示される
- **AND** 各エントリに名前・説明・種別（rule/hook）が含まれる

#### Scenario: essential カテゴリがデフォルト選択済み
- **WHEN** 推奨設定一覧が表示される
- **THEN** essential カテゴリのエントリはデフォルトで選択済みとして提示される
- **AND** recommended/optional は未選択状態で提示される

### Requirement: 既存設定との衝突検出
適用前に `~/.claude/rules/` と `~/.claude/settings.json` を走査し、カタログエントリと同名または同機能の既存設定を検出した場合、衝突として警告を表示する。衝突がある場合はスキップを推奨する。

#### Scenario: 同名ルールが既に存在する
- **WHEN** `~/.claude/rules/avoid-bash-builtin.md` が既に存在する状態で bootstrap を実行する
- **THEN** `avoid-bash-builtin` エントリに「既存設定あり — スキップ推奨」の警告が表示される

#### Scenario: 同一 matcher の hook が既に存在する
- **WHEN** `~/.claude/settings.json` に Bash matcher の PreToolUse hook が既に登録されている
- **THEN** `check-bash-builtin` hook エントリに衝突警告が表示される

### Requirement: ユーザー選択後に適用
ユーザーが適用対象を選択した後、選択されたエントリのみを `~/.claude/rules/` や `~/.claude/settings.json` に書き込む。書き込みは LLM の Write/Edit ツール経由で行い、Claude Code の permission mode による承認を経る。

#### Scenario: 選択した rule のみが適用される
- **WHEN** ユーザーが `avoid-bash-builtin` と `verification` を選択して適用を確認する
- **THEN** `~/.claude/rules/avoid-bash-builtin.md` と `~/.claude/rules/verification.md` のみが作成される
- **AND** 未選択のエントリは作成されない

#### Scenario: hook 適用時にスクリプトとsettings.json が更新される
- **WHEN** ユーザーが `check-bash-builtin` hook を選択して適用を確認する
- **THEN** hook スクリプトが `~/.claude/hooks/` に配置される
- **AND** LLM の Edit ツール経由で `~/.claude/settings.json` に PreToolUse hook エントリを追加する。Claude Code の permission mode による承認を経る（MUST）。スクリプトが直接 settings.json を書き換えてはならない（MUST NOT）

### Requirement: カタログ形式
`recommended-globals.json` は以下のフィールドを持つエントリの配列として定義する: `name`（string）、`type`（"rule" | "hook"）、`category`（"essential" | "recommended" | "optional"）、`description`（string）、`hook_config`（hook の場合のみ: matcher, event_type）、`template`（生成するファイルの内容テンプレート）。

#### Scenario: カタログ JSON が正しい構造を持つ
- **WHEN** `recommended-globals.json` をパースする
- **THEN** 各エントリが name, type, category, description, template フィールドを持つ
- **AND** type が "hook" のエントリは hook_config フィールドも持つ
