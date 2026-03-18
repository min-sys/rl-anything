## Why

Superpowers (https://github.com/obra/superpowers) の開発方法論には、rl-anything のテレメトリ基盤と組み合わせて価値のあるアイデアが3つある: 合理化防止テーブル、CSO (Claude Search Optimization)、証拠提示義務。ただし Superpowers プラグイン自体の導入は不要。ワークフローが OpenSpec と重複し、TDD 強制が全スキルに波及するため、知見の cherry-pick に留める。

現状の rl-anything は「スキル/ルールの構造品質」は計測できるが、「合理化によるスキップ」「description の発見性」「検証証拠の提示」は改善対象外。

## What Changes

- **合理化防止テーブルの自動生成**: corrections.jsonl のパターンから「スキップの言い訳 vs 実際の結果」テーブルをテレメトリ裏付きで自動生成。pitfall_manager に統合
- **CSO チェック軸の fitness 追加**: skill_quality fitness に「description が本文の要約になっていないか」「トリガーワードを含むか」等の CSO 検証を追加（Anthropic 公式ツールガイド由来）
- **証拠提示義務パターンの verification_catalog 追加**: 「Evidence before claims」ルールをテンプレート化し、discover/remediation 経由で未導入プロジェクトに提案

**方針**: Superpowers プラグインは導入しない。知見を3つ抽出し、rl-anything のパイプライン（pitfall_manager, skill_quality, verification_catalog）に組み込む。

## Capabilities

### New Capabilities
- `rationalization-prevention`: corrections.jsonl からスキップパターンを検出し、テレメトリ裏付きの合理化防止テーブルを自動生成する機能
- `cso-fitness-check`: スキル description の CSO (Claude Search Optimization) 品質をスコアリングする fitness 軸
- `evidence-verification-pattern`: verification_catalog への「証拠提示義務」パターン追加と discover/remediation 統合

### Modified Capabilities
- `skill-quality-scoring`: CSO チェック軸を追加（既存の rule-based 品質スコアリングを拡張）

## Impact

- **scripts/lib/pitfall_manager.py**: 合理化防止テーブル生成関数の追加
- **scripts/rl/fitness/skill_quality.py**: CSO 8軸目追加
- **scripts/lib/verification_catalog.py**: evidence-before-claims パターン追加
- **scripts/lib/skill_evolve.py**: RATIONALIZATION_* 定数追加
- **.claude/rules/**: verify-before-claim.md, root-cause-first.md 追加
- **discover/evolve/remediation**: 新パターンの統合ポイント
