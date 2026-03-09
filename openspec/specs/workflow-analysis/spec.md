## ADDED Requirements

### Requirement: スキル別ワークフロー統計を JSON で出力しなければならない（MUST）

`workflow-analysis analyze` コマンドは workflows.jsonl を読み取り、スキル別のワークフロー統計を JSON で出力しなければならない（MUST）。

#### Scenario: workflows.jsonl が存在しないまたは空の場合
- **WHEN** workflows.jsonl が存在しないまたは空である
- **THEN** 空の JSON オブジェクト `{}` を stdout に出力する
- **AND** stderr に警告メッセージを出力する

#### Scenario: 基本的な統計算出
- **WHEN** workflows.jsonl に opsx:apply の skill-driven ワークフローが 40 件存在する
- **THEN** opsx:apply のエントリに `workflow_count: 40` が含まれる
- **AND** `abstract_patterns` に連続同一エージェントを圧縮したパターンとその出現回数が含まれる
- **AND** `consistency` に最頻抽象パターンの占有率（0.0〜1.0）が含まれる
- **AND** `avg_steps` と `step_std` が含まれる

#### Scenario: 抽象パターンの圧縮
- **WHEN** ワークフローのステップが `[Explore, Explore, Explore, Plan]` の場合
- **THEN** 抽象パターンは `Explore → Plan` として集計される

#### Scenario: team-driven ワークフローの統計
- **WHEN** workflow_type="team-driven" のワークフローが存在する
- **THEN** `team:<team_name>` をキーとして統計を算出する

#### Scenario: agent-burst ワークフローの統計
- **WHEN** workflow_type="agent-burst" のワークフローが存在する
- **THEN** `(agent-burst)` をキーとして統計を算出する

### Requirement: 最小ワークフロー数でフィルタリングできなければならない（MUST）

`--min-workflows N` オプションで N 回未満のスキルを除外できなければならない（MUST）。デフォルトは 3。

#### Scenario: min-workflows フィルタ
- **WHEN** `--min-workflows 5` を指定し、opsx:apply が 40 件、plugin が 2 件
- **THEN** opsx:apply の統計は出力されるが、plugin の統計は出力されない

### Requirement: optimizer 向けの mutation ヒントを生成しなければならない（MUST）

`--hints` オプションを指定した場合、各スキルのワークフロー統計から DirectPatchOptimizer の改善プロンプトに注入するヒントテキストを生成しなければならない（MUST）。

#### Scenario: 低一貫性スキルへのヒント
- **WHEN** opsx:apply の consistency が 0.475 で、Explore パターンが 47.5%、general-purpose が 25.0%
- **THEN** ヒントに「一貫性が中程度（0.48）。Explore と general-purpose の使い分け基準を明確にする指示を検討」のような改善示唆が含まれる

#### Scenario: 高一貫性スキルへのヒント
- **WHEN** agent-browser の consistency が 0.75 で、Explore パターンが支配的
- **THEN** ヒントに「ワークフローは安定している。現在のエージェント戦略を維持」のような確認メッセージが含まれる

### Requirement: generate-fitness 向けのワークフロー統計を出力できなければならない（MUST）

`--for-fitness` オプションを指定した場合、generate-fitness の analyze_project.py 出力に統合可能な形式でワークフロー統計を出力しなければならない（MUST）。

#### Scenario: fitness 向け出力
- **WHEN** `--for-fitness` を指定して実行する
- **THEN** 出力に `workflow_stats` キーが含まれ、スキル別の `consistency`, `avg_steps`, `dominant_pattern` が含まれる
- **AND** この出力は analyze_project.py の出力 JSON にマージ可能な形式である
