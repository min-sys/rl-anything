## ADDED Requirements

### Requirement: Result summary generation
`optimize.py` の `run()` は戻り値に `summary` dict を含めなければならない（MUST）。以下の情報を構造化データとして返さなければならない（MUST）: 対象パス、ベースラインスコア、最良スコアとスコア差、各世代のベスト/平均/標準偏差/戦略、最良個体の CoT 評価内訳、diff 統計（追加行数、削除行数、変更セクション名）。

#### Scenario: Summary includes baseline comparison
- **WHEN** optimize が完了する
- **THEN** `result["summary"]` に `baseline_score`, `best_score`, `score_delta` が含まれなければならない（MUST）

#### Scenario: Summary includes generation history
- **WHEN** optimize が3世代で完了する
- **THEN** `result["summary"]["generations"]` に各世代の `best`, `avg`, `strategy` が含まれなければならない（MUST）
- **AND** 各世代に `std_dev`（集団内スコアの標準偏差）が含まれるべきである（SHOULD）。集団多様性の指標として GA 標準（DEAP 等）に準拠する

#### Scenario: Summary includes CoT breakdown
- **WHEN** 最良個体に cot_reasons が存在する
- **THEN** `result["summary"]["cot_breakdown"]` に cot-evaluation spec（`openspec/specs/cot-evaluation/spec.md`）で定義された各基準（明確性・完全性・構造・実用性）のスコアと reason が含まれなければならない（MUST）

#### Scenario: Summary includes diff statistics
- **WHEN** 最良個体がベースラインと異なる
- **THEN** `result["summary"]["diff_stats"]` に `lines_added`, `lines_deleted`, `changed_sections` が含まれなければならない（MUST）
- **AND** `changed_sections` は `difflib.unified_diff` の出力から `##` で始まる見出し行の追加・削除・変更を検出して抽出しなければならない（MUST）

#### Scenario: No improvement over baseline
- **WHEN** `score_delta == 0`（最良スコアがベースラインと同一）
- **THEN** サマリの `score_delta` は `0` を返さなければならない（MUST）
- **AND** `diff_stats` は `{"lines_added": 0, "lines_deleted": 0, "changed_sections": []}` を返さなければならない（MUST）
- **AND** SKILL.md 表示時に「改善なし: ベースラインからの変更はありません」と表示しなければならない（MUST）

### Requirement: Summary display in SKILL.md workflow
SKILL.md の accept/reject 確認ステップで、上記サマリをユーザーに表示してから判断を求めなければならない（MUST）。

#### Scenario: User sees summary before accept/reject
- **WHEN** optimize 完了後に accept/reject を確認する
- **THEN** スコア推移、CoT 内訳、diff 統計を含むサマリが表示された後に AskUserQuestion が呼ばれなければならない（MUST）

### Requirement: CoT fallback for missing data
CoT 評価データが欠落している場合、該当フィールドは "N/A" として表示しなければならない（MUST）。

#### Scenario: Missing CoT data handled gracefully
- **WHEN** 最良個体の cot_reasons が None
- **THEN** `result["summary"]["cot_breakdown"]` の各基準は `{"score": "N/A", "reason": "N/A"}` としなければならない（MUST）
