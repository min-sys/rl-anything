## MODIFIED Requirements

### Requirement: orphan_rule issue type を廃止する
`diagnose_rules()` は、orphan_rule 検出ロジックを削除しなければならない（MUST）。`.claude/rules/` は全て auto-load 対象であり、CLAUDE.md/SKILL.md からの参照有無に関わらずルールは有効であるため、orphan_rule 判定は不要である。

#### Scenario: ルールがスキルから参照されている
- **WHEN** `.claude/rules/commit-version.md` が存在し、いずれかのスキルの SKILL.md 内でそのルール名またはファイル名が言及されている
- **THEN** 当該ルールに関する issue は出力されない

#### Scenario: ルールがどこからも参照されていない
- **WHEN** `.claude/rules/obsolete-rule.md` が存在し、どのスキル・CLAUDE.md・他のルールからも参照されていない
- **THEN** orphan_rule は出力されない（auto-load 対象のため有効）

#### Scenario: stale_rule はファイル位置基準解決を適用する
- **WHEN** ルールファイル内にパス参照があり、プロジェクトルート基準では存在しないが、ルールファイルの親ディレクトリ基準では存在する
- **THEN** stale_rule として検出されない（D2 のファイル位置基準解決を適用）
