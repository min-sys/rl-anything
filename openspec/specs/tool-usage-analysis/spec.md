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
結果の `installed_artifacts` に mitigation_metrics を含める（MUST）。

#### Scenario: フラグ有効時の結果統合
- **WHEN** `run_discover(tool_usage=True)` が呼ばれる
- **THEN** 結果辞書に `tool_usage_patterns` キーが含まれ、`builtin_replaceable`、`repeating_patterns` が格納される
- **AND** `installed_artifacts` の各エントリに `recommendation_id` を持つものは `mitigation_metrics` を含む

#### Scenario: フラグ無効時のスキップ
- **WHEN** `run_discover()` がデフォルト引数で呼ばれる
- **THEN** `tool_usage_patterns` キーは結果に含まれない

#### Scenario: セッションファイルが存在しない場合
- **WHEN** 対象プロジェクトのセッションディレクトリが存在しない
- **THEN** 空の結果を返し、エラーを発生させない（MUST）

### Requirement: evolve 統合
evolve の discover フェーズ表示にツール利用分析セクションを含める（MUST）。
対策状態に応じて表示を切り替える（MUST）。

#### Scenario: evolve 経由での自動有効化
- **WHEN** evolve が discover を呼び出す
- **THEN** `tool_usage=True` で呼び出す（MUST）。discover 単体のデフォルト（無効）とは独立

#### Scenario: 対策済み推奨の表示
- **WHEN** installed_artifacts に mitigation_metrics を持つエントリがあり mitigated が True
- **THEN** 「対策済み (artifacts) — 直近 N 件検出」形式で表示する

#### Scenario: 未対策推奨の表示
- **WHEN** recommended_artifacts に recommendation_id 付きエントリがある（= 未導入）
- **THEN** 従来通り件数と改善提案を表示する

#### Scenario: ツール利用分析結果がない場合
- **WHEN** discover の結果に `tool_usage_patterns` が含まれていない
- **THEN** ツール利用分析セクションをスキップする

### Requirement: 閾値定数化
Step 10.2 の閾値をハードコードから `tool_usage_analyzer.py` のモジュール定数に移行する（MUST）。

#### Scenario: 定数定義
- **WHEN** `tool_usage_analyzer` モジュールがロードされた時点で
- **THEN** `BUILTIN_THRESHOLD=10`、`SLEEP_THRESHOLD=20`、`BASH_RATIO_THRESHOLD=0.40` が定義されている

#### Scenario: SKILL.md での参照
- **WHEN** Step 10.2 が閾値を使用する
- **THEN** `tool_usage_analyzer.py` の定数名を参照して記述する（ハードコード値ではなく）

## MODIFIED Requirements (evolve-report-improvements)

### Requirement: Display BASH_RATIO_THRESHOLD in report
evolve レポートの Bash 割合表示に目標閾値を併記し、達成/未達を SHALL 明示する。

#### Scenario: Bash ratio above threshold
- **WHEN** Bash 割合が BASH_RATIO_THRESHOLD (40%) 以上の場合
- **THEN** 「Bash 割合: X% (目標: ≤40%) — 未達」形式で表示する

#### Scenario: Bash ratio below threshold
- **WHEN** Bash 割合が BASH_RATIO_THRESHOLD (40%) 未満の場合
- **THEN** 「Bash 割合: X% (目標: ≤40%) — 達成」形式で表示する

### Requirement: Threshold constants accessible for report
tool_usage_analyzer.py の閾値定数をレポート生成時に参照可能に SHALL する。

### Normative Statements

- The system SHALL display the target threshold alongside the actual Bash ratio.
- The system SHALL indicate achievement status using 「達成」/「未達」 labels.
- The system SHALL use the existing `BASH_RATIO_THRESHOLD` constant; it MUST NOT hardcode the threshold value in report templates.
- BUILTIN_THRESHOLD and SLEEP_THRESHOLD SHALL also be displayed when relevant metrics are shown.
