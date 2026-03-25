# ADR-017: evolve-skill Independent Command

Date: 2026-03-18
Status: Accepted

## Context

スキルに自己進化パターン（Pre-flight / Failure-triggered Learning / pitfalls.md）を組み込むには、`evolve` パイプライン全体を回す必要があった（skill_evolve_assessment -> remediation）。自己進化パターン組み込みは1回限りの操作であり、パイプライン全体を回すのはオーバーヘッドが大きかった。

既存モジュール `scripts/lib/skill_evolve.py` に適性判定と変換提案のロジックが実装済みで、`skills/evolve/templates/` にテンプレートも用意されていた。

## Decision

- **独立コマンドを主、rl-loop 統合を副**: `/rl-anything:evolve-skill <name>` で特定スキルをピンポイントで自己進化対応にする独立コマンドを新設。rl-loop の `--evolve` は「最適化のついでに未対応なら提案する」便利フラグとして維持
- **SKILL.md ベースのスキル定義**: `skills/evolve-skill/SKILL.md` に配置。Python スクリプトではなく SKILL.md の方がプラグインのスキル一覧に自然に載り発見しやすい
- **2共通関数を skill_evolve.py に追加**: `assess_single_skill(skill_name, skill_dir)` と `apply_evolve_proposal(proposal)` を新設。独立コマンド・rl-loop・remediation の3箇所から呼び出し、DRY を維持
- **remediation のリファクタ**: 既存の `fix_skill_evolve()` を `apply_evolve_proposal()` のラッパーにリファクタ。SKILL.md 書き込み + pitfalls.md 作成ロジックを共通関数に抽出
- **rl-loop の Step 5.5 に配置**: テキスト最適化（Step 1-5）完了後に自己進化パターンを組み込む。最適化パッチがテンプレート部分を壊すリスクを回避
- **適性 medium 以上で提案**: low/rejected はスキップ。`--auto` 時のみ自動承認、`--dry-run` 時は判定結果表示のみ
- **SKILL.md 変更前にバックアップ**: `.md.pre-evolve-backup` を作成（run-loop.py の `.md.pre-rl-backup` パターンに倣う）

## Alternatives Considered

- **rl-loop のみに統合**: 1回限りの操作にループを回す必要がありオーバーヘッド大のため却下
- **Python スクリプトとして実装**: SKILL.md の方がプラグインスキル一覧に自然に載るため却下
- **適用ロジックを各呼び出し元に個別実装**: 3箇所で同一ロジックが重複し DRY 違反になるため却下
- **Step 1 前に自己進化パターンを組み込み**: 最適化パッチが追加セクションを壊す可能性があるため却下
- **バックアップなし**: テンプレートカスタマイズ結果が不適切だった場合の復元手段がないため却下

## Consequences

**良い影響:**
- 特定スキルをピンポイントで自己進化対応にでき、evolve パイプライン全体を回す必要がなくなった
- 3箇所（独立コマンド・rl-loop・remediation）で同一の共通関数を使うことで、一貫した動作と保守性を確保
- rl-loop に `--evolve` フラグを追加したことで、最適化と自己進化対応の一体実行が可能に

**悪い影響:**
- テンプレートカスタマイズに LLM コスト（`claude -p` 1回）が発生（`--dry-run` 時はスキップ）
- evolve-skill と evolve パイプラインの両経路が存在し、入口が2つある（用途が異なるため共存を許容）
- バックアップファイル `.md.pre-evolve-backup` が蓄積される（1スキル1ファイルのため実質無視できるサイズ）
