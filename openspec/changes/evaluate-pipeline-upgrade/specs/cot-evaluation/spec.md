## ADDED Requirements

### Requirement: Chain-of-Thought 付き LLM 評価
`_llm_evaluate` は各評価基準（明確性・完全性・構造・実用性）について根拠を明示してからスコアを算出する。出力はJSON形式とする。

#### Scenario: 正常な CoT 評価
- **WHEN** 候補スキルの内容を `_llm_evaluate` に渡す
- **THEN** 各基準の `score`（0.0-1.0）と `reason`（1-2文の根拠）を含むJSONを取得し、`total` を統合スコアとして返す

#### Scenario: JSON パース失敗時のフォールバック
- **WHEN** LLM の出力が正しいJSON形式でない
- **THEN** 出力テキストから数値を正規表現で抽出し、取得できない場合は 0.5 を返す

### Requirement: `--model` ハードコードの除去
optimize.py および run-loop.py のすべての `claude -p` 呼び出しから `--model` フラグを除去する。モデル選択は Claude Code のデフォルト設定に委ねる。

#### Scenario: evaluate での claude 呼び出し
- **WHEN** `_llm_evaluate` が claude CLI を呼び出す
- **THEN** コマンドは `["claude", "-p", "--output-format", "text"]` であり、`--model` フラグを含まない

#### Scenario: mutate での claude 呼び出し
- **WHEN** `mutate` が claude CLI を呼び出す
- **THEN** コマンドは `["claude", "-p", "--output-format", "text"]` であり、`--model` フラグを含まない

#### Scenario: crossover での claude 呼び出し
- **WHEN** `crossover` が claude CLI を呼び出す
- **THEN** コマンドは `["claude", "-p", "--output-format", "text"]` であり、`--model` フラグを含まない

#### Scenario: run-loop.py での claude 呼び出し
- **WHEN** run-loop.py が claude CLI を呼び出す
- **THEN** すべての呼び出しで `--model` フラグを含まない
