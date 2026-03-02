## MODIFIED Requirements

### Requirement: Individual クラスにテレメトリフィールドを追加しなければならない（MUST）
Individual クラスに strategy フィールドと cot_reasons フィールドを追加し、to_dict() で出力されるようにしなければならない（MUST）。

#### Scenario: strategy フィールドの記録
- **WHEN** mutate() が実行される
- **THEN** 生成された Individual の strategy が "mutation" に設定される

#### Scenario: crossover の strategy 記録
- **WHEN** crossover() が実行される
- **THEN** 生成された Individual の strategy が "crossover" に設定される

#### Scenario: elite の strategy 記録
- **WHEN** next_generation() でエリートが選出される
- **THEN** エリート Individual の strategy が "elite" に設定される

#### Scenario: cot_reasons の保存
- **WHEN** _llm_evaluate() が実行される
- **THEN** LLM の reason テキストが Individual の cot_reasons に保存される

### Requirement: history.jsonl に rejection_reason と human_accepted を記録しなければならない（MUST）
人間の accept/reject 判断と、reject 時のオプション理由を history.jsonl に記録しなければならない（MUST）。
本 spec が rejection_reason および human_accepted の記録仕様の Single Source of Truth である。
他の spec（fitness-evolution 等）はこのデータを参照する。

#### Scenario: accept の記録
- **WHEN** ユーザーが候補を accept する
- **THEN** history.jsonl エントリに human_accepted: true が追加されなければならない（MUST）

#### Scenario: reject と理由の記録
- **WHEN** ユーザーが候補を reject し、理由を入力する
- **THEN** history.jsonl エントリに human_accepted: false と rejection_reason が追加されなければならない（MUST）

#### Scenario: 理由なし reject
- **WHEN** ユーザーが候補を reject し、理由を入力しない
- **THEN** history.jsonl エントリに human_accepted: false と rejection_reason: null が追加されなければならない（MUST）
