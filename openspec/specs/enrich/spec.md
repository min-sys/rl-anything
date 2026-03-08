## DEPRECATED

> **Status**: enrich は廃止されました。Jaccard 類似度マッチング機能は discover の後処理フィルタに統合されています。

### Migration Guide

- enrich の Jaccard 類似度マッチング機能は discover の後処理フィルタに統合された。独立スキルとしての enrich は廃止。
- discover の出力に `matched_skills` と `unmatched_patterns` が含まれるようになる。enrich を直接呼び出していたコードは discover の出力を参照するよう変更する。
- Jaccard 類似度の共通モジュール import（`scripts/lib/similarity.py`）は discover に移管された。

### 旧 Requirements（参考）

以下は廃止前の要件。discover の diagnose-stage spec を参照のこと。

#### Requirement: Enrich matches patterns to existing skills

Enrich Phase は Discover が検出した error_patterns、rejection_patterns、および behavior_patterns を既存スキル群と照合し、関連するスキルを特定する（MUST）。照合にはキーワードマッチ（Jaccard 係数 >= 0.15）を使用する。Jaccard 係数の計算には `scripts/lib/similarity.py` の共通実装を使用しなければならない（MUST）。plugin 由来スキルは照合対象外とする（MUST）。

#### Scenario: Error pattern matches existing skill
- **WHEN** Discover が `error_pattern: "cdk deploy failed: stack timeout"` を検出し、既存スキルに `aws-cdk-deploy`（SKILL.md 内に "cdk" "deploy" キーワードあり）が存在する
- **THEN** Enrich は `aws-cdk-deploy` を関連スキルとして特定し、`matched_skills` リストに含める

#### Scenario: Behavior pattern matches existing skill (fallback)
- **WHEN** errors.jsonl / history.jsonl が未生成で error_patterns / rejection_patterns が空であり、Discover が `behavior_pattern: "Agent:Explore が 477 回使用"` を検出し、既存スキルに Explore 関連のスキルが存在する
- **THEN** Enrich は behavior_patterns からの照合にフォールバックし、関連スキルを `matched_skills` リストに含める

#### Scenario: All pattern sources empty
- **WHEN** errors.jsonl / history.jsonl が未生成で、かつ usage.jsonl にも behavior_patterns が検出されない
- **THEN** Enrich は `{"enrichments": [], "unmatched_patterns": [], "total_enrichments": 0, "total_unmatched": 0, "skipped_reason": "no_patterns_available"}` を出力し、後続フェーズに制御を渡す

#### Scenario: No matching skill found
- **WHEN** Discover が `error_pattern: "docker compose timeout"` を検出し、既存スキルに docker 関連のものが存在しない
- **THEN** Enrich は当該パターンを `unmatched_patterns` リストに含め、Discover の従来フロー（新規候補）に戻す

#### Scenario: Plugin skill excluded from matching
- **WHEN** Discover が `rejection_pattern: "openspec format error"` を検出し、`openspec-propose` スキルが存在するが origin が "plugin"
- **THEN** Enrich は `openspec-propose` を照合対象外とし、当該パターンを `unmatched_patterns` に含める

#### Requirement: Jaccard 類似度は共通モジュールから import する

enrich.py は `tokenize()` と `jaccard_coefficient()` を `scripts/lib/similarity.py` から import しなければならない（MUST）。ローカルに同等の関数を定義してはならない（MUST NOT）。

#### Scenario: import パスの確認
- **WHEN** enrich.py のソースコードを確認する
- **THEN** `from scripts.lib.similarity import tokenize, jaccard_coefficient` または相対パスでの import が存在する

#### Scenario: ローカル定義の除去
- **WHEN** enrich.py 内を `def tokenize` または `def jaccard_coefficient` で検索する
- **THEN** 一致する箇所が存在しない
