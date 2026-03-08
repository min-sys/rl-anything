## REMOVED Requirements

### Requirement: Enrich matches patterns to existing skills
**Reason**: enrich の Jaccard 類似度マッチング機能は discover の後処理フィルタに統合される。独立スキルとしての enrich は廃止。
**Migration**: discover の出力に `matched_skills` と `unmatched_patterns` が含まれるようになる。enrich を直接呼び出していたコードは discover の出力を参照するよう変更する。

### Requirement: Jaccard 類似度は共通モジュールから import する
**Reason**: enrich 廃止に伴い、この要件は discover に移管される。
**Migration**: discover.py が `scripts/lib/similarity.py` から直接 import する。
