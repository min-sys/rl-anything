## orphan_rule → unused_rule 移行ロードマップ

### 背景

orphan_rule（CLAUDE.md/SKILL.md から参照されていないルール）は、`.claude/rules/` が Claude の auto-load 対象であるため事実上 dead code となった。本 change で orphan_rule issue type を廃止する。

代替として、telemetry ベースの `unused_rule`（実行セッションで一度も呼び出されていないルール）検出への移行を計画する。

### Phase 1: データ基盤（既存）

- sessions.jsonl / usage.jsonl に rule 呼び出しの痕跡を記録する仕組みの検討
- 現状の observe hooks はスキル呼び出しを記録しているが、ルール単位の利用追跡は未実装

### Phase 2: unused_rule 検出

- telemetry_query.py に `query_rule_usage()` を追加
- 一定期間（例: 30日）呼び出し実績のないルールを `unused_rule` として検出
- `diagnose_rules()` に unused_rule issue type を追加
- coherence.py の Efficiency 軸に反映

### Phase 3: audit 統合

- audit レポートに unused_rule セクションを追加
- evolve の remediation で unused_rule に対するアクション提案（削除/統合）

### 留意事項

- ルール単位の利用追跡は Claude の内部動作に依存するため、直接的な検出は困難な場合がある
- 代替アプローチ: corrections.jsonl の修正パターンとルール内容の突合で「効果のないルール」を推定
