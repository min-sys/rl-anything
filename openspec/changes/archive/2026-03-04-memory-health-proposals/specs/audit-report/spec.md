## MODIFIED Requirements

### Requirement: /audit レポートに品質推移セクションを含めなければならない（MUST）

audit.py の generate_report() は、既存のセクション（Summary, Line Limit Violations, Usage, Skill Quality Trends, Potential Duplicates, Scope Advisory）に加え、Memory Health セクションを Line Limit Violations の直後に出力しなければならない（MUST）。generate_report() は新たに `project_dir: Optional[Path] = None` パラメータを受け取り、`build_memory_health_section()` に渡す。

#### Scenario: 品質推移セクションの表示

- **WHEN** `/rl-anything:audit` を実行し、quality-baselines.jsonl に commit スキルの計測レコードが 5 件存在する
- **THEN** レポートに "## Skill Quality Trends" セクションが含まれ、commit スキルのスコア推移がスパークライン風に表示される

#### Scenario: quality-baselines.jsonl が存在しない場合

- **WHEN** `/rl-anything:audit` を実行し、quality-baselines.jsonl が存在しない
- **THEN** 品質推移セクションは表示されない（既存のレポートセクションのみ出力）

#### Scenario: 計測レコードが1件のみの場合

- **WHEN** quality-baselines.jsonl にあるスキルの計測レコードが 1 件のみ
- **THEN** そのスキルの現在のスコアのみ表示し、推移グラフは表示しない

#### Scenario: Memory Health セクションとの共存

- **WHEN** Memory Health に問題がありかつ品質推移データもある
- **THEN** Line Limit Violations の後に Memory Health、その後に Usage、Skill Quality Trends の順で表示される
