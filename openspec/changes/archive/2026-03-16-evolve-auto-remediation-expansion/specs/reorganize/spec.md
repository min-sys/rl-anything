## MODIFIED Requirements

### Requirement: Reorganize output structure
Reorganize Phase の出力は以下の JSON 構造に従う（MUST）。`split_candidates` を issue_schema 形式の issue リストとしても出力する（MUST）。

```json
{
  "skipped": false,
  "clusters": [...],
  "split_candidates": [...],
  "issues": [
    {
      "type": "split_candidate",
      "file": ".claude/skills/<skill>/SKILL.md",
      "detail": {
        "skill_name": "...",
        "line_count": 450,
        "threshold": 300
      }
    }
  ],
  "total_clusters": 0,
  "total_split_candidates": 0
}
```

#### Scenario: Output includes issues field
- **WHEN** reorganize が 2 件の split_candidates を検出した
- **THEN** `issues` フィールドに 2 件の `split_candidate` issue が issue_schema 形式で含まれる

#### Scenario: No split candidates
- **WHEN** 全スキルが 300 行以下
- **THEN** `issues` フィールドは空リスト、`split_candidates` も空リスト
