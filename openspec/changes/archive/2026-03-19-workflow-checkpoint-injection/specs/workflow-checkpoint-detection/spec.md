## ADDED Requirements

### Requirement: Workflow skill identification
workflow_checkpoint モジュールは SKILL.md からワークフロースキルを判定する関数 `is_workflow_skill(skill_dir)` を提供する（SHALL）。判定は frontmatter 優先 + ヒューリスティクスフォールバックによる。

**判定ロジック**:
1. **frontmatter 優先**: SKILL.md frontmatter に `type: workflow` が存在すれば即 True
2. **ヒューリスティクスフォールバック**（frontmatter なしの場合）:
   - 基準A: `Step`/`Phase`/`ステップ`/`フェーズ` キーワードが numbered list 内に存在
   - 基準B: numbered markdown list（`1.` `2.` `3.`...）が3項目以上存在
   - 基準C: `Input`/`Output`/`入力`/`出力` キーワードが存在
   - 判定: 基準A+B の両方が成立で True、または基準A のみで numbered list 5項目以上で True

#### Scenario: Workflow skill via frontmatter
- **WHEN** SKILL.md frontmatter に `type: workflow` が宣言されている
- **THEN** `is_workflow_skill()` は True を返す（ヒューリスティクスをスキップ）

#### Scenario: Workflow skill with Step keywords
- **WHEN** SKILL.md に `1. Step 1: Analyze ...`, `2. Step 2: Generate ...`, `3. Step 3: Apply ...` が含まれる（frontmatter に type 未宣言）
- **THEN** `is_workflow_skill()` は True を返す（基準A+B 成立）

#### Scenario: Simple utility skill
- **WHEN** SKILL.md にステップ構造がなく、単一の操作のみを記述している
- **THEN** `is_workflow_skill()` は False を返す

#### Scenario: Skill with Phase-based structure
- **WHEN** SKILL.md に `Phase 1: Diagnose`, `Phase 2: Compile`, `Phase 3: Report` が含まれる
- **THEN** `is_workflow_skill()` は True を返す

#### Scenario: Step keywords with many numbered items
- **WHEN** SKILL.md に `ステップ` キーワードが numbered list 内に存在し、numbered list が5項目以上
- **AND** 基準B は単独では成立していない（基準A のみ）
- **THEN** `is_workflow_skill()` は True を返す（基準A + 5項目以上ルール）

### Requirement: Checkpoint gap detection from telemetry
`detect_checkpoint_gaps(skill_name, skill_dir, project_dir)` はテレメトリデータ（corrections.jsonl, errors.jsonl, workflows.jsonl）を分析し、ワークフロースキルに不足しているチェックポイントを特定する（SHALL）。

検出ロジック:
1. corrections.jsonl からスキル使用後の修正パターンを集計（`last_skill` フィルタ）
2. errors.jsonl からスキル実行中のエラーパターンを集計
3. 修正/エラーパターンを CHECKPOINT_CATALOG の各カテゴリの `detection_fn` で照合
4. マッチしたカテゴリのうち、SKILL.md に既存チェックが無いものを「ギャップ」として返す

**タイムアウト保護**: 検出処理全体に `CHECKPOINT_DETECTION_TIMEOUT_SECONDS=5` のタイムアウトを設定する（SHALL）。タイムアウト時は空のギャップリストを返す。

#### Scenario: Infrastructure deploy gap detected
- **WHEN** corrections.jsonl に openspec-verify 使用後「prodデプロイ忘れ」関連の修正が3件以上ある（`last_skill` フィルタ）
- **AND** SKILL.md にデプロイ確認ステップが存在しない
- **AND** プロジェクトが IaC プロジェクトである（detect_iac_project() = True）
- **THEN** `{"category": "infra_deploy", "evidence_count": 3, "confidence": 0.75}` を含むギャップリストが返される

#### Scenario: No gaps found
- **WHEN** スキルのテレメトリに修正/エラーパターンが CHECKPOINT_CATALOG のどのカテゴリにもマッチしない
- **THEN** 空のギャップリストが返される

#### Scenario: Gap already covered by existing step
- **WHEN** corrections.jsonl にデプロイ関連の修正があるが、SKILL.md に既にデプロイ確認ステップがある
- **THEN** そのカテゴリはギャップとして検出されない

#### Scenario: Telemetry data missing
- **WHEN** corrections.jsonl / errors.jsonl が存在しない、または空ファイルである
- **THEN** 空のギャップリストが返される（エラーを発生させない）

#### Scenario: Detection timeout
- **WHEN** 検出処理が CHECKPOINT_DETECTION_TIMEOUT_SECONDS を超過する
- **THEN** 空のギャップリストが返される（エラーを発生させない）

### Requirement: Checkpoint gap confidence scoring
各チェックポイントギャップに confidence スコアを付与する（SHALL）。

**定数**:
- `BASE_CHECKPOINT_CONFIDENCE=0.5`: ベースライン confidence
- `EVIDENCE_BONUS_PER_COUNT=0.05`: テレメトリ証拠1件あたりのボーナス
- `MAX_EVIDENCE_BONUS=0.25`: 証拠ボーナスの上限
- `GATE_BONUS=0.1`: applicability gate 通過時のボーナス

計算式: `BASE_CHECKPOINT_CONFIDENCE + min(evidence_count * EVIDENCE_BONUS_PER_COUNT, MAX_EVIDENCE_BONUS) + GATE_BONUS(if gate passed)`

**confidence 上限**: チェックポイント注入は SKILL.md を編集するため、常に proposable 分類（人間承認必須）とする。confidence 上限 0.85 は意図的設計であり、auto_fixable に分類されることを防止する。

#### Scenario: High evidence count
- **WHEN** 特定カテゴリの修正/エラーが6件以上あり、applicability gate を通過している
- **THEN** confidence は 0.5 + 0.25 + 0.1 = 0.85

#### Scenario: Low evidence count
- **WHEN** 特定カテゴリの修正/エラーが2件のみ
- **THEN** confidence は 0.5 + 0.10 = 0.60（gate 未通過時）

### Requirement: Minimum evidence threshold
チェックポイントギャップの検出には最低 MIN_CHECKPOINT_EVIDENCE=2 件のテレメトリ証拠を要求する（SHALL）。

#### Scenario: Evidence below threshold
- **WHEN** 特定カテゴリの修正/エラーが1件のみ
- **THEN** そのカテゴリはギャップとして検出されない

#### Scenario: Evidence at threshold
- **WHEN** 特定カテゴリの修正/エラーがちょうど2件
- **THEN** そのカテゴリはギャップとして検出される
