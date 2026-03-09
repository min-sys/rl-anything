# audit-report Specification

## Purpose
/audit レポートの出力形式と内容を定義する。品質推移セクション、劣化検知警告、Memory Health セクションの Semantic Verification サブセクションを含む。

## Requirements
### Requirement: /audit レポートに品質推移セクションを含めなければならない（MUST）

audit.py の generate_report() は、高頻度 global スキルの品質スコア履歴を読み込み、品質推移セクション（"## Skill Quality Trends"）をレポートに含めなければならない（MUST）。品質推移セクションには各スキルのスコア履歴をスパークライン風（Unicode ブロック文字）で視覚化しなければならない（SHALL）。

#### Scenario: 品質推移セクションの表示

- **WHEN** `/rl-anything:audit` を実行し、quality-baselines.jsonl に commit スキルの計測レコードが 5 件存在する
- **THEN** レポートに "## Skill Quality Trends" セクションが含まれ、commit スキルのスコア推移がスパークライン風に表示される

#### Scenario: quality-baselines.jsonl が存在しない場合

- **WHEN** `/rl-anything:audit` を実行し、quality-baselines.jsonl が存在しない
- **THEN** 品質推移セクションは表示されない（既存のレポートセクションのみ出力）

#### Scenario: 計測レコードが1件のみの場合

- **WHEN** quality-baselines.jsonl にあるスキルの計測レコードが 1 件のみ
- **THEN** そのスキルの現在のスコアのみ表示し、推移グラフは表示しない

### Requirement: 劣化検知時に警告と /optimize 推奨をレポートに表示しなければならない（MUST）

品質推移セクションにおいて劣化が検知されたスキルには、警告マーカーと /optimize 推奨コマンドを表示しなければならない（MUST）。劣化なしのスキルには警告マーカーを表示してはならない（MUST NOT）。

#### Scenario: 劣化スキルの警告表示

- **WHEN** commit スキルのスコアが 0.85 から 0.74 に低下し劣化と判定されている
- **THEN** レポートの品質推移セクションに commit スキルの行に "DEGRADED" 警告マーカーと推奨コマンド "/optimize commit" が表示される
- **FORMAT**: `commit  ▁▃▅▇▅▃ 0.74 DEGRADED → /optimize commit`

#### Scenario: 劣化なしスキルの正常表示

- **WHEN** openspec-refine スキルのスコアがベースラインから 5% 以内の変動に収まっている
- **THEN** レポートの品質推移セクションに openspec-refine スキルの行に警告マーカーは表示されない
- **FORMAT**: `openspec-refine  ▃▅▅▇▇ 0.82`

### Requirement: 品質推移セクションに再スコアリングが必要なスキルを表示しなければならない（SHALL）

前回計測から使用回数 50 回以上または 7 日以上経過したスキルを "RESCORE NEEDED" として表示しなければならない（SHALL）。

#### Scenario: 再スコアリングが必要なスキルの表示

- **WHEN** commit スキルの前回計測から 8 日経過している
- **THEN** レポートの品質推移セクションに commit スキルの行に "RESCORE NEEDED" マーカーが表示される

#### Scenario: 再スコアリングが不要なスキルの表示

- **WHEN** openspec-refine スキルの前回計測から 2 日前で使用回数差分が 10
- **THEN** レポートの品質推移セクションに "RESCORE NEEDED" マーカーは表示されない

### Requirement: /audit レポートに Memory Health セクションを含めなければならない（MUST）

audit.py の generate_report() は Memory Health セクションを含めなければならない（MUST）。Memory Health セクションは既存のルールベース検証（パス存在チェック + 肥大化警告）に加え、LLM セマンティック検証の結果サマリーを Semantic Verification サブセクションとして含めなければならない（MUST）。

Semantic Verification サブセクションは audit SKILL.md のステップで Claude Code が検証した結果を表示する。audit.py 自体は LLM を呼ばず、セマンティック検証用のコンテキスト収集のみを行う。

#### Scenario: Memory Health セクションにセマンティック検証結果が含まれる

- **WHEN** `/rl-anything:audit` を実行し、MEMORY に3セクションあり LLM 検証で1件が MISLEADING、1件が STALE と判定される
- **THEN** レポートの Memory Health セクション内に "### Semantic Verification" サブセクションが含まれ、MISLEADING 1件と STALE 1件の判定結果と修正提案が表示される

#### Scenario: 全セクションが CONSISTENT の場合

- **WHEN** MEMORY の全セクションが LLM 検証で CONSISTENT と判定される
- **THEN** "### Semantic Verification" サブセクションに「全セクション整合」と表示する

#### Scenario: auto-memory が存在しない場合

- **WHEN** auto-memory ディレクトリが存在せず global memory にも PJ 固有セクションがない
- **THEN** Semantic Verification サブセクションは表示しない

