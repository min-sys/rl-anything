## ADDED Requirements

### Requirement: Duplicate issue confidence upgrade to proposable
`duplicate` issue の `compute_confidence_score()` を修正する（MUST）。現在の flat 0.4 を similarity ベースに変更し、similarity ≥ DUPLICATE_PROPOSABLE_SIMILARITY（0.75、remediation.py 定数）の場合は DUPLICATE_PROPOSABLE_CONFIDENCE（0.60、remediation.py 定数）を返す。これにより manual_required（< 0.5）から proposable に昇格する（SHALL）。

#### Scenario: Duplicate classified as proposable
- **WHEN** audit が `aws-deploy` と `domain-naming` の重複（similarity 0.81）を検出した
- **THEN** confidence 0.60, category "proposable" に分類される

#### Scenario: Low similarity duplicate remains manual_required
- **WHEN** audit が 2 つのスキルの重複（similarity 0.55）を検出した
- **THEN** confidence はそのまま（similarity に応じた計算）で、0.5 未満なら manual_required のまま

### Requirement: Duplicate merge proposal generation
`duplicate` issue が proposable に分類された場合、`generate_proposals()` が LLM で統合案テキストを生成する（SHALL）。提案テキストには統合先ファイル名、統合方法、影響範囲を含む（SHALL）。ファイルの実際の変更は行わない（MUST NOT）。

#### Scenario: Merge proposal generated
- **WHEN** `aws-deploy` と `domain-naming` の重複が proposable として提示された
- **THEN** 「`aws-deploy.md` ルールの内容を `aws-deploy/SKILL.md` の references/ に統合し、ルールファイルを削除」等の具体的な統合案テキストが表示される

#### Scenario: Three-way duplicate proposal
- **WHEN** 3 つのアーティファクトが相互に重複している
- **THEN** 統合案テキストに 3 つの関係性と推奨統合先を含む
