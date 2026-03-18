## ADDED Requirements

### Requirement: description の要約ペナルティを検出する
skill_quality fitness は、スキルの description が本文の要約になっている場合にペナルティを MUST 付与する。

#### Scenario: description が本文冒頭と高類似度の場合
- **WHEN** description と SKILL.md 本文の最初の段落の Jaccard 類似度が CSO_SUMMARY_THRESHOLD (0.5) を超える
- **THEN** CSO スコアにペナルティ（-0.2）を適用する

#### Scenario: description が十分にユニークな場合
- **WHEN** description と本文の Jaccard 類似度が CSO_SUMMARY_THRESHOLD 以下
- **THEN** ペナルティは適用しない

### Requirement: トリガーワードの存在をチェックする
description に具体的なトリガーワード（動詞、コマンド名、条件語）が含まれている場合にボーナスを MUST 付与する。

#### Scenario: description にトリガーワードが含まれる場合
- **WHEN** description に skill_triggers.py で抽出されるトリガーワードが 1 つ以上含まれる
- **THEN** CSO スコアにボーナス（+0.1 per keyword, max +0.3）を適用する

#### Scenario: description がトリガーワードを含まない場合
- **WHEN** description にトリガーワードが含まれない
- **THEN** ボーナスは適用しない（ペナルティではない）

### Requirement: 行動促進形式をチェックする
description が「Use when...」「Trigger:」等の行動指示形式を含む場合にボーナスを MUST 付与する。

#### Scenario: 行動指示形式が含まれる場合
- **WHEN** description に CSO_ACTION_PATTERNS（"Use when", "Trigger:", "Use this skill when" 等）にマッチする表現がある
- **THEN** CSO スコアにボーナス（+0.1）を適用する

### Requirement: description の長さ制限を検出する
description が Anthropic 推奨の 1024 文字を超える場合にペナルティを MUST 付与する。

#### Scenario: description が 1024 文字を超える場合
- **WHEN** description の文字数が CSO_MAX_DESCRIPTION_LENGTH (1024) を超える
- **THEN** CSO スコアにペナルティ（-0.1）を適用する

#### Scenario: description が 1024 文字以下の場合
- **WHEN** description の文字数が CSO_MAX_DESCRIPTION_LENGTH 以下
- **THEN** ペナルティは適用しない

### Requirement: CSO スコアは skill_quality の一軸として統合する
CSO チェック結果は skill_quality fitness の既存スコアリングに 8 軸目として MUST 統合される。

#### Scenario: skill_quality で CSO 軸がスコアリングされる
- **WHEN** skill_quality fitness がスキルを評価する
- **THEN** 既存 7 軸（headings, frontmatter, examples, ng_ok, line_length, arguments, workflow）に加えて CSO 軸のスコアを算出し、重み付き平均に含める
