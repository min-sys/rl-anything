## ADDED Requirements

### Requirement: README にプラグイン検証コマンドを記載する
README.md のテストセクションに `claude plugin validate` コマンドを追加する（SHALL）。

#### Scenario: 開発者がバリデーションを実行できる
- **WHEN** 開発者が README のテスト手順に従う
- **THEN** `claude plugin validate` で frontmatter / hooks.json のエラーが検出される

### Requirement: CLAUDE.md のテストセクションにも追記する
CLAUDE.md のテストセクションに `claude plugin validate` を追記する（SHALL）。

#### Scenario: Claude が validate コマンドを認識する
- **WHEN** Claude がテスト実行時に CLAUDE.md を参照する
- **THEN** `claude plugin validate` も実行対象として認識できる
