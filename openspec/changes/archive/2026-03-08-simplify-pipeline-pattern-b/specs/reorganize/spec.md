## REMOVED Requirements

### Requirement: Reorganize proposes merge for clusters with 2+ skills
**Reason**: マージ候補検出は prune の semantic similarity ベースの検出に一元化する。reorganize と prune の二重検出を解消する。
**Migration**: マージ候補は prune の `duplicate_candidates` / `merge_proposals` から取得する。

### Requirement: Reorganize output structure
**Reason**: マージ候補検出の削除に伴い、出力構造から `merge_groups` を除去する。
**Migration**: 出力 JSON から `merge_groups` と `total_merge_groups` フィールドが削除される。`split_candidates` と `clusters`（split 検出に使用）は維持される。

## MODIFIED Requirements

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
