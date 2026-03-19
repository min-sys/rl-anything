## ADDED Requirements

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

### Requirement: Threshold classification
skill_evolve_assessment() はスコアに基づき3段階で分類する（SHALL）:
- **12-15点**: 適性高 → 変換を強く推奨
- **8-11点**: 適性中 → 変換可能、ユーザーに判断を委ねる
- **5-7点**: 適性低 → 変換非推奨、理由を提示

#### Scenario: Boundary score at threshold
- **WHEN** スコアが8点（閾値境界）のスキルを分析する
- **THEN** 「適性: 中」に分類される（7点なら低、8点なら中）

### Requirement: LLM scoring cache
外部依存度・判断複雑さの LLM 判定結果は `~/.claude/rl-anything/skill-evolve-cache.json` にキャッシュする（SHALL）。スキルファイルの SHA256 ハッシュと紐づけ、ファイル変更時のみ再計算する。

#### Scenario: Cache hit
- **WHEN** スキルファイルのハッシュがキャッシュと一致する
- **THEN** LLM を呼び出さず、キャッシュ値を使用する

#### Scenario: Cache miss on file change
- **WHEN** スキルファイルが更新されてハッシュが変わった
- **THEN** LLM で再評価し、新しいハッシュとスコアでキャッシュを更新する

### Requirement: Anti-pattern detection
適性判定時に5つのアンチパターンを検出する（SHALL）。評価時検出の3パターンが2件以上該当で変換非推奨とする。

評価時検出:
1. **Noise Collector**: 失敗多様性スコア=1 → 失敗パターンが少なく、スキル本体修正が効果的
2. **Context Bloat**: 頻度スコア=3 かつ 判断スコア=1 → Pre-flight のトークンコストが学習価値を超える
3. **Band-Aid**: 既存のトラブルシューティングセクションが10項目超 → 設計見直しが必要

運用時警告（変換後スキルに組込み）:
4. **Stale Knowledge**: 剪定なし運用時の警告
5. **Phantom Learning**: PJ固有問題を汎用 pitfall として記録するリスク

#### Scenario: Noise Collector detected
- **WHEN** 失敗多様性スコア=1 のスキルを分析する
- **THEN** 「Noise Collector: 失敗パターンが少ないため、スキル本体の1回修正が効果的です」と警告する

#### Scenario: Multiple anti-patterns trigger rejection
- **WHEN** Noise Collector と Context Bloat の両方に該当するスキルを分析する
- **THEN** 「変換非推奨: 評価時アンチパターン2件該当」と判定し、代替案を提示する

#### Scenario: Runtime anti-patterns included as warnings
- **WHEN** 適性ありのスキルに変換を適用する
- **THEN** Stale Knowledge と Phantom Learning の警告が変換後のスキルに含まれる

### Requirement: Target filter
skill_evolve_assessment() は以下のスキルのみを対象とする（SHALL）:
- `classify_artifact_origin()` が `"custom"` または `"global"` を返すスキル
- pitfalls.md と Failure-triggered Learning セクションが存在しないスキル（未変換）

#### Scenario: Plugin skill excluded
- **WHEN** `classify_artifact_origin()` が `"plugin"` を返すスキル（例: openspec-propose）を走査する
- **THEN** 適性判定をスキップする

#### Scenario: Symlink skill excluded
- **WHEN** スキルディレクトリが symlink であるスキル（例: agent-browser）を走査する
- **THEN** 適性判定をスキップする

#### Scenario: Already evolved skill excluded
- **WHEN** スキルに `references/pitfalls.md` と `Failure-triggered Learning` セクションが既に存在する
- **THEN** 「変換済み」として適性判定をスキップする
