## ADDED Requirements

### Requirement: orphan_rule issue type を廃止する
`diagnose_rules()` は、orphan_rule 検出ロジックを削除しなければならない（MUST）。`.claude/rules/` は全て auto-load 対象であり、CLAUDE.md/SKILL.md からの参照有無に関わらずルールは有効であるため、orphan_rule 判定は不要である。

#### Scenario: ルールがスキルから参照されている
- **WHEN** `.claude/rules/commit-version.md` が存在し、いずれかのスキルの SKILL.md 内でそのルール名またはファイル名が言及されている
- **THEN** 当該ルールに関する issue は出力されない

#### Scenario: ルールがどこからも参照されていない
- **WHEN** `.claude/rules/obsolete-rule.md` が存在し、どのスキル・CLAUDE.md・他のルールからも参照されていない
- **THEN** orphan_rule は出力されない（auto-load 対象のため有効）

### Requirement: 陳腐化ルールを検出する
`diagnose_rules()` は、ルール内で参照しているファイルパスやスキル名が存在しない場合、`stale_rule` issue として検出しなければならない（MUST）。

#### Scenario: ルール内の参照先が存在する
- **WHEN** `.claude/rules/aws-auth.md` 内で言及されたコマンドやパスがすべて有効
- **THEN** 当該ルールは `stale_rule` として検出されない

#### Scenario: ルール内の参照先が存在しない
- **WHEN** `.claude/rules/deploy.md` 内で `scripts/deploy.sh` を参照しているが、そのファイルが存在しない
- **THEN** `{"type": "stale_rule", "file": "...deploy.md", "detail": {"path": "scripts/deploy.sh", "line": 2}, "source": "diagnose_rules"}` が出力される

#### Scenario: stale_rule はファイル位置基準解決を適用する
- **WHEN** ルールファイル内にパス参照があり、プロジェクトルート基準では存在しないが、ルールファイルの親ディレクトリ基準では存在する
- **THEN** stale_rule として検出されない（ファイル位置基準解決を適用）

### Requirement: 閾値は定数から参照する
`diagnose_rules()` が使用する閾値はモジュールレベル定数または coherence.py の THRESHOLDS dict から取得しなければならない（MUST）。

### Requirement: 診断結果は統一フォーマットで出力する
`diagnose_rules()` は `List[Dict]` を返し、各要素は `{"type": str, "file": str, "detail": dict, "source": str}` フォーマットでなければならない（MUST）。

#### Scenario: 問題がない場合
- **WHEN** すべてのルールが正常
- **THEN** 空のリストを返す
