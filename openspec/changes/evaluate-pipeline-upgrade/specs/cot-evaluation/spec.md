## ADDED Requirements

### Requirement: Chain-of-Thought 付き LLM 評価
`_llm_evaluate` は各評価基準（明確性・完全性・構造・実用性）について根拠を明示してからスコアを算出しなければならない（MUST）。出力はJSON形式としなければならない（MUST）。

#### Scenario: 正常な CoT 評価
- **WHEN** 候補スキルの内容を `_llm_evaluate` に渡す
- **THEN** 各基準の `score`（0.0-1.0）と `reason`（1-2文の根拠）を含むJSONを取得し、`total` を統合スコアとして返さなければならない（MUST）

#### Scenario: JSON パース失敗時のフォールバック
- **WHEN** LLM の出力が正しいJSON形式でない
- **THEN** 出力テキストから数値を正規表現で抽出しなければならない（MUST）。取得できない場合は 0.5 にフォールバックしなければならない（MUST）

### Requirement: `--model` ハードコードの除去
optimize.py および run-loop.py のすべての `claude -p` 呼び出しから `--model` フラグを除去しなければならない（MUST）。モデル選択は Claude Code のデフォルト設定に委ねなければならない（MUST）。

#### Scenario: evaluate での claude 呼び出し
- **WHEN** `_llm_evaluate` が claude CLI を呼び出す
- **THEN** コマンドは `["claude", "-p", "--output-format", "text"]` でなければならず（MUST）、`--model` フラグを含んではならない（MUST NOT）

#### Scenario: mutate での claude 呼び出し
- **WHEN** `mutate` が claude CLI を呼び出す
- **THEN** コマンドは `["claude", "-p", "--output-format", "text"]` でなければならず（MUST）、`--model` フラグを含んではならない（MUST NOT）

#### Scenario: crossover での claude 呼び出し
- **WHEN** `crossover` が claude CLI を呼び出す
- **THEN** コマンドは `["claude", "-p", "--output-format", "text"]` でなければならず（MUST）、`--model` フラグを含んではならない（MUST NOT）

#### Scenario: run-loop.py での claude 呼び出し
- **WHEN** run-loop.py が claude CLI を呼び出す
- **THEN** すべての呼び出しで `--model` フラグを含んではならない（MUST NOT）

### Requirement: --model 後方互換性
既存ユーザーが `--model` フラグを指定した場合でもエラーにせず、警告を出力して処理を続行しなければならない（MUST）。

#### Scenario: ユーザーが --model フラグを指定して実行した場合
- **WHEN** `--model sonnet` 等のフラグを指定して実行する
- **THEN** stderr に「Warning: --model フラグは廃止されました。Claude Code のデフォルトモデルを使用します。」と警告を出力し、フラグを無視して処理を続行する

#### Scenario: --model フラグなしで実行した場合
- **WHEN** `--model` フラグなしで実行する
- **THEN** 警告なしで通常処理を行う
