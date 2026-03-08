## ADDED Requirements

### Requirement: Diagnose ステージはパターン検出と問題検出を統合する
Diagnose ステージは discover（パターン検出 + enrich 統合）、audit 問題検出（collect_issues）、reorganize（split 検出のみ）を1ステージとして実行しなければならない（MUST）。出力はレイヤー別の問題リストと候補リストを含まなければならない（MUST）。

#### Scenario: 全サブステップが実行される
- **WHEN** evolve が Diagnose ステージを実行する
- **THEN** discover（enrich 統合済み）、audit 問題検出、reorganize（split 検出）が順に実行され、統合された診断結果が生成される

#### Scenario: discover がパターン未検出でも他のサブステップは実行される
- **WHEN** discover がパターンを検出しない（usage.jsonl のデータ不足等）
- **THEN** audit 問題検出と reorganize（split 検出）は正常に実行される

### Requirement: Diagnose の出力は discover に enrich の照合結果を含む
discover の出力に、既存スキルとの Jaccard 類似度照合結果（旧 enrich の機能）を含まなければならない（MUST）。照合には `scripts/lib/similarity.py` の `jaccard_coefficient` を使用しなければならない（MUST）。

#### Scenario: パターンが既存スキルに一致
- **WHEN** discover が `error_pattern: "cdk deploy failed"` を検出し、既存スキルに `aws-cdk-deploy` が存在する
- **THEN** discover の出力の `matched_skills` に `aws-cdk-deploy` が含まれ、`similarity_score` が付与される

#### Scenario: パターンが既存スキルに不一致
- **WHEN** discover が `error_pattern: "docker compose timeout"` を検出し、docker 関連スキルが存在しない
- **THEN** discover の出力の `unmatched_patterns` に当該パターンが含まれる

### Requirement: Diagnose は session-scan を実行しない
discover のテキストレベルパターンマイニング（session-scan）は実行してはならない（MUST NOT）。usage.jsonl ベースのパターン検出のみを使用しなければならない（MUST）。

#### Scenario: session-scan が呼ばれない
- **WHEN** Diagnose ステージが実行される
- **THEN** discover 内の session-scan 関連コード（テキストマイニング）は実行されない
