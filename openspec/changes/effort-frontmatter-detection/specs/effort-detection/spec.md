## ADDED Requirements

### Requirement: effort 未設定スキルの検出

`detect_missing_effort_frontmatter(project_dir)` は `.claude/skills/*/SKILL.md` を走査し、frontmatter に `effort` フィールドがないスキルを検出して返却する。

#### Scenario: effort 未設定スキルが存在する場合
- **WHEN** プロジェクトに effort 未設定のスキルが1つ以上ある
- **THEN** `applicable: True` と evidence リスト（skill_name, skill_path, proposed_effort, confidence, reason）を返す

#### Scenario: 全スキルに effort が設定済み
- **WHEN** プロジェクトの全スキルに effort が設定されている
- **THEN** `applicable: False` と空の evidence リストを返す

#### Scenario: スキルディレクトリが存在しない
- **WHEN** `.claude/skills/` ディレクトリが存在しない
- **THEN** `applicable: False` を返す

### Requirement: effort レベルの推定

`infer_effort_level(skill_path)` はスキルの特性から effort レベル（low/medium/high）を推定する。推定結果は `level`, `confidence`, `reason` を含む辞書を返す。

#### Scenario: disable-model-invocation スキル
- **WHEN** frontmatter に `disable-model-invocation: true` がある
- **THEN** `level: "low"`, `confidence: 0.90` を返す

#### Scenario: Agent を使用するスキル
- **WHEN** frontmatter の `allowed-tools` に `Agent` が含まれる
- **THEN** `level: "high"`, `confidence: 0.90` を返す

#### Scenario: 短いスキル
- **WHEN** コンテンツ行数が `LOW_LINE_THRESHOLD`（80）未満
- **THEN** `level: "low"`, `confidence: 0.75` を返す

#### Scenario: 長いスキル
- **WHEN** コンテンツ行数が `HIGH_LINE_THRESHOLD`（300）以上
- **THEN** `level: "high"`, `confidence: 0.75` を返す

#### Scenario: パイプライン系キーワードを含むスキル
- **WHEN** コンテンツに `HIGH_KEYWORDS` パターンが `HIGH_KEYWORD_MIN_MATCHES`（2）回以上マッチ
- **THEN** `level: "high"`, `confidence: 0.75` を返す

#### Scenario: デフォルト
- **WHEN** 上記いずれにも該当しない
- **THEN** `level: "medium"`, `confidence: 0.75` を返す

### Requirement: issue_schema 統合

`make_missing_effort_issue()` は検出結果を `MISSING_EFFORT_CANDIDATE` 型の issue dict に変換する。

#### Scenario: factory 関数の出力形式
- **WHEN** skill_name, skill_path, proposed_effort, confidence を引数に呼び出す
- **THEN** `type: MISSING_EFFORT_CANDIDATE`, detail に全引数フィールドを含む issue dict を返す

### Requirement: remediation ハンドラ

`fix_missing_effort()` は `update_frontmatter()` を使用して effort フィールドを SKILL.md に追加する。`_verify_missing_effort()` は追加後の frontmatter を検証する。

#### Scenario: 正常な修正
- **WHEN** 存在する SKILL.md に対して fix_missing_effort を実行
- **THEN** frontmatter に proposed_effort が追加され、`fixed: True` を返す

#### Scenario: ファイルが存在しない
- **WHEN** 存在しないパスに対して fix_missing_effort を実行
- **THEN** `fixed: False` とエラーメッセージを返す

### Requirement: audit 統合

`collect_issues()` 内で `detect_missing_effort_frontmatter()` を呼び出し、検出結果を `missing_effort` 型の issue として issues リストに追加する。

#### Scenario: audit で effort 未設定が検出される
- **WHEN** プロジェクトに effort 未設定スキルがある状態で `collect_issues()` を実行
- **THEN** `type: "missing_effort"` の issue が結果に含まれる
