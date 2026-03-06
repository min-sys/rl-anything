## Context

現在の optimize は結果表示として run_id、世代数、集団サイズ、最良スコア、最良個体ID、各世代のベスト/平均を出力する。accept/reject 確認時にはこの情報のみで判断を求める。ベースラインとの差分や変更内容の要約がなく、ユーザーは「何が変わったのか」を理解できない。

## Goals / Non-Goals

**Goals:**
- accept/reject 確認前に、判断に必要な情報を一画面で表示
- ベースラインとの diff サマリ、CoT 評価内訳、スコア推移を含める

**Non-Goals:**
- 結果表示の対話的操作（ページング、フィルタリング等）
- diff の全行表示（サマリのみ）

## Decisions

### D1. サマリ生成の実装箇所

`optimize.py` の `run()` 戻り値に `summary` フィールドを追加し、SKILL.md の accept/reject ステップで表示。

**根拠**: SKILL.md 側で LLM に diff 生成させるのではなく、Python 側で構造化データとして出力する方が一貫性がある。Optuna/DEAP 等の最適化ツールも構造化データ（dict/JSON）で結果を返却し、CLI 表示は整形テキストとする設計が標準。

**代替案**: LLM にサマリを自然言語で生成させる → 却下: optimize 自体が既にコスト高く、追加 API コストは避けるべき。構造化データの方がテスト可能性も高い。

### D2. サマリの内容

```
=== 最適化結果サマリ ===
対象: skills/my-skill/SKILL.md
ベースラインスコア: 0.72
最良スコア: 0.85 (+0.13)
戦略: mutation (Gen 2)

--- スコア推移 ---
Gen | Best  | Avg   | StdDev | 戦略
  0 | 0.72  | 0.68  | 0.03   | elite
  1 | 0.80  | 0.74  | 0.05   | mutation
  2 | 0.85  | 0.78  | 0.02   | mutation

--- CoT 評価内訳 (最良個体) ---
clarity:      0.90 (reason: ...)
completeness: 0.85 (reason: ...)
structure:    0.88 (reason: ...)
practicality: 0.80 (reason: ...)

--- 変更サマリ ---
+12 行追加, -3 行削除, 2 セクション変更
主な変更: エッジケース対処の追加、構造の整理
```

**baseline_score の取得元**: 世代0の最初の個体（= オリジナルスキル）の評価スコア。`history[0]["individuals"][0]["fitness"]` から取得する。

**代替案の検討**:

| 代替案 | 説明 | 採否 | 理由 |
|--------|------|------|------|
| A: std dev 追加 | 世代テーブルに集団内スコアの標準偏差を表示 | **採用** | GA 標準（DEAP 等）で集団多様性の指標として一般的。収束度合いの判断材料になる |
| B: sparkline 表示 | audit.py の `generate_sparkline()` でスコア推移を視覚化 | **不採用** | `generate_sparkline()` は品質トレンド用（数十データポイント想定）で、世代数3程度では視覚効果が薄い |
| C: トップN個体の比較表示 | ベスト1個体だけでなくトップN個体を表示 | **不採用** | `population_size=3` でトップ1以外の表示は情報過多。判断を複雑にするだけで実用性が低い |

### D3. diff サマリの生成方法

`difflib.unified_diff` でベースラインと最良個体の diff を取得し、追加/削除行数をカウント。主な変更点は変更されたセクション見出し（`##` 行）から抽出。

**代替案**: LLM で diff を要約 → 却下: 追加 API コストが発生し、optimize 自体が既にコスト高い。

### D4. CoT 基準名の参照

CoT 評価の基準名（clarity, completeness, structure, practicality）は `openspec/specs/cot-evaluation/spec.md` の定義に準拠する。基準が将来変更された場合は、cot-evaluation spec の更新に追従して本サマリも更新する。ハードコードは `_generate_summary()` 内の1箇所に限定し、変更時の影響範囲を最小化する。

## Commonality Analysis

| 既存ユーティリティ | 場所 | 再利用検討 | 結論 |
|-------------------|------|-----------|------|
| `generate_sparkline()` | `skills/audit/scripts/audit.py:793` | スコア推移の視覚化に使えるか検討 | **不採用**: 世代数3程度ではスパークライン（`_` から `^` の8段階）の視覚効果が薄い。audit の品質トレンド（数十データポイント）とはユースケースが異なる |

## Risks / Trade-offs

- **出力の長さ**: サマリが長すぎるとユーザーが読まない → CoT reason は1行に制限、diff は統計のみ
- **CoT データの欠落**: LLM 評価が失敗した場合 cot_reasons が None → フォールバックで "N/A" 表示
- **std dev の計算コスト**: population_size=3 のため統計的意味は限定的だが、収束傾向の参考にはなる
