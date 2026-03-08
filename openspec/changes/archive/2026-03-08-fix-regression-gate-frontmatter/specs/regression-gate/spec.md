## ADDED Requirements

### Requirement: frontmatter 保持チェック
元スキルに YAML frontmatter（`---` で始まるブロック）が存在する場合、パッチ後のコンテンツにも frontmatter が存在しなければならない（MUST）。frontmatter が消失している場合はゲート不合格としなければならない（MUST）。

#### Scenario: frontmatter 付きスキルが frontmatter を保持
- **WHEN** 元コンテンツが `---` で始まり、パッチ後コンテンツも `---` で始まる
- **THEN** このチェックは合格とし、他のゲートチェックに進まなければならない（MUST）

#### Scenario: frontmatter 付きスキルから frontmatter が消失
- **WHEN** 元コンテンツが `---` で始まるが、パッチ後コンテンツが `---` で始まらない
- **THEN** スコア 0.0 を返さなければならず（MUST）、ゲート不合格理由として `frontmatter_lost` を記録しなければならない（MUST）

#### Scenario: 元スキルに frontmatter がない場合
- **WHEN** 元コンテンツが `---` で始まらない
- **THEN** frontmatter チェックはスキップし、他のゲートチェックのみ適用しなければならない（MUST）
