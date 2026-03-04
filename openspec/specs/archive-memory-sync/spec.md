# archive-memory-sync Specification

## Purpose
openspec-archive 実行時に、完了した change が MEMORY（auto-memory / global CLAUDE.md）に与える影響を LLM で分析し、更新ドラフト（diff 形式）をユーザーに提示する。

## Requirements
### Requirement: openspec-archive スキルは archive 時に MEMORY への影響を分析しなければならない（MUST）

openspec-archive-change SKILL.md の Step 5（archive 実行）の前に Step 4.5（Memory Sync）を追加しなければならない（MUST）。このステップでは:

1. archive 対象の `proposal.md` と `tasks.md` を読み取る
2. 現在の MEMORY（project auto-memory + global memory）を読み取る
3. Claude Code 自身が「この change は MEMORY のどのセクションに影響するか」を判断する
4. 影響がある場合は更新ドラフト（diff 形式）を提示する
5. ユーザーが承認すれば MEMORY を更新、スキップも可能

#### Scenario: MEMORY に関連セクションがあり更新が必要

- **WHEN** `optimize-fullregen-cost` change を archive し、MEMORY に `## doc-ci-cd-pipeline` セクションがあり、差分更新の実装が反映されていない
- **THEN** Memory Sync ステップで「doc-ci-cd-pipeline セクションの更新を推奨」と表示し、更新ドラフトを提示する

#### Scenario: MEMORY に関連セクションがなく新規追加が必要

- **WHEN** `add-user-auth` change を archive し、MEMORY に認証関連のセクションがない
- **THEN** Memory Sync ステップで「新規セクション追加を推奨」と表示し、追加ドラフトを提示する

#### Scenario: MEMORY に影響なし

- **WHEN** archive 対象の change がテストの修正のみで MEMORY に影響しない
- **THEN** Memory Sync ステップで「MEMORY への影響なし」と表示し、更新提案をスキップする

#### Scenario: ユーザーがスキップを選択

- **WHEN** Memory Sync ステップで更新ドラフトが提示されたが、ユーザーが「スキップ」を選択
- **THEN** MEMORY を更新せずに archive を続行する

### Requirement: Memory Sync は AskUserQuestion で承認を取らなければならない（MUST）

MEMORY の更新は必ず AskUserQuestion ツールでユーザーの承認を取らなければならない（MUST）。自動更新してはならない（MUST NOT）。

選択肢:
- 「更新を適用」: MEMORY を更新ドラフトの内容で更新する
- 「スキップ」: MEMORY を更新せずに archive を続行する

#### Scenario: 更新適用の確認フロー

- **WHEN** 更新ドラフトが提示される
- **THEN** AskUserQuestion で「更新を適用」「スキップ」の選択肢を表示し、ユーザーの選択に従う
