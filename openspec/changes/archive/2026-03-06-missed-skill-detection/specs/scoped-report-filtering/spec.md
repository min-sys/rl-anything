## MODIFIED Requirements

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
