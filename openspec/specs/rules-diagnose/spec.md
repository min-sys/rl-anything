## ADDED Requirements

### Requirement: 孤立ルールを検出する
`diagnose_rules()` は、どのスキルや CLAUDE.md からも参照されていないルールファイルを `orphan_rule` issue として検出しなければならない（MUST）。

#### Scenario: ルールがスキルから参照されている
- **WHEN** `.claude/rules/commit-version.md` が存在し、いずれかのスキルの SKILL.md 内でそのルール名またはファイル名が言及されている
- **THEN** 当該ルールは `orphan_rule` として検出されない

#### Scenario: ルールがどこからも参照されていない
- **WHEN** `.claude/rules/obsolete-rule.md` が存在し、どのスキル・CLAUDE.md・他のルールからも参照されていない
- **THEN** `{"type": "orphan_rule", "file": "...obsolete-rule.md", "detail": {"name": "obsolete-rule"}, "source": "diagnose_rules"}` が出力される

### Requirement: 陳腐化ルールを検出する
`diagnose_rules()` は、ルール内で参照しているファイルパスやスキル名が存在しない場合、`stale_rule` issue として検出しなければならない（MUST）。

#### Scenario: ルール内の参照先が存在する
- **WHEN** `.claude/rules/aws-auth.md` 内で言及されたコマンドやパスがすべて有効
- **THEN** 当該ルールは `stale_rule` として検出されない

#### Scenario: ルール内の参照先が存在しない
- **WHEN** `.claude/rules/deploy.md` 内で `scripts/deploy.sh` を参照しているが、そのファイルが存在しない
- **THEN** `{"type": "stale_rule", "file": "...deploy.md", "detail": {"path": "scripts/deploy.sh", "line": 2}, "source": "diagnose_rules"}` が出力される

### Requirement: 孤立ルール検出は coherence.py の結果を活用する
`diagnose_rules()` は、coherence.py の `score_efficiency()` が返す `orphan_rules` 情報を活用しつつ、スキルからの参照チェック（CLAUDE.md に加え SKILL.md 内の言及）を追加で行わなければならない（MUST）。

#### Scenario: coherence.py が孤立と判定したがスキルから参照されている
- **WHEN** coherence.py が `.claude/rules/commit-version.md` を `orphan_rules` に含めているが、いずれかの SKILL.md 内でそのルール名が言及されている
- **THEN** 当該ルールは `orphan_rule` として検出されない（スキル参照で補完）

### Requirement: 閾値は定数から参照する
`diagnose_rules()` が使用する閾値はモジュールレベル定数または coherence.py の THRESHOLDS dict から取得しなければならない（MUST）。

### Requirement: 診断結果は統一フォーマットで出力する
`diagnose_rules()` は `List[Dict]` を返し、各要素は `{"type": str, "file": str, "detail": dict, "source": str}` フォーマットでなければならない（MUST）。

#### Scenario: 問題がない場合
- **WHEN** すべてのルールが正常
- **THEN** 空のリストを返す
