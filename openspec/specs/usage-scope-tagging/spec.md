## ADDED Requirements

### Requirement: Dynamic plugin skill map

`_load_plugin_skill_map()` は `installed_plugins.json` を読み込み、`{skill_name: plugin_name}` マッピングを返す。`.claude/skills/` と `skills/` の両レイアウトに対応する。

#### Scenario: Plugin skill detection

- **WHEN** installed_plugins.json に `openspec@openspec` プラグインが登録されている
- **AND** そのプラグインの installPath 配下に `skills/openspec-propose/` がある
- **THEN** `_load_plugin_skill_map()` は `{"openspec-propose": "openspec", ...}` を返す

#### Scenario: Multiple plugins

- **WHEN** `openspec@openspec` と `rl-anything@rl-anything` の両方がインストールされている
- **THEN** 各プラグインのスキルがそれぞれのプラグイン名にマッピングされる

#### Scenario: Backward compatibility

- **WHEN** `_load_plugin_skill_names()` が呼ばれる
- **THEN** `_load_plugin_skill_map()` のキーセットが frozenset として返される

### Requirement: No observe.py modification

observe.py への scope フィールド追加は行わない。レポート生成時に `_load_plugin_skill_map()` で動的分類する。

#### Scenario: Existing records unmodified

- **WHEN** usage.jsonl に scope フィールドのないレコードが含まれる
- **THEN** レポート生成時にプラグインマップで動的に分類される
