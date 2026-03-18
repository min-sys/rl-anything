## MODIFIED Requirements

### Requirement: skill_quality に CSO 軸を追加する
既存の skill_quality fitness に CSO (Claude Search Optimization) 軸を MUST 追加する。

#### Scenario: skill_quality が CSO 軸を含めてスコアリングする
- **WHEN** skill_quality がスキルを評価する
- **THEN** 従来の 7 軸（headings, frontmatter, examples, ng_ok, line_length, arguments, workflow）に加えて CSO 軸（要約ペナルティ、トリガー語ボーナス、行動促進ボーナス、長さペナルティ）を 8 軸目として算出し、全体スコアに反映する

#### Scenario: description が存在しないスキルの場合
- **WHEN** SKILL.md に frontmatter description がない
- **THEN** CSO 軸は 0.0 とし、全体スコアへの影響は既存軸で補う

### Requirement: CSO 閾値は定数化する
CSO 関連の閾値は全て定数として定義し、regression gate でチェック可能にする MUST。

#### Scenario: 定数が定義されている
- **WHEN** CSO チェックモジュールがロードされる
- **THEN** CSO_SUMMARY_THRESHOLD, CSO_TRIGGER_BONUS, CSO_ACTION_BONUS, CSO_MAX_DESCRIPTION_LENGTH, CSO_LENGTH_PENALTY, CSO_WEIGHT が定数として参照可能である
