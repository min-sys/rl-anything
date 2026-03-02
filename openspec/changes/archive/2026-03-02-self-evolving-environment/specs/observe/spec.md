## ADDED Requirements

### Requirement: PostToolUse hook で使用スキル・ファイルパス・エラーを記録しなければならない（MUST）
hooks/observe.py は PostToolUse async hook として、Skill ツール呼び出し時にスキル名・ファイルパス・エラー有無を usage.jsonl に追記しなければならない（MUST）。
global スキルの場合、プロジェクトパスも usage-registry.jsonl に記録しなければならない（MUST）（Scope Advisory 用）。
LLM 呼び出しを行ってはならない（MUST NOT）。

#### Scenario: スキル使用の記録
- **WHEN** Claude が Skill ツールを呼び出す
- **THEN** usage.jsonl にスキル名・タイムスタンプ・ファイルパスが追記される

#### Scenario: global スキルの Usage Registry 記録
- **WHEN** global スキル（~/.claude/skills/ 配下）が使用される
- **THEN** usage-registry.jsonl にスキル名・プロジェクトパス・タイムスタンプが追記される

#### Scenario: エラーの記録
- **WHEN** ツール呼び出しがエラーを返す
- **THEN** errors.jsonl にエラー内容・スキル名・タイムスタンプが追記される

#### Scenario: JSONL 書き込み失敗時のサイレント失敗
- **WHEN** JSONL ファイルへの書き込みが失敗する（ディスクフル、パーミッションエラー等）
- **THEN** セッションをブロックしてはならない（MUST NOT）。エラーは stderr に記録し、hook は正常終了する

### Requirement: Stop hook でセッション要約を記録しなければならない（MUST）
hooks/session_summary.py は Stop async hook として、セッション終了時に使用スキル数・エラー数・ファイル数のサマリを sessions.jsonl に追記しなければならない（MUST）。
LLM 呼び出しを行ってはならない（MUST NOT）。

#### Scenario: セッション要約の記録
- **WHEN** Claude Code セッションが終了する
- **THEN** sessions.jsonl にセッション ID・使用スキル数・エラー数・タイムスタンプが追記される

### Requirement: PreCompact hook で進化状態をチェックポイントしなければならない（MUST）
hooks/save_state.py は PreCompact async hook として、コンテキスト圧縮前に進化の中間状態を保存しなければならない（MUST）。

#### Scenario: 状態のチェックポイント
- **WHEN** Claude Code がコンテキスト圧縮を実行する
- **THEN** 現在の evolve 関連の中間状態が checkpoint.json に保存される

### Requirement: SessionStart hook で状態を復元しなければならない（MUST）
hooks/restore_state.py は SessionStart compact hook として、保存済みチェックポイントから状態を復元しなければならない（MUST）。

#### Scenario: 状態の復元
- **WHEN** 新しいセッションが開始され、checkpoint.json が存在する
- **THEN** 前回の進化状態が復元される

### Requirement: 観測データは ~/.claude/rl-anything/ に保存しなければならない（MUST）
全ての観測データ（usage.jsonl, errors.jsonl, sessions.jsonl, usage-registry.jsonl）は ~/.claude/rl-anything/ ディレクトリに保存しなければならない（MUST）。
ディレクトリが存在しない場合、自動作成しなければならない（MUST）。

#### Scenario: データ保存先
- **WHEN** observe hook がデータを記録する
- **THEN** ~/.claude/rl-anything/ 配下の対応する JSONL ファイルに追記される

#### Scenario: ディレクトリ不在時の自動作成
- **WHEN** ~/.claude/rl-anything/ ディレクトリが存在しない状態で hook が実行される
- **THEN** ディレクトリを自動作成し（MUST）、データ記録を継続する
