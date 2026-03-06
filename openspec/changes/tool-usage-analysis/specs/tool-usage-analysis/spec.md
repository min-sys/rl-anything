## ADDED Requirements

### Requirement: ツール呼び出し抽出
セッション JSONL からツール呼び出し（`message.content[].type == "tool_use"`）を抽出し、ツール名別に集計する機能を提供する（MUST）。
対象プロジェクトのセッションファイルのみをスキャンする（MUST）。

#### Scenario: 正常なセッションファイルからの抽出
- **WHEN** プロジェクトのセッション JSONL にツール呼び出しが含まれている
- **THEN** ツール名（`name` フィールド）ごとの呼び出し回数を返す

#### Scenario: Bash コマンドの詳細抽出
- **WHEN** ツール名が `Bash` の tool_use エントリがある
- **THEN** `input.command` フィールドからコマンド文字列を抽出する

#### Scenario: パースエラー時の graceful スキップ
- **WHEN** セッション JSONL に不正な JSON 行が含まれている
- **THEN** その行をスキップし、他の行の処理を継続する（MUST）

### Requirement: Bash コマンド分類
抽出された Bash コマンドを3カテゴリに分類する（MUST）。

| カテゴリ | 判定基準 |
|----------|----------|
| `builtin_replaceable` | cat, grep, rg, find, head, tail, wc, sed, awk をコマンド先頭語で検出 |
| `repeating_pattern` | 先頭語+サブコマンドでグルーピングし、閾値以上の出現回数 |
| `cli_legitimate` | 上記に該当しない全てのコマンド（デフォルト） |

#### Scenario: Built-in 代替可能コマンドの検出
- **WHEN** Bash コマンドの先頭語が `cat`（リダイレクト/heredoc なし）、`grep`、`rg`、`find`、`head`、`tail`、`wc`、`sed`、`awk` のいずれか
- **THEN** `builtin_replaceable` カテゴリに分類し、代替ツール名を付記する（例: `cat → Read`、`sed → Edit`）

#### Scenario: 繰り返しパターンの検出
- **WHEN** 同一の「先頭語 + サブコマンド」パターンが閾値（デフォルト5）以上出現
- **THEN** `repeating_pattern` カテゴリに分類し、出現回数とサブカテゴリ情報を含める

#### Scenario: CLI 正当利用のデフォルト分類
- **WHEN** コマンドが `builtin_replaceable` にも `repeating_pattern` にも該当しない
- **THEN** `cli_legitimate` カテゴリに分類する

### Requirement: discover 統合
`run_discover()` の結果に `tool_usage_patterns` キーとしてツール利用分析結果を含める（MUST）。
`--tool-usage` フラグで有効化する（MUST）。デフォルトは無効。

#### Scenario: フラグ有効時の結果統合
- **WHEN** `run_discover(tool_usage=True)` が呼ばれる
- **THEN** 結果辞書に `tool_usage_patterns` キーが含まれ、`builtin_replaceable`（ルール候補）と `repeating_patterns`（スキル候補）が格納される

#### Scenario: フラグ無効時のスキップ
- **WHEN** `run_discover()` がデフォルト引数で呼ばれる
- **THEN** `tool_usage_patterns` キーは結果に含まれない

#### Scenario: セッションファイルが存在しない場合
- **WHEN** 対象プロジェクトのセッションディレクトリが存在しない
- **THEN** 空の結果を返し、エラーを発生させない（MUST）

### Requirement: evolve 統合
evolve の discover フェーズ表示にツール利用分析セクションを含める（MUST）。

#### Scenario: evolve 経由での自動有効化
- **WHEN** evolve が discover を呼び出す
- **THEN** `tool_usage=True` で呼び出す（MUST）。discover 単体のデフォルト（無効）とは独立

#### Scenario: ツール利用分析結果の表示
- **WHEN** evolve が discover を実行し、`tool_usage_patterns` が結果に含まれている
- **THEN** 以下を表示する: builtin_replaceable の件数とルール候補提案、repeating_patterns の上位パターンとスキル候補提案、全ツール呼び出し数と Bash の割合

#### Scenario: ツール利用分析結果がない場合
- **WHEN** discover の結果に `tool_usage_patterns` が含まれていない
- **THEN** ツール利用分析セクションをスキップする
