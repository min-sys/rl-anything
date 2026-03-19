## ADDED Requirements

### Requirement: Workflow checkpoint gap discovery
discover の `run_discover()` は全ワークフロースキルを走査し、不足チェックポイントを `workflow_checkpoint_gaps` フィールドとして結果に含める（SHALL）。

走査対象:
1. プロジェクトの `.claude/skills/` 配下の全スキル
2. `is_workflow_skill()` が True のスキルのみ

各スキルに対して `detect_checkpoint_gaps()` を実行し、ギャップがあるもののみ結果に含める。

#### Scenario: Workflow skills with gaps found
- **WHEN** プロジェクトに3つのワークフロースキル（verify, archive, deploy）があり、verify に infra_deploy ギャップ、deploy に data_migration ギャップがある
- **THEN** `workflow_checkpoint_gaps` に2エントリ（verify, deploy）が含まれ、各エントリにスキル名・ギャップカテゴリ・confidence が含まれる

#### Scenario: No workflow skills in project
- **WHEN** プロジェクトにワークフロースキルが存在しない
- **THEN** `workflow_checkpoint_gaps` は空リストとなる

#### Scenario: Workflow skills without gaps
- **WHEN** 全ワークフロースキルにギャップが検出されない
- **THEN** `workflow_checkpoint_gaps` は空リストとなる

### Requirement: Discover report integration
evolve レポートの Step 10 に「Workflow Checkpoint Gaps」セクションを追加し、検出されたギャップを表示する（SHALL）。

表示形式: スキル名 / ギャップカテゴリ / evidence_count / confidence

#### Scenario: Gaps displayed in evolve report
- **WHEN** discover で workflow_checkpoint_gaps が検出された
- **THEN** evolve レポートに以下のようなセクションが表示される:
  ```
  ### Workflow Checkpoint Gaps
  | Skill | Category | Evidence | Confidence |
  | verify | infra_deploy | 3 | 0.75 |
  ```

#### Scenario: No gaps in report
- **WHEN** workflow_checkpoint_gaps が空
- **THEN** セクション自体が非表示となる
