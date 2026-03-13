## ADDED Requirements

### Requirement: optimize gate 不合格時の分離提案表示

optimize の regression gate が `line_limit_exceeded` で不合格になった場合、`suggest_separation()` を呼び出し、分離提案メッセージをユーザーに表示する。

#### Scenario: rule パッチが行数超過でリジェクト

- **WHEN** optimize が rule ファイルへのパッチを生成し、regression gate が `line_limit_exceeded` で不合格
- **THEN** 通常のリジェクトメッセージに加えて「references/ への分離を提案します」メッセージを表示する

#### Scenario: rule 以外のファイルが行数超過

- **WHEN** optimize が skill ファイルへのパッチを生成し、regression gate が `line_limit_exceeded` で不合格
- **THEN** 分離提案は表示せず、通常のリジェクトメッセージのみ表示する

### Requirement: result に suggestion フィールド追加

optimize の result dict に `suggestion: Optional[str]` フィールドを追加し、分離提案がある場合にテキストを格納する。

#### Scenario: 分離提案ありの result

- **WHEN** gate 不合格で分離提案が生成された
- **THEN** `result["suggestion"]` に提案テキストが格納され、`result["status"]` は `"rejected"` のまま
