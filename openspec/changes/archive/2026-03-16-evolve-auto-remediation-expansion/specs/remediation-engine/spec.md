## MODIFIED Requirements

### Requirement: Auto-fixable action execution with rationale
auto_fixable カテゴリの問題に対して、修正アクションと修正理由（rationale）を生成し、AskUserQuestion で一括承認を求める（SHALL）。全レイヤーの auto_fixable issue に対して FIX_DISPATCH テーブル経由で対応する fix 関数を呼び出す（SHALL）。

FIX_DISPATCH に以下を追加する:
- `stale_memory` → `fix_stale_memory()`
- `cap_exceeded` → `fix_pitfall_archive()`
- `line_guard` → `fix_pitfall_archive()`
- `split_candidate` → `fix_split_candidate()`
- `preflight_scriptification` → `fix_preflight_scriptification()`

#### Scenario: Stale memory fix via FIX_DISPATCH
- **WHEN** `stale_memory` issue が auto_fixable に分類された
- **THEN** `FIX_DISPATCH["stale_memory"]` で `fix_stale_memory()` が呼び出され、MEMORY.md から該当エントリ行が削除される

#### Scenario: Pitfall archive fix via FIX_DISPATCH
- **WHEN** `cap_exceeded` issue が auto_fixable に分類された
- **THEN** `FIX_DISPATCH["cap_exceeded"]` で `fix_pitfall_archive()` が呼び出され、Cold 層がアーカイブされる

#### Scenario: Split candidate fix via FIX_DISPATCH
- **WHEN** `split_candidate` issue が proposable に分類され、ユーザーが承認した
- **THEN** `FIX_DISPATCH["split_candidate"]` で `fix_split_candidate()` が呼び出され、分割案テキストが表示される

#### Scenario: Batch approval with rationale display
- **WHEN** auto_fixable な問題が3件検出された
- **THEN** 3件をまとめて表示し、各修正に対する rationale を併記した上で、AskUserQuestion で承認を求める

#### Scenario: Fix dispatch for unknown type
- **WHEN** auto_fixable に FIX_DISPATCH に登録されていない issue type が含まれている
- **THEN** 当該 issue はスキップされ、warning がログ出力される

#### Scenario: Skill evolution fix via FIX_DISPATCH
- **WHEN** `skill_evolve_candidate` issue が proposable に分類され、ユーザーが承認した
- **THEN** `FIX_DISPATCH["skill_evolve_candidate"]` で `fix_skill_evolve()` が呼び出され、自己進化パターンが適用される

### Requirement: Confidence-based issue classification
remediation engine は audit の検出結果を受け取り、各問題に対して `confidence_score`（修正の確実性 0.0〜1.0）と `impact_scope`（file / project / global）を算出し、閾値ベースで `auto_fixable`、`proposable`、`manual_required` の3カテゴリに動的分類する（SHALL）。confidence_score の算出時、confidence-calibration.json が存在しアクティブな場合は、キャリブレーション済みの値で静的値を上書きしなければならない（MUST）。global scope の issue は `confidence >= PROPOSABLE_CONFIDENCE` の場合に `proposable` に昇格する（MUST）。`auto_fixable` にはならない（MUST）。

`duplicate` issue の confidence 算出を修正する（SHALL）。現在の flat 0.4 を similarity ベースに変更し、similarity ≥ DUPLICATE_PROPOSABLE_SIMILARITY（0.75）の場合は DUPLICATE_PROPOSABLE_CONFIDENCE（0.60）を返す。これにより manual_required から proposable に昇格する。新 issue type（duplicate, split_candidate, cap_exceeded, preflight_scriptification 等）は既存の `compute_confidence_score()` 内の confidence-calibration.json override ロジックで自動的に calibration 対象となる（SHALL）。

#### Scenario: Duplicate with high similarity classified as proposable
- **WHEN** `duplicate` issue（similarity 0.81）が classify_issue() に渡された
- **THEN** confidence 0.60, category "proposable" に分類される

#### Scenario: Duplicate with low similarity remains manual_required
- **WHEN** `duplicate` issue（similarity 0.55）が classify_issue() に渡された
- **THEN** confidence < 0.50, category "manual_required" に分類される

#### Scenario: High suitability skill classified as proposable
- **WHEN** skill_evolve_assessment() がスキルを適性高（13点）と判定した
- **THEN** issue type `skill_evolve_candidate` が confidence 0.85, impact_scope "project" で `proposable` に分類される

#### Scenario: High-confidence file-scoped issue classified as auto_fixable
- **WHEN** audit が通常の MEMORY ファイル内の陳腐化参照を検出した
- **THEN** confidence_score ≥ 0.9 かつ impact_scope = file と判定され、`auto_fixable` カテゴリに分類される（従来動作維持）

#### Scenario: Calibrated confidence applied
- **WHEN** confidence-calibration.json に `{stale_ref: {calibrated: 0.80, status: "active"}}` が存在する
- **THEN** stale_ref の confidence_score は 0.95（静的値）ではなく 0.80（キャリブレーション値）が使用される

### Requirement: Verify dispatch for new issue types
VERIFY_DISPATCH に以下を追加する（SHALL）:
- `cap_exceeded` → `_verify_pitfall_archive()`
- `line_guard` → `_verify_pitfall_archive()`
- `split_candidate` → `_verify_split_candidate()`
- `preflight_scriptification` → `_verify_preflight_scriptification()`

`stale_memory` は既に VERIFY_DISPATCH に登録済み。

#### Scenario: Pitfall archive verification
- **WHEN** `fix_pitfall_archive()` 実行後に `_verify_pitfall_archive()` が呼び出された
- **THEN** Active 件数または行数が閾値以下であること、`pitfalls-archive.md` に移動先が存在することを確認する

#### Scenario: Split candidate verification
- **WHEN** `fix_split_candidate()` 実行後に `_verify_split_candidate()` が呼び出された
- **THEN** 提案テキストが生成されたことを確認する（ファイル変更は行わないため、常に resolved=true）

#### Scenario: Preflight scriptification verification
- **WHEN** `fix_preflight_scriptification()` 実行後に `_verify_preflight_scriptification()` が呼び出された
- **THEN** 提案テキストとテンプレートが生成されたことを確認する（ファイル変更は行わないため、常に resolved=true）