### Requirement: /audit レポートに Coherence Score セクションを含めなければならない（MUST）
audit レポートに `--coherence-score` オプションが指定された場合、`compute_coherence_score()` を呼び出し、"## Environment Coherence Score" セクションをレポートに追加しなければならない（MUST）。`--coherence-score` 未指定時はセクションを表示してはならない（MUST NOT）。Coherence Score セクションは既存セクションの先頭（## Skill Quality Trends の前）に表示する。

#### Scenario: --coherence-score 指定時のセクション表示
- **WHEN** `/rl-anything:audit --coherence-score` を実行し、coherence スコアが overall=0.85, coverage=1.0, consistency=0.7, completeness=0.9, efficiency=0.8 の場合
- **THEN** レポートに "## Environment Coherence Score" セクションが含まれ、以下のフォーマットで overall スコアと4軸の内訳が表示される:
  ```
  ## Environment Coherence Score: 0.85
  Coverage:     1.00 ████████████████████
  Consistency:  0.70 ██████████████░░░░░░ ← CLAUDE.md に skill-x が記載されているが実在しない
  Completeness: 0.90 ██████████████████░░
  Efficiency:   0.80 ████████████████░░░░
  ```

#### Scenario: --coherence-score 未指定時
- **WHEN** `/rl-anything:audit` を実行する（`--coherence-score` なし）
- **THEN** レポートに "## Environment Coherence Score" セクションは含まれない

#### Scenario: 低スコア軸への改善アドバイス表示
- **WHEN** いずれかの軸スコアが 0.7 未満の場合
- **THEN** Coherence Score セクション内に、0.7 未満の軸ごとに fail したチェック項目を箇条書きで表示する

### Requirement: Audit report output
audit スキルは `--telemetry-score` オプションで Telemetry Score セクションをレポートに追加しなければならない（MUST）。

既存の `--coherence-score` と同様のフォーマットで:
- 3軸スコア（Utilization / Effectiveness / Implicit Reward）を個別表示 MUST
- overall スコアを表示 MUST
- data_sufficiency が False の場合は警告メッセージを表示 MUST
- `--coherence-score` と `--telemetry-score` の両方が指定された場合、Environment Fitness（統合スコア）も表示 MUST

#### Scenario: Telemetry score display
- **WHEN** `audit --telemetry-score` を実行する
- **THEN** レポートに Telemetry Score セクション（3軸 + overall + data_sufficiency）が表示される

#### Scenario: Combined score display
- **WHEN** `audit --coherence-score --telemetry-score` を実行する
- **THEN** Coherence Score + Telemetry Score + Environment Fitness（統合スコア）が表示される

#### Scenario: Insufficient data warning
- **WHEN** `audit --telemetry-score` を実行し、data_sufficiency が False
- **THEN** 警告メッセージ「Data insufficient: N sessions (minimum 30 required)」が表示される

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

## ADDED Requirements (self-evolution)

### Requirement: Pipeline Health section in audit report
audit レポートに `--pipeline-health` オプションが指定された場合、"## Pipeline Health" セクションをレポートに追加しなければならない（MUST）。`--pipeline-health` 未指定時はセクションを表示してはならない（MUST NOT）。

#### Scenario: --pipeline-health with sufficient data
- **WHEN** `audit --pipeline-health` を実行し、remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件以上の outcome がある
- **THEN** "## Pipeline Health" セクションが表示され、issue_type 別の precision、approval_rate、false_positive_count が表形式で表示される

#### Scenario: --pipeline-health with insufficient data
- **WHEN** `audit --pipeline-health` を実行し、remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件未満の outcome しかない
- **THEN** "## Pipeline Health" セクションに「データ不足（N/`MIN_OUTCOMES_FOR_ANALYSIS` 件）。evolve を繰り返し実行してデータを蓄積してください。」と表示する

#### Scenario: --pipeline-health with degraded type
- **WHEN** ある issue_type の approval_rate が `APPROVAL_RATE_DEGRADED_THRESHOLD`（デフォルト: 0.7）未満
- **THEN** 該当行に "DEGRADED" マーカーを表示し、`/rl-anything:evolve` での self-evolution を推奨する

#### Scenario: Section ordering with other score sections
- **WHEN** `audit --pipeline-health --coherence-score --telemetry-score` を実行する
- **THEN** Pipeline Health セクションは既存スコアセクション（Environment Fitness → Constitutional → Coherence → Telemetry）の後に表示される

### Requirement: Pipeline Health は LLM コール不要
Pipeline Health セクションの生成は remediation-outcomes.jsonl の集計のみで行い、LLM 呼び出しを行ってはならない（MUST NOT）。

#### Scenario: No LLM cost
- **WHEN** `audit --pipeline-health` を実行する
- **THEN** LLM API への呼び出しは発生せず、Python の集計処理のみで完了する
