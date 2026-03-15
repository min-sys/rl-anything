## MODIFIED Requirements

### Requirement: Task completion check on archive
openspec-archive-change スキルの既存タスク完了チェック（Step 3 の `- [ ]` 未完了警告）に、ARCHIVE_COMPLETION_THRESHOLD（0.80）による閾値判定を追加する（MUST）。完了率が 80% 未満の場合、警告を表示して AskUserQuestion で続行確認を求める（SHALL）。80% 以上の場合はそのまま archive を続行する（SHALL）。既存の個別未完了タスク警告は維持する（SHALL）。

#### Scenario: All tasks complete
- **WHEN** tasks.md の全チェックボックスが `[x]` で完了率 100%
- **THEN** 警告なしで archive を続行する

#### Scenario: Completion rate below 80%
- **WHEN** tasks.md の完了率が 60%（6/10 タスク完了）
- **THEN** 「タスク完了率 60%（6/10）— 未完了タスクがあります」と警告し、AskUserQuestion で「続行する」「中止する」を提示する

#### Scenario: Completion rate at 80%
- **WHEN** tasks.md の完了率がちょうど 80%（8/10 タスク完了）
- **THEN** 警告なしで archive を続行する

#### Scenario: No tasks.md exists
- **WHEN** change ディレクトリに tasks.md が存在しない
- **THEN** 完了率チェックをスキップし、archive を続行する

### Requirement: Verify skill deprecation
openspec-verify-change スキルを廃止する（MUST）。SKILL.md を削除し、CLAUDE.md のスキル一覧から除外する（SHALL）。

#### Scenario: Verify skill removed
- **WHEN** evolve-auto-remediation-expansion の実装が完了した
- **THEN** `.claude/skills/openspec-verify-change/SKILL.md` が削除され、CLAUDE.md から verify-change の記載が除外されている

### Requirement: Funnel analysis excludes verify
ファネル分析（OpenSpec Workflow Analytics）から verify フェーズを除外する（MUST）。ファネルは `propose → refine → apply → archive` の 4 段階とする（SHALL）。

#### Scenario: Funnel without verify
- **WHEN** evolve の Report で OpenSpec Workflow Analytics が表示される
- **THEN** ファネルは `propose(N) → refine(N) → apply(N) → archive(N)` の 4 段階で表示され、verify は含まれない
