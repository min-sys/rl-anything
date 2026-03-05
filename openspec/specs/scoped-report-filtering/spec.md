## ADDED Requirements

### Requirement: Project-scoped main ranking

evolve の Discover/Audit レポートのメインランキングはプラグインスキルを除外し、PJ 固有スキルのみを集計対象とする。

#### Scenario: Plugin skills excluded from main ranking

- **WHEN** openspec-propose が 95 回、building-ui が 10 回使用されている
- **AND** openspec-propose は openspec プラグインに属する
- **THEN** メインランキングには building-ui が表示され、openspec-propose は表示されない

### Requirement: Plugin usage summary

レポートに「Plugin usage」セクションを追加し、プラグイン別の総使用回数をサマリ表示する。

#### Scenario: Plugin summary display

- **WHEN** openspec プラグインのスキルが合計 340 回、rl-anything プラグインのスキルが 30 回使用されている
- **THEN** `Plugin usage: openspec(340) / rl-anything(30)` と表示される

### Requirement: OpenSpec workflow analytics

openspec プラグインが検出された場合、「OpenSpec Workflow Analytics」セクションを表示する。

#### Scenario: Funnel display

- **WHEN** openspec プラグインのスキルに propose/refine/apply/archive フェーズが含まれる
- **THEN** ファネル（例: `propose(13) → refine(86) → apply(45) → archive(5)`）と完走率が表示される

#### Scenario: Phase efficiency

- **WHEN** 各フェーズの使用レコードが存在する
- **THEN** フェーズ別の実行数、平均ステップ数、一貫性指標が表示される

### Requirement: Discover plugin filtering

discover の `detect_behavior_patterns()` はプラグインスキルをメインランキングから除外し、plugin_summary エントリとして末尾に付加する。さらに missed skill opportunities の検出結果をレポートに含める（MUST）。

#### Scenario: Plugin summary in discover

- **WHEN** openspec-propose が 50 回、rl-anything:audit が 10 回使用されている
- **THEN** メインパターンには含まれず、`plugin_summary` エントリにプラグイン別内訳が含まれる

#### Scenario: Missed skill opportunities in discover report

- **WHEN** missed skill 検出により `channel-routing` が 3セッションで missed と判定された
- **THEN** レポートの `missed_skill_opportunities` セクションにスキル名・トリガーワード・セッション数が含まれる

#### Scenario: No missed skills in report

- **WHEN** missed skill opportunity が 0件
- **THEN** `missed_skill_opportunities` セクションは出力されない
