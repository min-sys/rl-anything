# Phase 3: Optimize（最適化）

既存スキル/ルールの品質を遺伝的アルゴリズムで改善する。

## 既存機能（維持）

- `/optimize <target>` — 個別スキルの遺伝的最適化
- `/rl-loop <target>` — ベースライン取得 → バリエーション生成 → 評価 → 人間確認のループ
- `/generate-fitness` — プロジェクト固有の評価関数を自動生成

## evolve での拡張

### 1. 対象の自動選定

evolve 実行時に全アーティファクトをスキャンし、スコアが閾値以下のものを自動で候補に。

```
Optimize candidates:
  skills/bot-create — score 0.58 (threshold 0.70)
  rules/deploy-check — score 0.45 (threshold 0.60)
```

### 2. ルール対応

skills だけでなく `rules/*.md` も最適化対象に。
ルール用の fitness 関数は「明確性」「抽象化レベル」「3行以内か」で評価。

### 3. claude-reflect の修正を hard constraint として使用

CLAUDE.md に記録された修正パターンを、バリエーション生成時の制約として渡す。

```
例:
  claude-reflect が記録: "don't add emojis unless asked"
  → optimize のバリエーション生成で「絵文字を含むバリアントは生成しない」を制約に
```

### 4. 戦略学習（telemetry 活用）

execution telemetry の戦略別 fitness 改善幅を分析し、
次回の optimize で有効な戦略の配分を自動調整。

```
例:
  過去10回の実績:
    mutation:  平均 +0.12
    crossover: 平均 +0.05
    elite:     平均 +0.00

  → 次回の配分: mutation 70%, crossover 20%, elite 10%
    （デフォルトの均等配分から調整）
```

### 5. CoT reason 活用

過去の CoT 評価 reason テキストをバリエーション生成のヒントとして使用。

```
例:
  高スコアの reason: "エッジケースが網羅されている"
  低スコアの reason: "手順が曖昧で再現性が低い"

  → 次のバリエーション生成で:
    "エッジケースを明示的に列挙し、手順を具体的に記述するバリアントを優先生成"
```

## クロスラン集計（aggregate-runs）

複数の optimize / rl-loop ラン間で傾向を集計するスクリプト。

```bash
python3 skills/audit/scripts/aggregate_runs.py --dir <results_dir>
```

出力:
- pitfalls パターンの出現頻度ランキング
- 承認率（approved / total）
- 戦略別の平均 fitness 改善幅

Report フェーズと `/evolve` のレポートで使用される。
詳細は [report.md](./report.md) を参照。
