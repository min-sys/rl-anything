## ADDED Requirements

### Requirement: PreToolUse hook テンプレート生成
`generate_hook_template()` は builtin_replaceable パターンから PreToolUse hook のシェルスクリプトを生成する（MUST）。スクリプトは `~/.claude/hooks/` ディレクトリに出力する（MUST）。

#### Scenario: Bash 呼び出し検出 hook の生成
- **WHEN** builtin_replaceable に `grep → Grep` と `cat → Read` が含まれている
- **THEN** Bash ツールの呼び出し時にコマンド先頭語を検査し、`grep` または `cat` を検出した場合に警告メッセージを返すシェルスクリプトが生成される

#### Scenario: hook スクリプトの入力フォーマット
- **WHEN** PreToolUse hook が Bash ツール呼び出しを受け取る
- **THEN** stdin から JSON（`tool_name`, `tool_input` を含む）を読み取り、`tool_input.command` の先頭語を検査する（MUST）

#### Scenario: hook スクリプトの出力フォーマット
- **WHEN** 代替可能コマンドが検出された
- **THEN** reason メッセージ（`<command> の代わりに <alternative> ツールを使用してください`）を stderr に出力し `exit 2` で終了する（MUST）

#### Scenario: 正当なコマンドの通過
- **WHEN** Bash コマンドの先頭語が代替可能コマンドに該当しない
- **THEN** hook は何も出力せず exit 0 で終了する（MUST）

### Requirement: settings.json 登録案の提示
hook スクリプト生成後、`~/.claude/settings.json` への hook 登録の差分案をテキストで表示する（MUST）。settings.json の自動書き換えは行わない（MUST）。

#### Scenario: 登録案の差分表示
- **WHEN** hook スクリプトが `~/.claude/hooks/check-bash-builtin.py` に生成された
- **THEN** `settings.json` に追加すべき `hooks.PreToolUse` エントリの JSON 差分が表示される

#### Scenario: 既存 hook との共存
- **WHEN** `settings.json` に既存の PreToolUse hook が存在する
- **THEN** 既存エントリを保持した上で新しいエントリを追加する差分を表示する（MUST）
