# ADR-007: All-Layer Diagnose Adapter Pattern

Date: 2026-03-08
Status: Accepted

## Context

evolve パイプラインの Diagnose ステージは Skill レイヤーのみを診断対象としていた（discover: usage.jsonl ベースのパターン検出、audit collect_issues(): 行数超過・陳腐化参照・重複候補・ハードコード値、reorganize: split 検出）。coherence.py が Coverage/Consistency/Completeness/Efficiency の4軸でレイヤー横断的な静的分析を行っていたが、診断結果（具体的な問題リスト）としては出力されておらず、evolve の remediation パイプラインに流れていなかった。Rules / Memory / Hooks / CLAUDE.md の4レイヤーは観測データは一部あるが診断メカニズムが不在で、問題（陳腐化、矛盾、肥大化、未使用）が検出されないまま蓄積していた。

## Decision

- レイヤー別診断ロジックを `scripts/lib/layer_diagnose.py` に統合モジュールとして実装する。各診断関数は 30-80 行程度の見込みで、レイヤーごとの独立ファイル分割はオーバーヘッドが利点を上回るため採用しない
- coherence.py の `compute_coherence_score()` を呼び出し、返却される details dict を layer_diagnose.py 内のアダプター関数で issue フォーマットに変換する。coherence.py 自体は変更しない（アダプターパターン）
- issue type はレイヤープレフィックス付きの命名規則を採用: `orphan_rule`, `stale_rule`, `stale_memory`, `memory_duplicate`, `hooks_unconfigured`, `claudemd_phantom_ref` 等
- 既存の `audit.collect_issues()` を拡張し、新レイヤーの診断呼び出しを追加する（新関数 `collect_all_issues()` は作らない）
- Hooks の診断は `settings.json` の設定存在チェックのみとする。テレメトリベース診断は観測データ不足のため将来対応

## Alternatives Considered

- **レイヤーごとに独立ファイル（rules_diagnose.py, memory_diagnose.py 等）**: 各関数が 30-80 行と小規模で、ファイル分割のオーバーヘッドが利点を上回るため却下
- **coherence.py の `_check_*()` 内部関数を抽出して共有**: リグレッションリスクが増加し、coherence.py のテスト維持コストが上がるため却下。アダプターパターンで details dict を変換するだけで十分
- **新たに `collect_all_issues()` を作成**: evolve.py が既に `collect_issues()` を呼んでおり、呼び出し元の変更が不要な既存関数の拡張を選択
- **Hooks のテレメトリベース診断（エラー率・未使用検出）**: errors.jsonl に hook イベント名が記録されておらず、信頼性が担保できないため延期

## Consequences

**良い影響:**
- Rules / Memory / Hooks / CLAUDE.md の問題が evolve パイプラインで自動検出されるようになり、全レイヤーの健全性を維持できる
- coherence.py との重複実装を避けつつ、アダプターパターンで責務を分離できる
- 統一フォーマット `{"type", "file", "detail", "source"}` により、後続の Compile ステージ（remediation）への統合が容易

**悪い影響:**
- `orphan_rule` 等の偽陽性リスクがある（実際は使われているルールを誤検出する可能性）。confidence_score を低め（0.4-0.6）に設定し、proposable/manual_required に分類することで緩和
- Subagents レイヤーは観測データ不足のため除外。テレメトリ蓄積後に別フェーズで対応が必要
