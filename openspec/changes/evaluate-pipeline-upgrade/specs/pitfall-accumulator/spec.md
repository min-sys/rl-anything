## ADDED Requirements

### Requirement: 失敗パターンの自動蓄積
optimize.py および run-loop.py は最適化中に観測した失敗パターンを対象スキルの `references/pitfalls.md` に自動蓄積しなければならない（MUST）。`references/` ディレクトリが存在しない場合は自動作成しなければならない（MUST）。

#### Scenario: Regression Gate 不合格時の記録
- **WHEN** `_regression_gate` が候補バリエーションを不合格にする（空、行数超過、禁止パターン検出）
- **THEN** 不合格理由を pitfalls.md に追記しなければならない（MUST）。形式: `| {date} | regression-gate | {理由} | - |`

#### Scenario: CoT 評価で特定基準が低スコアの場合
- **WHEN** CoT 評価の結果、いずれかの基準（clarity/completeness/structure/practicality）のスコアが 0.4 未満
- **THEN** その基準名と reason を pitfalls.md に追記しなければならない（MUST）。形式: `| {date} | cot-evaluation | {基準}: {reason} | {score} |`

#### Scenario: rl-loop で人間が却下した場合
- **WHEN** run-loop.py の人間確認ステップでユーザーがバリエーションを却下する
- **THEN** 却下されたバリエーションの CoT 評価結果から最低スコアの基準を pitfalls.md に追記しなければならない（MUST）。形式: `| {date} | human-rejected | {基準}: {reason} | {score} |`

### Requirement: pitfalls.md のフォーマット
pitfalls.md は以下のフォーマットに準拠しなければならない（MUST）。

#### Scenario: 新規作成時のフォーマット
- **WHEN** pitfalls.md が存在せず新規作成する
- **THEN** 以下のヘッダーで作成しなければならない（MUST）:
  ```
  # Known Pitfalls

  最適化プロセスで観測された失敗パターン。fitness 関数の anti_patterns として自動参照される。

  | Date | Source | Pattern | Score |
  |------|--------|---------|-------|
  ```

#### Scenario: 既存の pitfalls.md への追記
- **WHEN** pitfalls.md が既に存在する
- **THEN** 既存の内容を保持したまま、テーブル末尾に新しい行を追記しなければならない（MUST）。既存行を変更・削除してはならない（MUST NOT）

### Requirement: 重複排除
同一の失敗パターンが繰り返し観測された場合でも、pitfalls.md が無制限に肥大化しないよう制御しなければならない（MUST）。

#### Scenario: 同一パターンの重複検出
- **WHEN** 追記しようとするパターンが既存の pitfalls.md に同一の Pattern 文字列で既に存在する
- **THEN** 新規行の追記をスキップしなければならない（MUST）

#### Scenario: pitfalls.md の行数上限
- **WHEN** pitfalls.md のテーブル行数が 50 行を超える
- **THEN** 最も古い行（テーブル上部）を削除してから新しい行を追記しなければならない（MUST）。直近の知見を優先する

### Requirement: Regression Gate の動的拡張
pitfalls.md に蓄積されたパターンを Regression Gate のチェック対象に追加しなければならない（MUST）。

#### Scenario: pitfalls.md のパターンで Regression Gate を強化
- **WHEN** pitfalls.md が存在し、テーブルに `regression-gate` または `cot-evaluation` ソースのパターンが記録されている
- **THEN** `_regression_gate` は静的チェック（空/行数/TODO等）に加えて、pitfalls.md のパターンもチェック対象に含めなければならない（MUST）

#### Scenario: pitfalls.md が存在しない場合
- **WHEN** pitfalls.md が存在しない
- **THEN** `_regression_gate` は静的チェックのみで動作しなければならない（MUST）（後方互換）
