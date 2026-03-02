## ADDED Requirements

### Requirement: /rl-anything:feedback スキルでフィードバックを収集しなければならない（MUST）
対話フロー（カテゴリ → ドメイン → スコア → 自由記述）でフィードバックを収集し、GitHub Issue として送信しなければならない（MUST）。

#### Scenario: フィードバックの収集と送信
- **WHEN** ユーザーが `/rl-anything:feedback` を実行する
- **THEN** カテゴリ選択 → ドメイン選択 → スコア入力 → 自由記述の対話フローが開始され、
  プレビュー確認後に GitHub Issue が作成される

#### Scenario: gh 未認証時のフォールバック
- **WHEN** gh CLI が認証されていない
- **THEN** フィードバックは ~/.claude/rl-anything/feedback-drafts/ にローカル保存しなければならない（MUST）

### Requirement: プライバシーを保護しなければならない（MUST）
フィードバックにはスキルの内容やファイルパスを含めてはならない（MUST NOT）。
Issue 送信前に必ずプレビューを表示し、ユーザーの確認を得なければならない（MUST）。

#### Scenario: プレビュー確認
- **WHEN** フィードバックが入力完了する
- **THEN** Issue 本文のプレビューが表示され、ユーザーが承認するまで送信されない

#### Scenario: スキル内容の除外
- **WHEN** フィードバック Issue が生成される
- **THEN** Issue 本文に SKILL.md の内容やローカルファイルパスが含まれない

### Requirement: GitHub Issue テンプレートを配置しなければならない（MUST）
.github/ISSUE_TEMPLATE/feedback.yml に YAML Issue Forms テンプレートを配置しなければならない（MUST）。

#### Scenario: テンプレートの配置
- **WHEN** リポジトリに .github/ISSUE_TEMPLATE/feedback.yml が存在する
- **THEN** GitHub Issue 作成時にフォーム形式でフィードバックを入力できる
