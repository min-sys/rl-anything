## MODIFIED Requirements

### Requirement: Interactive review via SKILL.md

SKILL.md の指示により Claude が corrections を対話的にレビューする（MUST）。AskUserQuestion で approve/edit/skip を選択させる。promotion_candidates 表示の後に memory_update_candidates がある場合は「MEMORY 更新候補」セクションとして表示する（MUST）。

#### Scenario: User approves a correction
- **WHEN** ユーザーが correction を "Apply" する
- **THEN** 提案先ファイルに Edit ツールで書込み、corrections.jsonl の reflect_status を "applied" に更新する

#### Scenario: User skips a correction
- **WHEN** ユーザーが correction を "Skip" する
- **THEN** corrections.jsonl の reflect_status を "skipped" に更新し、ファイル変更なし

#### Scenario: User skips remaining corrections
- **WHEN** 対話レビュー中にユーザーが "Skip remaining" を選択する
- **THEN** 未レビューの全 corrections の reflect_status を "skipped" に更新し、レビューを終了する

#### Scenario: MEMORY 更新候補の表示
- **WHEN** reflect 出力に memory_update_candidates が存在する
- **THEN** promotion_candidates の後に「MEMORY 更新候補」セクションとして correction_message、memory_file、memory_line を一覧表示する
