## ADDED Requirements

### Requirement: corrections データの LLM 入力サニタイズ
`semantic_detector.py` が corrections データを LLM に渡す前に、message フィールドをサニタイズする（MUST）。

#### Scenario: 長文メッセージの切り詰め
- **WHEN** corrections レコードの message が500文字を超える
- **THEN** LLM に渡す前に先頭500文字に切り詰め、末尾に `...` を付与する（結果は最大503文字）

#### Scenario: 制御文字の除去
- **WHEN** corrections レコードの message に制御文字（\x00-\x1f、\x7f、ただし \n \t を除く）が含まれる
- **THEN** LLM に渡す前に制御文字が除去される

#### Scenario: XML/HTML タグの除去
- **WHEN** corrections レコードの message に `<system>`, `</system>`, `<system-reminder>`, `</system-reminder>`, `<instructions>`, `</instructions>`, `<context>`, `</context>`, `<rules>`, `</rules>`, `<Claude>`, `</Claude>` のいずれかの XML タグが含まれる
- **THEN** LLM に渡す前に該当タグが除去される

### Requirement: corrections.jsonl のファイルパーミッション
`ensure_data_dir()` はディレクトリを `700` で作成する（MUST）。`append_jsonl()` は新規ファイル作成時にパーミッションを `600` に設定する（MUST）。

#### Scenario: 新規ディレクトリ作成時のパーミッション
- **WHEN** `ensure_data_dir()` が `~/.claude/rl-anything/` を初回作成する
- **THEN** ディレクトリのパーミッションが `700` (rwx------) である

#### Scenario: 新規 JSONL ファイル作成時のパーミッション
- **WHEN** `append_jsonl()` が新規ファイルを作成する
- **THEN** ファイルのパーミッションが `600` (rw-------) である

#### Scenario: 既存ファイルへの追記時
- **WHEN** `append_jsonl()` が既存ファイルに追記する
- **THEN** ファイルのパーミッションは変更されない

#### Scenario: chmod 失敗時のサイレント続行
- **WHEN** `append_jsonl()` がファイルパーミッションの設定に失敗する（例: ファイルシステムが chmod をサポートしない）
- **THEN** パーミッション設定失敗を stderr に警告出力し、ファイル書き込み自体は続行する
