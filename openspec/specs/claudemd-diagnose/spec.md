## ADDED Requirements

### Requirement: CLAUDE.md 内の幻影参照を検出する
`diagnose_claudemd()` は、CLAUDE.md 内で言及されているスキル名やルール名が `.claude/skills/` や `.claude/rules/` に実在しない場合、`claudemd_phantom_ref` issue として検出しなければならない（MUST）。

#### Scenario: 言及されたスキルが実在する
- **WHEN** CLAUDE.md に `evolve` スキルが記載されており、`.claude/skills/evolve/SKILL.md` が存在する
- **THEN** `claudemd_phantom_ref` として検出されない

#### Scenario: 言及されたスキルが実在しない
- **WHEN** CLAUDE.md に `deprecated-skill` が記載されているが、`.claude/skills/deprecated-skill/` が存在しない
- **THEN** `{"type": "claudemd_phantom_ref", "file": "CLAUDE.md", "detail": {"name": "deprecated-skill", "ref_type": "skill", "line": 42}, "source": "diagnose_claudemd"}` が出力される

#### Scenario: プラグインスキルは除外する
- **WHEN** CLAUDE.md に `openspec-propose` が記載されており、これがプラグイン由来のスキル
- **THEN** `claudemd_phantom_ref` として検出されない（プラグインスキルは `.claude/skills/` に存在しなくても正常）

### Requirement: CLAUDE.md のスキルセクション欠落を検出する
`diagnose_claudemd()` は、`.claude/skills/` にスキルが存在するのに CLAUDE.md に Skills セクションがない場合、`claudemd_missing_section` issue として検出しなければならない（MUST）。セクション名の検出は prefix を許容し、`## Key Skills`、`## Available Skills` 等にもマッチしなければならない（MUST）。

#### Scenario: 標準的な Skills セクションがある
- **WHEN** CLAUDE.md に `## Skills` または `## スキル` セクションがあり、スキルが存在する
- **THEN** `claudemd_missing_section` として検出されない

#### Scenario: prefix 付き Skills セクションがある
- **WHEN** CLAUDE.md に `## Key Skills` セクションがあり、スキルが存在する
- **THEN** `claudemd_missing_section` として検出されない

#### Scenario: Skills セクションがないがスキルが存在する
- **WHEN** `.claude/skills/` に 3 つのスキルがあるが、CLAUDE.md に Skills セクションがない
- **THEN** `{"type": "claudemd_missing_section", "file": "CLAUDE.md", "detail": {"section": "skills", "skill_count": 3}, "source": "diagnose_claudemd"}` が出力される

### Requirement: CLAUDE.md が存在しない場合は空リストを返す
`diagnose_claudemd()` は、CLAUDE.md が存在しない場合、空のリストを返さなければならない（MUST）。

#### Scenario: CLAUDE.md が存在しない
- **WHEN** プロジェクトルートに CLAUDE.md が存在しない
- **THEN** 空のリストを返す

### Requirement: 診断結果は統一フォーマットで出力する
`diagnose_claudemd()` は `List[Dict]` を返し、各要素は `{"type": str, "file": str, "detail": dict, "source": str}` フォーマットでなければならない（MUST）。

#### Scenario: 問題がない場合
- **WHEN** CLAUDE.md が正常
- **THEN** 空のリストを返す
