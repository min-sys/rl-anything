## MODIFIED Requirements

### Requirement: Telemetry-based suitability scoring
skill_evolve_assessment() は usage.jsonl と errors.jsonl からスキルの自己進化適性を5項目（各1-3点、15点満点）で算出する（SHALL）。

スコアリング項目:
1. **実行頻度**: usage.jsonl から直近30日の呼び出し回数を集計。1=月3回以下 / 2=週数回(4-15回) / 3=日常的(16回以上)
2. **失敗多様性**: errors.jsonl からユニークな根本原因カテゴリ数を集計。1=0-1種類 / 2=2-3種類 / 3=4種類以上
3. **外部依存度**: スキル内容の静的解析（API/クラウド/MCP キーワード検出）。1=ローカル完結 / 2=一部外部連携 / 3=外部依存多数
4. **判断複雑さ**: LLM によるスキル構造評価。1=決定論的 / 2=数箇所の分岐 / 3=判断・ヒューリスティクス多数
5. **出力評価可能性**: テレメトリの成功/失敗パターンから推定（`query_usage()` の件数 - `query_errors()` の件数で成功率を算出）。1=評価困難 / 2=部分的に評価可能 / 3=明確な品質基準あり

**追加**: ワークフロースキルと判定された場合、`assess_single_skill()` の返却値に `workflow_checkpoints` フィールドを追加する（SHALL）。このフィールドには `detect_checkpoint_gaps()` の結果（チェックポイントギャップのリスト）が含まれる。非ワークフロースキルの場合は `workflow_checkpoints: None` を返す。

#### Scenario: High suitability skill
- **WHEN** aws-deploy 相当のスキル（頻度3, 多様性3, 外部3, 判断2, 評価2 = 13点）を分析する
- **THEN** 「適性: 高（13/15）」と判定し、変換を推奨する

#### Scenario: Low suitability skill
- **WHEN** 単純なファイル変換スキル（頻度1, 多様性1, 外部1, 判断1, 評価1 = 5点）を分析する
- **THEN** 「適性: 低（5/15）- 変換非推奨」と判定し、理由を提示する

#### Scenario: Medium suitability with user decision
- **WHEN** スコアが9点のスキルを分析する
- **THEN** 「適性: 中（9/15）」と判定し、成長が期待できるポイントと懸念点を提示してユーザーに判断を委ねる

#### Scenario: Workflow skill with checkpoint gaps
- **WHEN** openspec-verify 相当のワークフロースキル（Step構造あり）を分析する
- **AND** テレメトリに infra_deploy 関連の修正が3件ある
- **THEN** 返却値に `workflow_checkpoints: [{"category": "infra_deploy", "confidence": 0.75, ...}]` が含まれる

#### Scenario: Non-workflow skill
- **WHEN** 単純なユーティリティスキル（Step構造なし）を分析する
- **THEN** 返却値に `workflow_checkpoints: None` が含まれる
