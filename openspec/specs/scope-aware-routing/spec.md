## ADDED Requirements

### Requirement: Project-specific signal detection
`suggest_claude_file()` は correction テキストにプロジェクト固有のシグナルが含まれるかを判定する（MUST）。以下をプロジェクト固有シグナルとする:
- CLAUDE.md の Skills セクションに記載されたスキル名
- correction テキスト内のパスがプロジェクトルートに実際に存在するディレクトリパス
- CLAUDE.md から抽出した技術スタック名

#### Scenario: Correction mentions project-specific skill
- **WHEN** correction テキストが「/channel-routing スキルを使うべきだった」を含む
- **AND** `channel-routing` が現在のプロジェクトの CLAUDE.md に記載されている
- **THEN** プロジェクト固有と判定し、`.claude/rules/` へのルーティングを提案する

#### Scenario: Correction mentions project path
- **WHEN** correction テキストが「src/api/ のファイルを変更する際は...」を含む
- **AND** プロジェクトルートに `src/api/` ディレクトリが存在する
- **THEN** プロジェクト固有と判定する

#### Scenario: Correction is generic behavior
- **WHEN** correction テキストが「タスクが変わったらスキルを確認する」である
- **AND** プロジェクト固有のスキル名・パス・技術スタックへの言及がない
- **THEN** プロジェクト固有と判定されず、既存のキーワードベースルーティング（global）にフォールスルーする

### Requirement: Scope detection priority order
`suggest_claude_file()` のルーティング優先順位は: guardrail → プロジェクト固有シグナル → モデル名 → always/never/prefer → path-scoped rule → subdirectory → auto-memory の順とする（MUST）。

#### Scenario: Project-specific signal overrides always keyword
- **WHEN** correction テキストが「/channel-routing は always 使うべき」を含む
- **AND** `channel-routing` がプロジェクト固有スキル
- **THEN** プロジェクト固有シグナル（優先度高）により `.claude/rules/` が提案される（`always` キーワードによる global ルーティングより優先）

#### Scenario: Guardrail still highest priority
- **WHEN** guardrail タイプの correction にプロジェクト固有スキル名が含まれる
- **THEN** guardrail ルーティング（`.claude/rules/guardrails.md`）が最優先で適用される
