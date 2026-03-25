# ADR-009: Simplify Pipeline to 3-Stage Architecture

Date: 2026-03-08
Status: Accepted

## Context

evolve パイプラインは8ステージ（Observe / Discover / Enrich / Optimize / Reorganize / Prune / Reflect / Report）/ 15スキル / 約8,350 LOC と複雑すぎる構成だった。enrich が 164 LOC の薄いラッパー、reorganize と prune がマージ候補を二重検出、regression gate が optimize.py にハードコードされている等の問題が判明していた。業界の成功例（DSPy, Reflexion, OpenAI Cookbook）は最大3ステージで同等以上の効果を達成している。

## Decision

- **8ステージから3ステージ（Diagnose / Compile / Housekeeping）に統合**: 各グループ内は順序依存があるが、グループ間は概念的に独立
  - Diagnose: discover（パターン検出 + enrich 統合済み）+ audit 問題検出 + reorganize（split 検出のみ）
  - Compile: optimize（corrections からパッチ + 共通 gate）+ remediation（audit 違反の自動修正）+ reflect（corrections からメモリルーティング）
  - Housekeeping: prune（ゼロ使用アーカイブ + マージ提案）+ evolve-fitness（30+ サンプル時のみ）
- **enrich を discover の後処理フィルタに統合**: `_enrich_patterns()` 関数として discover.py に組み込み、独立スキルとしての enrich は廃止
- **マージ候補検出を prune に一元化**: reorganize からマージ候補検出を削除し split 検出のみに縮小。prune の semantic similarity ベースの検出に一本化
- **regression gate を `scripts/lib/regression_gate.py` に共通ライブラリとして抽出**: optimize.py と rl-loop で共有。`GateResult` dataclass + `check_gates()` インターフェース。スコアフィールドは含めず合否判定のみ
- **discover から session-scan（テキストレベルパターンマイニング、約50 LOC）を削除**: ノイズが多く usage.jsonl ベースの検出で十分カバー
- **backfill をパイプライン外のセットアップコマンドに再分類**: 実行頻度が1-2回で日常パイプラインの一部ではない

## Alternatives Considered

- **enrich を残しつつ evolve から直接呼ばない**: 将来の混乱を招くため却下
- **session-scan を optional flag (`--with-session-scan`) として残す**: 使用実績がなくコード複雑化するため却下
- **reorganize の TF-IDF クラスタリングを prune に移植**: 複雑化するため却下。prune の既存 semantic similarity で十分
- **backfill を evolve の初回実行時に自動呼び出し**: セットアップは明示的に行うべきため却下

## Consequences

**良い影響:**
- スキル数 15 から 14 へ削減、LOC 約8,350 から約7,900 へ約450 LOC 削減
- パイプラインの構造が明確になり、後続の全層 Diagnose / 全層 Compile / 自己進化の土台が整う
- regression gate の共通化により、optimize / rl-loop / 将来の全層 Compile で統一的な品質ゲートを適用可能
- マージ候補検出の二重実装が解消される

**悪い影響:**
- enrich 統合により discover.py が約164 LOC 増加
- evolve SKILL.md の全面書き換えによりプロンプト品質が一時的に低下するリスクがある（既存ステップの記述は維持して緩和）
- reorganize のマージ検出削除で精度低下の可能性があるが、prune の semantic similarity が同等以上の精度を持つため影響は限定的
