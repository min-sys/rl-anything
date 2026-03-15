## MODIFIED Requirements

### Requirement: Active pitfall cap enforcement
自己進化済みスキルの Active pitfall が10件を超えた場合、剪定レビューを提案する（SHALL）。`cap_exceeded` issue を issue_schema 形式で生成し、remediation に渡す（MUST）。confidence は 0.90（auto_fixable）とする（SHALL）。

#### Scenario: Active cap exceeded with issue generation
- **WHEN** あるスキルの Active pitfall が 12 件になった
- **THEN** `cap_exceeded` issue が `{type: "cap_exceeded", file: "<pitfalls.md path>", confidence: 0.90, detail: {skill_name: "...", active_count: 12, cap: 10, cold_count: N}}` 形式で生成される

#### Scenario: Cap exceeded but no cold layer
- **WHEN** Active pitfall が 12 件だが Cold 層が 0 件
- **THEN** `cap_exceeded` issue は生成されるが、`detail.cold_count: 0` を含み、fix 関数側で対処不能を判定する

#### Scenario: Active cap not exceeded
- **WHEN** Active pitfall が 10 件以下
- **THEN** `cap_exceeded` issue は生成されない

### Requirement: Cold layer definition expansion
Cold 層の定義を拡張し、Graduated と Candidate に加えて New も含める（MUST）。アーカイブ優先順位: Graduated > Candidate > New（SHALL）。

#### Scenario: New pitfalls included in cold layer count
- **WHEN** pitfalls.md に Active 10件、New 13件、Candidate 2件、Graduated 1件がある
- **THEN** cold_count は 16（13+2+1）と算出され、アーカイブ対象として利用可能

#### Scenario: Archive priority order respected
- **WHEN** line_guard でアーカイブが必要で Cold 層に Graduated 1件、Candidate 2件、New 5件がある
- **THEN** Graduated → Candidate → New の順でアーカイブされる

### Requirement: Pre-flight scriptification detection
pitfall_hygiene() は Active pitfall の成熟度を評価し、Pre-flight スクリプト化候補を `preflight_candidates` フィールドで出力する（SHALL）。成熟条件: Avoidance-count ≥ 卒業閾値の 50% かつカテゴリが action/tool_use/output のいずれか。

#### Scenario: Scriptification candidates detected
- **WHEN** Active pitfall 10件のうち 3件が成熟条件を満たす
- **THEN** `preflight_candidates: [{pitfall_id: "#5", category: "tool_use", avoidance_count: 8, template: "tool_use.sh"}, ...]` が返却される

#### Scenario: No scriptification candidates
- **WHEN** 全 Active pitfall の Avoidance-count が卒業閾値の 50% 未満
- **THEN** `preflight_candidates` は空リスト

### Requirement: Hygiene result extended fields
pitfall_hygiene() の返却値（既存: `graduation_proposals`, `archive_candidates`, `codegen_proposals`, `line_count`）に、新規フィールド `issues`（issue_schema 形式の issue リスト）と `preflight_candidates` を追加する（SHALL）。`cap_exceeded` と `line_guard` は `issues` フィールド内に issue_schema 形式で出力する（MUST）。

#### Scenario: Extended result with issues and preflight candidates
- **WHEN** pitfall_hygiene() が実行され、cap_exceeded 1件と preflight_candidates 2件が検出された
- **THEN** 従来のフィールドに加え、`issues: [{type: "cap_exceeded", ...}]` と `preflight_candidates: [...]` が返却される
