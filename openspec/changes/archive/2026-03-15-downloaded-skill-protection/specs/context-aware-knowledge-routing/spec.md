## ADDED Requirements

### Requirement: Last-skill context priority in routing
`suggest_claude_file()` は corrections の `last_skill` フィールドが non-null の場合、そのスキルの references/ ディレクトリを優先ルーティング先として提案する（MUST）。この層は always/never 層の後、frontmatter paths 層の前（位置6）に配置する。

#### Scenario: Last skill context routes to skill references
- **WHEN** correction の `last_skill` が "atlas-browser" であり、メッセージが「ブラウザ検証で要素が見つからない時は wait を入れる」
- **THEN** `.claude/skills/atlas-browser/references/pitfalls.md` が提案される（confidence `LAST_SKILL_CONFIDENCE`）

#### Scenario: Last skill is protected — redirect to local alternative
- **WHEN** correction の `last_skill` が "openspec-verify-change"（plugin 由来）であり、メッセージが「検証時にスナップショット比較を使う」
- **THEN** プロジェクト側の `.claude/skills/openspec-verify-change/references/pitfalls.md` が代替先として提案される（confidence `LAST_SKILL_CONFIDENCE`）

#### Scenario: Last skill is null — fallback to existing routing
- **WHEN** correction の `last_skill` が null
- **THEN** 既存の8層ルーティング（project signal → model → always/never → ...）にフォールバックする

#### Scenario: Last skill context overrides keyword match
- **WHEN** correction の `last_skill` が "atlas-browser" であり、メッセージに「検証」キーワードが含まれる
- **THEN** 「検証」キーワードに引きずられず、`atlas-browser` の references/ が提案される

### Requirement: Skill references directory resolution
ルーティング先としてスキルの references/ ディレクトリを解決する際、`.claude/skills/<name>/references/pitfalls.md` を標準パスとする（MUST）。

#### Scenario: References directory exists
- **WHEN** `.claude/skills/atlas-browser/references/pitfalls.md` が既に存在する
- **THEN** そのパスを返す

#### Scenario: References directory does not exist
- **WHEN** `.claude/skills/my-skill/references/` が存在しない
- **THEN** `.claude/skills/my-skill/references/pitfalls.md` を提案し、ディレクトリ作成が必要であることを示す
