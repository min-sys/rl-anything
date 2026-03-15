## MODIFIED Requirements

### Requirement: 8-tier memory hierarchy routing
corrections は8層メモリ階層の適切な書込先にルーティングされる（MUST）。CLAUDE.local.md（個人用）と auto-memory（低信頼度ステージング）を含む。ルーティング判定時にプロジェクト固有シグナル検出を実施し、`always/never/prefer` キーワードによる global ルーティングよりも優先する（MUST）。**`last_skill` コンテキストが存在する場合、always/never 層の後・frontmatter paths 層の前（位置6）に挿入された last-skill 層でスキルの references/ にルーティングする（MUST）。保護スキルの場合はローカル代替先にリダイレクトする。**

#### Scenario: Guardrail routed to rules
- **WHEN** guardrail タイプの correction をルーティングする
- **THEN** `.claude/rules/guardrails.md` が提案される

#### Scenario: Last skill context routes at position 6
- **WHEN** correction の `last_skill` が "atlas-browser" であり、always/never キーワードも含まない
- **THEN** 位置6の last-skill 層で評価され、`.claude/skills/atlas-browser/references/pitfalls.md` が提案される

#### Scenario: Last skill is protected — redirect to local
- **WHEN** correction の `last_skill` が "openspec-verify-change"（plugin 由来）
- **THEN** プロジェクト側の references/ が代替先として提案される

#### Scenario: Project-specific skill in correction with always keyword
- **WHEN** correction テキストが「/channel-routing は always 使うべき」を含む
- **AND** `channel-routing` が現在のプロジェクトの CLAUDE.md に記載されたスキル
- **THEN** プロジェクト固有シグナルにより `.claude/rules/` が提案される（global ではなく）

#### Scenario: Generic always keyword without project signal
- **WHEN** correction テキストが「タスクが変わったら always スキルを確認する」を含む
- **AND** プロジェクト固有シグナルが検出されない
- **THEN** 従来通り `~/.claude/CLAUDE.md`（global）が提案される

#### Scenario: Model preference routed to global
- **WHEN** "claude-4" 等のモデル名を含む correction をルーティングする
- **THEN** `~/.claude/CLAUDE.md` または model-preferences rule が提案される

#### Scenario: Path-scoped rule match
- **WHEN** correction に "src/api" パスの言及があり、`paths: src/api/` を持つ rule がある
- **THEN** その rule ファイルが提案される

#### Scenario: Low confidence routed to auto-memory
- **WHEN** confidence 0.65 の correction をルーティングする
- **THEN** auto-memory のトピック別ファイル（例: `workflow.md`）に仮置きが提案される

#### Scenario: Machine-specific routed to CLAUDE.local.md
- **WHEN** correction にローカルパスや個人設定が含まれ、ユーザーが CLAUDE.local.md を選択する
- **THEN** `./CLAUDE.local.md` に書き込まれる
