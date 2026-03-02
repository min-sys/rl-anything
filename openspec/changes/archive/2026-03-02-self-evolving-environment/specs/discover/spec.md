## ADDED Requirements

### Requirement: /rl-anything:discover スキルで観測データからスキル/ルール候補を発見しなければならない（MUST）
usage.jsonl、errors.jsonl、sessions.jsonl、history.jsonl の観測データから繰り返しパターンを検出し、スキル/ルール候補を生成しなければならない（MUST）。

#### Scenario: 繰り返し行動パターンの検出
- **WHEN** 同じツール呼び出しパターンが5回以上繰り返されている
- **THEN** スキル候補として提案される

#### Scenario: 繰り返しエラーパターンの検出
- **WHEN** 同じエラーが3回以上記録されている
- **THEN** ルール候補（予防策）として提案される

#### Scenario: 繰り返し却下理由の検出
- **WHEN** 同じ rejection_reason が3回以上記録されている
- **THEN** ルール候補（品質基準）として提案される

### Requirement: 生成されるアーティファクトは構造的制約を満たさなければならない（MUST）
生成されるスキルは SKILL.md 500行以下、ルールは3行以内でなければならない（MUST）。

#### Scenario: スキル候補の構造バリデーション
- **WHEN** スキル候補が生成される
- **THEN** SKILL.md が500行以下であることがバリデーションされる

#### Scenario: ルール候補の構造バリデーション
- **WHEN** ルール候補が生成される
- **THEN** ルールが3行以内であることがバリデーションされる

### Requirement: スコープ配置を判断しなければならない（MUST）
Discover が候補を見つけた時、global / project / plugin のいずれに配置すべきかを判断しなければならない（MUST）。

#### Scenario: global 配置の兆候
- **WHEN** パターンが git/commit/PR/テスト/lint/Claude Code 自体に関連する
- **THEN** global スコープへの配置を提案する

#### Scenario: project 配置の兆候
- **WHEN** パターンが特定フレームワーク依存・ドメイン固有・ファイルパス依存である
- **THEN** project スコープへの配置を提案する

#### Scenario: 中間スコープの兆候
- **WHEN** パターンが特定ツール依存（figma 等）で複数PJで使われうる
- **THEN** global 配置 + Usage Registry 追跡を提案する

### Requirement: claude-reflect データの取り込み（オプション）
claude-reflect がインストールされている場合、learnings-queue のデータも入力ソースとして利用しなければならない（SHALL）。

#### Scenario: claude-reflect 未インストール時
- **WHEN** claude-reflect のファイルが存在しない
- **THEN** Discover は他の入力ソースのみで正常に動作しなければならない（MUST）
