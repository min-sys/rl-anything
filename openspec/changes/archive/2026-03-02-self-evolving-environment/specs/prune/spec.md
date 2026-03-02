## ADDED Requirements

### Requirement: /rl-anything:prune スキルで未使用アーティファクトを淘汰しなければならない（MUST）
dead glob・zero invocation・重複の3基準でアーティファクトを検出し、アーカイブを提案しなければならない（MUST）。

#### Scenario: dead glob 検出
- **WHEN** rules の paths 対象がマッチするファイルが存在しない
- **THEN** 該当ルールが淘汰候補としてリストされる

#### Scenario: zero invocation 検出
- **WHEN** project スキル/ルールが usage.jsonl で30日間使用記録がない
- **THEN** 該当アーティファクトが淘汰候補としてリストされる

#### Scenario: global スキルの安全な判断
- **WHEN** global スキルが現プロジェクトで未使用である
- **THEN** Usage Registry を参照し、他プロジェクトでの使用状況を確認してから判断しなければならない（MUST）

#### Scenario: 重複検出
- **WHEN** 2つ以上のスキル/ルールが意味的に類似している
- **THEN** audit-report の重複検出結果（意味的類似度判定、閾値 80%）を利用し（SHALL）、統合候補としてリストされる

### Requirement: アーカイブ方式で淘汰しなければならない（MUST）（削除してはならない（MUST NOT））
淘汰対象は .claude/rl-anything/archive/ に移動しなければならない（MUST）。直接削除を行ってはならない（MUST NOT）。

#### Scenario: アーカイブ
- **WHEN** ユーザーが淘汰候補を承認する
- **THEN** 対象ファイルが .claude/rl-anything/archive/ に移動される

#### Scenario: 復元
- **WHEN** ユーザーがアーカイブされたアーティファクトの復元を要求する
- **THEN** archive/ から元の場所にファイルが復元される

### Requirement: 全淘汰は人間承認が必須である（MUST）
自動的にアーカイブを実行してはならない（MUST NOT）。候補リストを提示し、ユーザーが承認したもののみ実行しなければならない（MUST）。

#### Scenario: 承認フロー
- **WHEN** 淘汰候補がリストされる
- **THEN** ユーザーが個別に承認/却下するまで実行されない
