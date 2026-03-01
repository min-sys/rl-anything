## ADDED Requirements

### Requirement: 回帰テストゲート
`evaluate` メソッドの先頭でハードゲートチェックを実施し、最低品質を保証しなければならない（MUST）。不合格の場合は LLM 評価をスキップして即 0.0 を返さなければならない（MUST）。

#### Scenario: 空コンテンツ
- **WHEN** 候補スキルの内容が空文字列またはホワイトスペースのみ
- **THEN** スコア 0.0 を返さなければならず（MUST）、LLM 評価を実行してはならない（MUST NOT）

#### Scenario: 行数制限超過
- **WHEN** 候補スキルの行数が `_max_lines` を超過する
- **THEN** スコア 0.0 を返さなければならず（MUST）、LLM 評価を実行してはならない（MUST NOT）

#### Scenario: 禁止パターンの検出
- **WHEN** 候補スキルに `TODO`, `FIXME`, `HACK`, `XXX` のいずれかが含まれる
- **THEN** スコア 0.0 を返さなければならず（MUST）、LLM 評価を実行してはならない（MUST NOT）

#### Scenario: すべてのゲートを通過
- **WHEN** 空でなく、行数制限内で、禁止パターンがない
- **THEN** 通常の評価フロー（カスタム fitness → CoT 評価）に進まなければならない（MUST）

### Requirement: ゲート不合格時のログ出力
ゲート不合格の理由を stderr またはコンソールに出力しなければならない（MUST）。

#### Scenario: 不合格理由の表示
- **WHEN** 回帰テストゲートで不合格になる
- **THEN** `"  ゲート不合格: {理由}"` を print 出力しなければならない（MUST）（例: `"  ゲート不合格: 禁止パターン TODO を検出"`）
