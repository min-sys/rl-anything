## ADDED Requirements

### Requirement: /audit レポートに Constitutional Score セクションを含めなければならない（MUST）
audit レポートに `--constitutional-score` オプションが指定された場合、`compute_constitutional_score()` を呼び出し、"## Constitutional Score" セクションをレポートに追加しなければならない（MUST）。`--constitutional-score` 未指定時はセクションを表示してはならない（MUST NOT）。

#### Scenario: --constitutional-score 指定時のセクション表示
- **WHEN** `audit --constitutional-score` を実行し、5 原則の評価が完了する
- **THEN** "## Constitutional Score" セクションが表示され、overall スコア、原則別スコア、推定コストが含まれる

#### Scenario: --constitutional-score 未指定時
- **WHEN** `audit` をオプションなしで実行する
- **THEN** "## Constitutional Score" セクションは表示されない

#### Scenario: 原則キャッシュが存在しない場合の初回抽出
- **WHEN** `audit --constitutional-score` を実行し、`.claude/principles.json` が存在しない
- **THEN** LLM で原則を自動抽出してキャッシュした後、Constitutional 評価を実行する

#### Scenario: LLM 呼び出し失敗時のフォールバック
- **WHEN** `audit --constitutional-score` を実行し、LLM 呼び出しが全て失敗する
- **THEN** "## Constitutional Score" セクションに「LLM 評価に失敗しました」と表示し、他のセクション（Coherence/Telemetry）は正常に表示する

### Requirement: Chaos Score の audit 統合
`--constitutional-score` 指定時、Constitutional Score セクション内に Chaos Testing の結果サブセクション "### Chaos Testing (Robustness)" を含めなければならない（MUST）。重要度ランキング上位 5 件と robustness_score を表示する。

#### Scenario: Chaos Testing 結果の表示
- **WHEN** `audit --constitutional-score` を実行し、Rules 5件 + Skills 10件の Chaos Testing が完了する
- **THEN** "### Chaos Testing (Robustness)" サブセクションに robustness_score と重要度ランキング上位 5 件が表示される

#### Scenario: single_point_of_failure の警告
- **WHEN** 1 つの構成要素の ΔScore が `THRESHOLDS["spof_delta"]`（0.15）以上
- **THEN** 該当要素に "SPOF WARNING" マーカーが表示される

### Requirement: Section ordering
`--constitutional-score --coherence-score --telemetry-score` が全て指定された場合、セクションは以下の順序で表示しなければならない（MUST）:
1. Environment Fitness（全体スコア）
2. Constitutional Score
3. Coherence Score
4. Telemetry Score

#### Scenario: 全オプション指定時のセクション順序
- **WHEN** `audit --constitutional-score --coherence-score --telemetry-score` を実行する
- **THEN** レポート内のセクションが Environment Fitness → Constitutional → Coherence → Telemetry の順序で表示される
