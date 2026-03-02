## ADDED Requirements

### Requirement: 生成/更新パイプラインでサイズバリデーションを強制しなければならない（MUST）
evolve / optimize / discover の全パイプラインで、出力アーティファクトのサイズを検証しなければならない（MUST）。

#### Scenario: SKILL.md のバリデーション
- **WHEN** スキルが生成または更新される
- **THEN** 500行以下であることが検証され、超過時は分割を提案しなければならない（MUST）

#### Scenario: rules のバリデーション
- **WHEN** ルールが生成または更新される
- **THEN** 3行以内であることが検証されなければならない（MUST）

#### Scenario: memory ファイルのバリデーション
- **WHEN** memory/*.md が更新される
- **THEN** 120行以下であることが検証され、超過時は分割を提案しなければならない（MUST）

### Requirement: evolve 実行時に bloat check を自動実行しなければならない（MUST）
/evolve 実行時に CLAUDE.md・MEMORY.md・rules 総数・skills 総数をチェックし、レポートに含めなければならない（MUST）。

#### Scenario: 肥大化警告
- **WHEN** CLAUDE.md が150行超、MEMORY.md が150行超、rules が100個超、skills が30個超のいずれか
- **THEN** 対応する警告と改善提案がレポートに含まれなければならない（MUST）

### Requirement: Usage Registry でプロジェクト横断の使用状況を追跡しなければならない（MUST）
~/.claude/rl-anything/usage-registry.jsonl に global スキルの使用をプロジェクト別に記録しなければならない（MUST）。

#### Scenario: 使用状況の記録
- **WHEN** global スキルが使用される
- **THEN** スキル名・プロジェクトパス・タイムスタンプ・使用回数が usage-registry.jsonl に記録される

#### Scenario: Scope Advisor による最適化提案
- **WHEN** audit または evolve が実行される
- **THEN** Usage Registry データに基づき、global ↔ project のスコープ最適化提案がレポートに含まれなければならない（SHALL）

### Requirement: Plugin Bundling 提案を行わなければならない（SHALL）
常に一緒に使われるスキル群を検出し、plugin パッケージ化を提案しなければならない（SHALL）。

#### Scenario: 関連スキル群の検出
- **WHEN** 3つ以上のスキルが常に同じプロジェクト群で使用されている
- **THEN** plugin としてバンドル化する提案を表示しなければならない（SHALL）
