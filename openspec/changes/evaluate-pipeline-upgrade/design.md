## Context

optimize.py の評価パイプラインは現在3段構成: カスタム fitness → LLM評価（フォールバック）。LLM評価は `claude -p --model haiku` で数値のみ出力させており、思考過程がなく信頼性が低い。ユーザーは Max プラン（月額サブスク）で Claude Code を使うため、API コスト最適化のための `--model haiku` 指定は不要。

現行の評価フロー:
```
evaluate() → _run_custom_fitness() → 見つからなければ → _llm_evaluate(haiku, 数値のみ)
```

## Goals / Non-Goals

**Goals:**
- `--model` ハードコードを除去し、Claude Code のデフォルトモデルを使用
- LLM評価の精度向上（CoT、Pairwise）
- 実行ベース評価で「スキルが実際に機能するか」を測定
- 回帰テストゲートで最低品質を保証

**Non-Goals:**
- 外部フレームワーク（DSPy, Promptfoo, DeepEval）の統合
- マルチモデルアンサンブル（SE-Jury的な複数LLM並列評価）
- メタ評価（評価関数自体の品質測定）— 将来スコープ

## Decisions

### 1. `--model` 指定の除去方針

**選択**: `claude -p` のみ使用。`--model` フラグを全箇所から削除

**代替案**: `--model` を CLI 引数で外部化（`optimize.py --eval-model opus`） → 不要な複雑さ。Max プランではモデル選択は Claude Code 側で管理

**理由**: Max プランはサブスク固定料金。モデル選択はユーザーの Claude Code 設定（`/model` コマンド）に委ねるのが自然。plugin 側がモデルを強制する理由がない

### 2. CoT評価の出力形式

**選択**: JSON構造化出力（各基準のscore + reason）

```json
{
  "clarity": {"score": 0.8, "reason": "手順が番号付きで明確"},
  "completeness": {"score": 0.7, "reason": "エッジケースの記述が不足"},
  "structure": {"score": 0.9, "reason": "見出し階層が適切"},
  "practicality": {"score": 0.75, "reason": "コード例があるが不完全"},
  "total": 0.79
}
```

**代替案**: 自由記述 + 最後にスコア → パース不安定。JSON なら `--output-format json` との相性も良い

### 3. Pairwise Comparison の導入箇所

**選択**: `next_generation` のエリート選択時のみ。トップ2候補を比較し、位置バイアス緩和のため A/B 入替で2回評価

**代替案**: 全個体間の総当たり比較 → O(n²) で実行時間が爆発

**理由**: エリート選択が進化の方向性を決める最重要ポイント。ここだけ高精度にすれば十分

### 4. 実行ベース評価の設計

**選択**: オプショナルな `--test-tasks` フラグで有効化。テストタスクファイル（YAML）を指定すると、候補スキルを `claude -p` に渡してタスクを実行し、出力品質を別の `claude -p` 呼び出しで評価する2段階パイプライン

**代替案**: 常に実行ベース評価 → 遅すぎる（1個体あたり追加30-60秒）

**理由**: 実行ベース評価はコストが高い。`--test-tasks` がない場合は従来の CoT 評価のみで動作し、後方互換を維持

#### Weight 根拠（CoT × 0.4 + execution × 0.6）
- 実行ベース評価は実際のタスク遂行能力を直接測定するため、LLM判定（CoT）より信頼性が高い
- ただし全タスクをカバーできるとは限らないため、CoT を補完的に保持
- 参考: Agent-as-a-Judge (2024) では実行ベース評価がLLM判定を精度で上回る結果
- 代替案: 0.5/0.5（均等）→ 実行ベースの優位性を活かせない
- 代替案: 0.3/0.7（実行重視）→ テストタスクが偏った場合のリスクが大きい
- 0.4/0.6 は実行ベースの信頼性を反映しつつ、CoT による網羅性を確保するバランス点

### 5. 失敗パターンの自動蓄積（pitfall-accumulator）

**選択**: 最適化中に観測した失敗パターンを対象スキルの `references/pitfalls.md` に自動蓄積し、次回の Regression Gate と fitness 関数に反映するフィードバックループを構築

**観測ポイント（3箇所）**:

| 観測ポイント | 記録する内容 | トリガー条件 |
|---|---|---|
| Regression Gate 不合格 | 不合格理由（空/行数超過/禁止パターン） | ゲート不合格時 |
| CoT 評価の低スコア | 基準名 + reason | いずれかの基準が 0.4 未満 |
| rl-loop の人間却下 | 却下バリエーションの最低基準 + reason | ユーザーが却下時 |

**蓄積先**: 対象スキルの `references/pitfalls.md`（Markdown テーブル形式）

**安全策**:
- 重複パターンは追記スキップ
- テーブル行数上限 50 行（FIFO で古い行を削除）
- 既存行の変更・削除は行わない（追記のみ）

**フィードバック経路**:
```
optimize/rl-loop 実行 → 失敗パターン観測 → pitfalls.md に蓄積
  ↓
次回 Regression Gate → pitfalls.md のパターンも動的チェック
  ↓
次回 generate-fitness → pitfalls.md を anti_patterns として取り込み
```

**代替案**: pitfalls.md を使わず optimize.py 内部の result.json に記録 → スキル固有の知見がランごとに分散し、世代を跨いだ学習にならない

**理由**: pitfalls.md はスキルに紐づくファイルとして永続化されるため、最適化ランを跨いで知見が蓄積される。generate-fitness-skill の project-analyzer が既に pitfalls.md の読み取りに対応しているため、蓄積と消費の両方が plugin 内で完結する

### 6. 回帰ゲートの設計

**選択**: `evaluate` メソッドの先頭でハードゲートチェック。不合格なら即 0.0 を返す

チェック項目:
- 空でないこと
- 行数制限内であること（既存の `_check_line_limit`）
- 禁止パターン（`TODO`, `FIXME`, `HACK`）がないこと

**理由**: LLM 呼び出し前にフィルタリングすることで、無駄な API 呼び出しを削減

## Risks / Trade-offs

- **[CoT評価が遅くなる]** → 思考過程分の出力が増えるが、Max プランでは実質コスト影響なし。精度向上のトレードオフとして許容
- **[Pairwise の位置バイアスが完全には除去できない]** → 入替2回で緩和。完全一致しない場合は絶対スコアにフォールバック
- **[実行ベース評価のテストタスク設計が手間]** → generate-fitness-skill と組み合わせてテストタスクも自動生成する将来拡張で対応
- **[`--model` 削除は BREAKING]** → 既存の CI スクリプト等で `--model` を指定している場合に影響。CLAUDE.md に移行手順を記載
- **[pitfalls.md の肥大化]** → 50 行上限 + 重複排除で制御。古いパターンは FIFO で削除されるが、重要なパターンが消える可能性あり → 将来的に頻度ベースの重要度判定を検討
