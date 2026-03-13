## ADDED Requirements

### Requirement: reflect 反映先 rule の行数チェック

reflect が corrections を rule ファイルに反映する際、反映後の行数を `check_line_limit()` で確認し、超過時は `suggest_separation()` の提案をユーザーに表示する。

#### Scenario: 反映後に行数超過

- **WHEN** reflect が correction を rule ファイルに反映した結果、行数が制限を超過した
- **THEN** 分離提案メッセージを表示し、ユーザーに分離実行の判断を委ねる

#### Scenario: 反映後も行数制限内

- **WHEN** reflect が correction を rule ファイルに反映した結果、行数が制限内
- **THEN** 通常通り反映を完了し、分離提案は表示しない

### Requirement: remediation の分離実行モード

evolve/remediation の `fix_line_limit_violation` で、対象が rule ファイルの場合に LLM 圧縮ではなく分離実行（要約+参照リンクへの書き換え + 分離先ファイル生成）を行う。

#### Scenario: rule の line_limit_violation を auto_fix

- **WHEN** evolve が rule ファイルの `line_limit_violation`（auto_fixable）を修正する
- **THEN** LLM に「要約+参照リンク」への書き換えを指示し、分離先の references ファイルも生成する

#### Scenario: 分離後の rule が行数制限内

- **WHEN** 分離実行が完了した
- **THEN** 書き換え後の rule ファイルが行数制限内であることを検証する
