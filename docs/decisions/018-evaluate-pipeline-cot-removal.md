# ADR-018: Evaluate Pipeline CoT & Model Hardcode Removal

Date: 2026-03-02
Status: Accepted

## Context

optimize.py の評価パイプラインは `claude -p --model haiku` で数値のみ出力させており、思考過程がなく信頼性が低かった。ユーザーは Max プラン（月額サブスク固定料金）で Claude Code を使うため、`--model haiku` 指定によるコスト最適化は不要であり、むしろ品質を制限していた。2025年の研究（Think-J, Agent-as-a-Judge, SE-Jury）で評価精度を大幅に向上させる手法が確立されていた。

## Decision

- **`--model` ハードコードの削除**: optimize.py, run-loop.py から `--model haiku/sonnet` 指定を全箇所から除去。Claude Code のデフォルトモデルを使用。Max プランではモデル選択はユーザーの Claude Code 設定に委ねる
- **Chain-of-Thought 評価**: `_llm_evaluate` を JSON 構造化出力に変更。各基準（clarity/completeness/structure/practicality）の score + reason を出力し、スコアの説明可能性と精度を向上
- **Pairwise Comparison**: `next_generation` のエリート選択時のみ導入。トップ2候補を比較し、位置バイアス緩和のため A/B 入替で2回評価
- **実行ベース評価**: オプショナルな `--test-tasks` フラグで有効化。候補スキルを `claude -p` でタスク実行し、出力品質を別の `claude -p` で評価する2段階パイプライン。重み: CoT x 0.4 + execution x 0.6
- **回帰テストゲート**: `evaluate` メソッドの先頭でハードゲートチェック（空でない・行数制限内・禁止パターンなし）。不合格なら即 0.0 を返し、無駄な LLM 呼び出しを削減
- **失敗パターンの自動蓄積**: 最適化中に観測した失敗パターン（ゲート不合格・CoT 低スコア・人間却下）を `references/pitfalls.md` に自動蓄積。次回の Regression Gate と fitness 関数にフィードバック。重複排除 + 50行上限 FIFO

## Alternatives Considered

- **`--model` を CLI 引数で外部化**: Max プランでは不要な複雑さのため却下
- **自由記述 + 最後にスコア**: パース不安定のため JSON 構造化出力を採用
- **全個体間の総当たり Pairwise 比較**: O(n^2) で実行時間が爆発するため、エリート選択時のみに限定
- **常に実行ベース評価**: 1個体あたり追加 30-60秒で遅すぎるため、`--test-tasks` オプションで有効化
- **CoT x 0.5 / execution x 0.5（均等）**: 実行ベースの優位性を活かせないため不採用
- **CoT x 0.3 / execution x 0.7（実行重視）**: テストタスクが偏った場合のリスクが大きいため不採用
- **pitfalls.md を使わず result.json に記録**: スキル固有の知見がランごとに分散し世代を跨いだ学習にならないため却下
- **外部フレームワーク（DSPy, Promptfoo, DeepEval）の統合**: 外部依存が増加し Non-Goals

## Consequences

**良い影響:**
- CoT 評価により各基準の根拠が明示され、スコアの信頼性と説明可能性が大幅に向上
- `--model` 削除により Claude Code のデフォルトモデル（通常より高品質）が使われ、評価精度が改善
- 回帰テストゲートにより低品質な候補への無駄な LLM 呼び出しが削減
- pitfalls.md への失敗パターン自動蓄積により、最適化ランを跨いだ知見の蓄積が実現
- Pairwise Comparison によりエリート選択の精度が向上

**悪い影響:**
- CoT 評価は出力量が増え処理が遅くなる（Max プランでは実質コスト影響なし、精度向上とのトレードオフ）
- `--model` 削除は BREAKING CHANGE（既存スクリプトで指定している場合に影響）
- Pairwise の位置バイアスは完全には除去できない（入替2回で緩和、不一致時は絶対スコアにフォールバック）
- pitfalls.md の 50行 FIFO により重要なパターンが消える可能性（将来的に頻度ベースの重要度判定を検討）
