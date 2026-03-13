## ADDED Requirements

### Requirement: Auto-fix for untagged reference candidates
remediation パイプラインで untagged_reference_candidates を自動修正する。システムは スキルの frontmatter に `type: reference` を追加する fix 関数を FIX_DISPATCH に SHALL 登録する。

#### Scenario: Skill with existing frontmatter but no type
- **WHEN** SKILL.md に frontmatter（`---` ブロック）が存在するが type フィールドが無い場合
- **THEN** 既存 frontmatter 内に `type: reference` 行を追加する

#### Scenario: Skill with no frontmatter at all
- **WHEN** SKILL.md に frontmatter ブロックが存在しない場合
- **THEN** ファイル先頭に `---\ntype: reference\n---\n` を追加する

#### Scenario: YAML parse error during fix
- **WHEN** frontmatter の YAML パースに失敗した場合
- **THEN** fix をスキップし、`record_outcome()` に `error: "yaml_parse_error"` を記録する
- **THEN** `fixed=False` を返却する

#### Scenario: Empty file
- **WHEN** 対象ファイルが空の場合
- **THEN** `fixed=False` を返却する

### Requirement: Verification for reference type fix
VERIFY_DISPATCH に untagged_reference_candidates の検証を SHALL 追加する。

#### Scenario: Verify type field was added
- **WHEN** fix 適用後に検証を実行する
- **THEN** 対象ファイルの frontmatter に `type: reference` が存在することを確認する

### Requirement: Frontmatter update utility
`scripts/lib/frontmatter.py` に `update_frontmatter()` 関数を SHALL 追加する。

#### Scenario: Update existing frontmatter
- **WHEN** ファイルに既存の frontmatter がある場合
- **THEN** 指定されたキー/値を frontmatter に追加・更新し、ファイルを書き戻す

#### Scenario: Add frontmatter to file without one
- **WHEN** ファイルに frontmatter が存在しない場合
- **THEN** ファイル先頭に `---` ブロックを追加し、指定されたキー/値を含める

### Normative Statements

- The system SHALL use `update_frontmatter()` from `scripts/lib/frontmatter.py` for all frontmatter modifications.
- The system SHALL NOT modify any content outside the frontmatter block.
- On YAML parse error, the system SHALL skip the fix and record the error.
- On empty file, the system SHALL return `fixed=False` without error.
- The verification function SHALL confirm the presence of `type: reference` in the frontmatter after fix.
