## ADDED Requirements

### Requirement: Reorganize clusters skills by content similarity
Reorganize Phase は全スキルの SKILL.md テキストから TF-IDF ベクトルを生成し、階層クラスタリングで意味的に近いスキル群を特定する（MUST）。plugin 由来スキルは分析対象外とする（MUST）。ただしクラスタリング結果はマージ提案には使用せず、split 候補検出の補助情報としてのみ使用する（MUST）。

#### Scenario: Related skills clustered together
- **WHEN** `aws-cdk-deploy`, `aws-cdk-development`, `aws-common` の3スキルが存在する
- **THEN** Reorganize はこれらを同一クラスタに分類するが、マージ提案は生成しない

#### Scenario: Unrelated skills in separate clusters
- **WHEN** `mailpit-test` と `draw-io` が存在する
- **THEN** Reorganize はこれらを別クラスタに分類する

### Requirement: Reorganize detects oversized skills for split
単一スキルで SKILL.md の行数が 300 行を超える場合、「分割候補」として提案する（MUST）。これが reorganize の主要な責務である。

#### Scenario: Oversized skill detected
- **WHEN** `mega-skill/SKILL.md` が 450 行ある
- **THEN** 出力の `split_candidates` に当該スキルを含め、分割を提案する

#### Scenario: All skills within size limit
- **WHEN** 全スキルの SKILL.md が 300 行以下
- **THEN** `split_candidates` は空リストとなる

### Requirement: Reorganize skips when skill count is low
分析対象のスキル数が 5 未満の場合、Reorganize Phase をスキップする（MUST）。

#### Scenario: Less than 5 skills
- **WHEN** 分析対象のスキルが 3 個
- **THEN** Reorganize は `{"skipped": true, "reason": "insufficient_skills", "count": 3}` を出力し、クラスタリングを実行しない

### Requirement: Reorganize graceful degradation without scipy
scipy がインストールされていない環境では、Reorganize Phase をスキップし警告を出力する（MUST）。エラーで evolve 全体を停止してはならない（MUST NOT）。

#### Scenario: scipy not installed
- **WHEN** `import scipy` が ImportError を返す
- **THEN** Reorganize は `{"skipped": true, "reason": "scipy_not_available"}` を出力する

### Requirement: Reorganize output structure
Reorganize Phase の出力は以下の JSON 構造に従う（MUST）。マージ候補検出は prune の semantic similarity ベースの検出に一元化されたため、`merge_groups` と `total_merge_groups` は出力に含めない。

```json
{
  "skipped": false,
  "clusters": [
    {
      "cluster_id": 0,
      "skills": ["skill-a", "skill-b", "skill-c"],
      "centroid_keywords": ["deploy", "aws", "cdk"]
    }
  ],
  "split_candidates": [
    {
      "skill_name": "mega-skill",
      "line_count": 450,
      "threshold": 300
    }
  ],
  "total_clusters": 0,
  "total_split_candidates": 0
}
```

#### Scenario: Full output with all sections populated
- **WHEN** 10 スキルが分析され、3 クラスタに分類、1 分割候補がある
- **THEN** 出力は `clusters` 3件、`split_candidates` 1件を含む

### Requirement: Reorganize uses configurable distance threshold
クラスタリングの距離閾値はデフォルト 0.7 とし、`evolve-state.json` の `reorganize_threshold` で変更可能とする（MUST）。

#### Scenario: Custom threshold configured
- **WHEN** `evolve-state.json` に `"reorganize_threshold": 0.5` が設定されている
- **THEN** Reorganize は距離閾値 0.5 でクラスタリングを実行する

## REMOVED Requirements

### Requirement: Reorganize proposes merge for clusters with 2+ skills
**Reason**: マージ候補検出は prune の semantic similarity ベースの検出に一元化する。reorganize と prune の二重検出を解消する。
**Migration**: マージ候補は prune の `duplicate_candidates` / `merge_proposals` から取得する。

### Requirement: Reorganize output structure (merge_groups)
**Reason**: マージ候補検出の削除に伴い、出力構造から `merge_groups` を除去する。
**Migration**: 出力 JSON から `merge_groups` と `total_merge_groups` フィールドが削除された。`split_candidates` と `clusters`（split 検出に使用）は維持される。
