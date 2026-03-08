## 1. 共通 Regression Gate ライブラリの抽出

- [x] 1.1 `scripts/lib/regression_gate.py` を新設: `GateResult` dataclass と `check_gates()` 関数を実装（shared-regression-gate spec 準拠）。pitfall パターンロード機能を含む
- [x] 1.2 `check_gates()` のユニットテスト作成: 空コンテンツ、行数超過、禁止パターン、frontmatter 消失、pitfall パターン検出、全通過の6シナリオ
- [x] 1.3 `optimize.py` のゲートロジックを `check_gates()` 呼び出しに置換（regression-gate spec 準拠）
- [x] 1.4 rl-loop は現行の `check_line_limit()` チェックを維持。optimize 経由で gate 済みパッチを受け取る構造を確認
- [x] 1.5 既存テスト（`scripts/tests/`, `skills/genetic-prompt-optimizer/tests/`）が全て通ることを確認

## 2. enrich → discover 統合

- [x] 2.1 `discover.py` に `_enrich_patterns()` 関数を追加: `scripts/lib/similarity.py` の `jaccard_coefficient` を使用して既存スキルとの照合を実行（diagnose-stage spec 準拠）
- [x] 2.2 discover の出力 JSON に `matched_skills` と `unmatched_patterns` フィールドを追加
- [x] 2.3 discover の session-scan 関連コード（テキストレベルパターンマイニング）を削除
- [x] 2.4 enrich の SKILL.md frontmatter に `deprecated: true` を追加
- [x] 2.5 discover に enrich 統合後の Jaccard 照合テストを新規作成（`matched_skills`, `unmatched_patterns` の出力検証）

## 3. reorganize のマージ検出削除

- [x] 3.1 `reorganize.py` から `merge_groups` 生成ロジックを削除（reorganize spec 準拠）
- [x] 3.2 reorganize の出力 JSON から `merge_groups` と `total_merge_groups` フィールドを除去
- [x] 3.3 reorganize の split 検出テストを新規作成（300行超検出、全スキル300行以下時の空リスト）
- [x] 3.4 evolve SKILL.md 内の reorganize 呼び出し箇所を確認し、マージ結果参照を削除

## 4. evolve オーケストレーターの3ステージ再構成

- [x] 4.1 evolve の SKILL.md を3ステージ構成（Diagnose → Compile → Housekeeping）に書き換え
- [x] 4.2 Diagnose ステージ: discover（enrich 統合済み）→ audit 問題検出（collect_issues）→ reorganize（split 検出のみ）の順序で記述
- [x] 4.3 Compile ステージ: optimize（corrections → パッチ）→ remediation（audit 違反修正）→ reflect（メモリルーティング）の順序で記述
- [x] 4.4 Housekeeping ステージ: prune（ゼロ使用アーカイブ + マージ提案）→ evolve-fitness（30+ サンプル時のみ）の順序で記述
- [x] 4.5 evolve SKILL.md 内の enrich 呼び出しを削除（discover に統合済み）

## 5. backfill の再分類とドキュメント更新

- [x] 5.1 backfill の SKILL.md description を「セットアップコマンド」として更新（日常パイプラインではない旨を明記）
- [x] 5.2 CLAUDE.md の「3つの柱」テーブルを Pattern B の3ステージ構成に更新
- [x] 5.3 README.md のパイプライン説明を3ステージ構成に更新
- [x] 5.4 docs/roadmap.md を Pattern B の5 Phase ロードマップに更新

## 6. 統合テストと最終確認

- [x] 6.1 全テストスイート実行: `python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v`
- [x] 6.2 evolve の手動実行テスト: 3ステージが正しく順序実行されることを確認
- [x] 6.3 optimize の手動実行テスト: 共通 gate が正しく動作することを確認
