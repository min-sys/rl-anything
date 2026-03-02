## ADDED Requirements

### Requirement: /rl-anything:audit スキルで環境の健康診断を実行しなければならない（MUST）
全 skills / rules / memory の棚卸し + 行数チェック + 使用状況集計を行い、1画面レポートを出力しなければならない（MUST）。

#### Scenario: 健康診断レポートの出力
- **WHEN** ユーザーが `/rl-anything:audit` を実行する
- **THEN** アーティファクト一覧・サイズ・使用頻度・重複候補・Scope Advisory を含む1画面レポートが出力される

#### Scenario: 行数チェック
- **WHEN** audit が実行される
- **THEN** CLAUDE.md（200行）、rules（3行）、SKILL.md（500行）、MEMORY.md（200行）、memory/（120行）の制限超過が検出される

### Requirement: Global ↔ Project 重複検出を実行しなければならない（MUST）
global と project に意味的に類似したスキル/ルールがある場合、統合を提案しなければならない（MUST）。
意味的類似度の判定は LLM ベースで行い、閾値は 80% とする（SHALL）。
本 spec が意味的類似度検出ロジックの Single Source of Truth である。

#### Scenario: 重複検出と統合提案
- **WHEN** global と project に類似度 80% 以上のスキル/ルールが存在する
- **THEN** 統合提案がレポートに含まれる

### Requirement: Scope Advisory を提供しなければならない（MUST）
Usage Registry データに基づき、global スキルの使用PJ数と頻度を表示しなければならない（MUST）。
スコープの最適化（global → project 降格、project → global 昇格）を提案しなければならない（SHALL）。

#### Scenario: Scope Advisory レポート
- **WHEN** audit が実行される
- **THEN** 各 global スキルの使用PJ数・最終使用日・推奨アクションが表示される

### Requirement: クロスラン集計を実行しなければならない（MUST）
scripts/aggregate-runs.py で複数の optimize/rl-loop 実行結果を集計しなければならない（MUST）。

#### Scenario: クロスラン集計の実行
- **WHEN** 複数の history.jsonl エントリが存在する状態で集計を実行する
- **THEN** 戦略別（elite/mutation/crossover）の有効性・スコア推移・accept/reject 比率が集計される
