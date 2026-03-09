## MODIFIED Requirements

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
