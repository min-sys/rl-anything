## Why

現在の適応度評価は単一LLMによる数値のみ出力（思考過程なし）で、スコアの信頼性が低い。また `--model haiku/sonnet` をハードコードしているが、ユーザーは Max プラン（サブスク）で Claude Code を使うため、モデル指定は不要かつ品質を制限している。2025年の研究（Think-J, Agent-as-a-Judge, SE-Jury）で評価精度を大幅に向上させる手法が確立されており、それらを取り込む。

## What Changes

- **`--model` ハードコードの削除**: optimize.py, run-loop.py から `--model haiku/sonnet` 指定を除去。Claude Code のデフォルトモデルを使用
- **Chain-of-Thought 評価の導入**: `_llm_evaluate` で思考過程付きJSON出力に変更し、スコアの説明可能性と精度を向上
- **Pairwise Comparison の追加**: エリート選択時にトップ候補同士を直接比較。位置バイアス緩和のため入替2回評価
- **実行ベース評価の追加**: 候補スキルで実際にテストタスクを実行し、出力品質を評価する2段階パイプライン
- **回帰テストゲートの導入**: LLM評価前に構造的必要条件（frontmatter, 禁止パターン等）をチェックし、不合格なら即却下

## Capabilities

### New Capabilities

- `cot-evaluation`: Chain-of-Thought 付き LLM 評価。各基準の根拠を明示してからスコアを算出
- `pairwise-comparison`: 2つの候補スキルを直接比較し、優劣を判定する評価方式
- `execution-based-eval`: テストタスクセットで候補スキルを実行し、出力品質を評価する
- `regression-gate`: LLM評価前の構造的必要条件チェック（ハードゲート）

### Modified Capabilities

（なし — openspec/specs/ に既存 spec なし）

## Impact

- `skills/genetic-prompt-optimizer/scripts/optimize.py`: `_llm_evaluate`, `next_generation`, `evaluate` メソッドの変更
- `skills/rl-loop-orchestrator/scripts/run-loop.py`: `--model` 指定の削除
- **BREAKING**: `--model` オプションをCLI引数から削除。代わりに Claude Code のデフォルト設定を使用
