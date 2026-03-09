## ADDED Requirements

### Requirement: orphan_rule issue type を廃止する

`diagnose_rules()` は orphan_rule 検出ロジックを削除しなければならない（MUST）。`.claude/rules/` は Claude が自動読み込みするため、現行のスキャン対象は全て auto-load ディレクトリ内にあり、orphan_rule 判定は事実上 dead code である。

#### Scenario: ルールがどこからも参照されていなくても orphan_rule は検出されない
- **WHEN** `.claude/rules/obsolete-rule.md` が存在し、どのスキル・CLAUDE.md・他のルールからも参照されていない
- **THEN** `diagnose_rules()` は `orphan_rule` を出力しない

#### Scenario: diagnose_rules の出力に orphan_rule type が含まれない
- **WHEN** `diagnose_rules()` を任意の環境で実行する
- **THEN** 出力される issue リストに `type: "orphan_rule"` の要素は含まれない

### Requirement: coherence.py の orphan_rules カウントも廃止する

`score_efficiency()` の orphan_rules カウントを削除しなければならない（MUST）。orphan_rule issue type の廃止に伴い、coherence スコアの Efficiency 軸からも除去する。

#### Scenario: coherence スコアに orphan_rules が影響しない
- **WHEN** `score_efficiency()` を実行する
- **THEN** orphan_rules は Efficiency スコアの計算に含まれない
