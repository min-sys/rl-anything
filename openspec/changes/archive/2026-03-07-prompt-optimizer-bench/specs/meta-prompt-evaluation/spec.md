## ADDED Requirements

### Requirement: 4メトリクスで評価する

各試行を以下の4メトリクスで独立に評価しなければならない（SHALL）。

| メトリクス | 定義 | 範囲 |
|-----------|------|------|
| score_improvement | LLM CoT 評価の (after - before) | -1.0 〜 1.0 |
| survival_rate | 変異体がオリジナルを上回った比率 | 0.0 〜 1.0 |
| completeness | 出力が途切れず完全なスキルになった比率 | 0.0 〜 1.0 |
| llm_cost | API 呼び出し回数 | 0 〜 N |

#### Scenario: 全メトリクスが記録される

- **WHEN** 1つの試行が完了する
- **THEN** 4メトリクス全てが結果 JSON に記録される

### Requirement: LLM CoT 評価は改善前後の diff を含める

評価プロンプトに元のスキルと変異体の両方を含め、比較評価しなければならない（SHALL）。

#### Scenario: 比較評価

- **WHEN** 変異体を評価する
- **THEN** 評価プロンプトに元のスキルと変異体の diff を含め、「何が改善されたか」「何が劣化したか」を判定する

### Requirement: テストタスク評価（Layer B）を実行できる

スキルにテストタスクセットが紐付けられている場合、実タスク実行で変異体を評価できなければならない（SHALL）。

#### Scenario: テストタスクによる実行評価

- **WHEN** ターゲットスキルに `test_tasks` YAML が紐付けられている
- **THEN** (1) 変異後のスキルを system prompt として `claude -p` でタスクを実行 → (2) 出力品質を別の LLM 呼び出しで評価 → (3) スコアを `score_improvement` に反映する

### Requirement: 変異の完全性を自動判定する

変異体の出力が途中で切れていないかを自動判定しなければならない（SHALL）。

#### Scenario: 完全性チェック

- **WHEN** 変異体が生成される
- **THEN** (1) frontmatter が存在するか (2) 主要セクション（## ヘッダー）が元のスキルと同数以上あるか (3) 末尾が途中で切れていないか を検証する

#### Scenario: 不完全な変異体の扱い

- **WHEN** 完全性チェックが失敗する
- **THEN** `completeness` メトリクスに 0 を記録し、`survival_rate` の計算からも除外する
