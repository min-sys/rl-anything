## ADDED Requirements

### Requirement: Plugin skill origin detection
`skill_origin.py` はスキルファイルパスからその origin（plugin / global / custom）を判定する（MUST）。`installed_plugins.json` を優先ソースとし、存在しない場合はパスベースでフォールバックする。

#### Scenario: Plugin skill detected via installed_plugins.json
- **WHEN** `installed_plugins.json` に "rl-anything" プラグインが登録されており、スキルパスがそのプラグインのスキル名に一致する
- **THEN** `classify_skill_origin()` が `"plugin"` を返す

#### Scenario: Plugin skill detected via path fallback
- **WHEN** `installed_plugins.json` が存在しないが、スキルパスが `~/.claude/plugins/` 配下にある
- **THEN** `classify_skill_origin()` が `"plugin"` を返す

#### Scenario: Custom skill detection
- **WHEN** スキルパスがプロジェクトの `.claude/skills/` 配下にあり、`installed_plugins.json` にマッチしない
- **THEN** `classify_skill_origin()` が `"custom"` を返す

### Requirement: Protected skill check
`is_protected_skill(path)` はスキルが編集保護対象かを判定する（MUST）。plugin origin のスキルは保護対象とする。

#### Scenario: Plugin skill is protected
- **WHEN** `is_protected_skill()` に plugin origin のスキルパスを渡す
- **THEN** `True` を返す

#### Scenario: Custom skill is not protected
- **WHEN** `is_protected_skill()` にプロジェクト固有スキルのパスを渡す
- **THEN** `False` を返す

### Requirement: Local alternative suggestion
保護スキルへの編集が検出された場合、`suggest_local_alternative(skill_name, project_root)` がプロジェクト側の代替パスを返す（MUST）。

#### Scenario: Suggest references directory
- **WHEN** 保護スキル "openspec-verify-change" への知見追加が検出される
- **THEN** `{project_root}/.claude/skills/openspec-verify-change/references/pitfalls.md` を代替先として返す

#### Scenario: Existing local references
- **WHEN** 保護スキル "atlas-browser" に対してプロジェクト側に既に `references/pitfalls.md` が存在する
- **THEN** 既存ファイルのパスを返し、新規作成ではなく追記を提案する

### Requirement: Protection warning generation
保護スキルへの編集操作に対して警告メッセージを生成する（MUST）。警告にはスキル名、保護理由、代替先パスを含む。

#### Scenario: Warning message format
- **WHEN** 保護スキル "openspec-verify-change" への編集が検出される
- **THEN** 以下を含む警告を返す: スキル名、「プラグイン由来のため変更保護」の理由、ローカル代替先パス

### Requirement: Graceful degradation on invalid data
`installed_plugins.json` の異常状態に対して安全にフォールバックする（MUST）。

#### Scenario: installed_plugins.json is invalid JSON
- **WHEN** `installed_plugins.json` が不正 JSON（パースエラー）
- **THEN** パスベースフォールバックで origin 判定を継続する（例外を投げない）

#### Scenario: installed_plugins.json has unknown version
- **WHEN** `installed_plugins.json` の `version` フィールドが未知の形式（例: `"3.0"`）
- **THEN** 空の plugin skill map を返却し、パスベースフォールバックに委譲する

#### Scenario: Skill path does not exist
- **WHEN** `classify_skill_origin()` に存在しないスキルパスが渡される
- **THEN** `"custom"` を返却する（存在しないパスはプラグイン由来と判定しない）
