## ADDED Requirements

### Requirement: Split candidates converted to issue_schema
reorganize の `split_candidates` を `make_split_candidate_issue()` factory 関数で issue_schema 形式に変換する（MUST）。issue type は `split_candidate`、confidence は 0.70、impact_scope は "project" とする（SHALL）。

#### Scenario: Split candidate issue created
- **WHEN** reorganize が `split_candidates: [{skill_name: "bot-create", line_count: 316, threshold: 300}]` を出力した
- **THEN** `make_split_candidate_issue()` が `{type: "split_candidate", file: ".claude/skills/bot-create/SKILL.md", confidence: 0.70, detail: {skill_name: "bot-create", line_count: 316, threshold: 300}}` を返す

#### Scenario: No split candidates
- **WHEN** reorganize の `split_candidates` が空
- **THEN** `split_candidate` issue は生成されない

### Requirement: Split proposal generation via LLM
`split_candidate` issue が proposable に分類された場合、fix 関数 `fix_split_candidate()` は対象スキルの SKILL.md を読み、LLM でセクション分析を行い、分割案テキストを生成する（SHALL）。ファイルの実際の変更は行わない（MUST NOT）。提案テキストには分割先ファイル名と各ファイルの概要を含む（SHALL）。

#### Scenario: Split proposal generated
- **WHEN** ユーザーが `split_candidate` の proposable を承認した
- **THEN** LLM が SKILL.md を分析し「references/ に X セクション（Y行）を切り出し、SKILL.md を Z行に削減」という提案テキストを表示する。ファイル変更は行わない

#### Scenario: User rejects split proposal
- **WHEN** ユーザーが分割提案をスキップした
- **THEN** `remediation-outcomes.jsonl` に skipped として記録する
