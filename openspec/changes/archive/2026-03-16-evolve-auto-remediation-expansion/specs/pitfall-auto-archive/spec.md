## ADDED Requirements

### Requirement: Cold layer auto-archive via FIX_DISPATCH
`cap_exceeded` と `line_guard` issue に対する fix 関数 `fix_pitfall_archive()` を FIX_DISPATCH に登録する（MUST）。fix 関数は Cold 層（status: Graduated, Candidate, New）のうち最も古い項目を `pitfalls-archive.md` に移動する（SHALL）。Active 状態の pitfall は対象外とする（MUST NOT）。

Cold 層の優先順位（アーカイブ順序）:
1. Graduated（役割を終えた知見）
2. Candidate（未昇格）
3. New（未検証 — 最大の肥大化要因になりやすい）

#### Scenario: Cap exceeded — archive by priority order
- **WHEN** スキルの Active pitfall が 12 件で cap（10件）を超過し、Cold 層に Graduated 1件、Candidate 1件、New 5件がある
- **THEN** `fix_pitfall_archive()` が Graduated 1件 → Candidate 1件の順で計 2件を `pitfalls-archive.md` に移動する

#### Scenario: Line guard — archive until under threshold
- **WHEN** `pitfalls.md` が 733 行で PITFALL_MAX_LINES（500行）を超過し、Cold 層に New 13件、Candidate 2件、Graduated 3件がある
- **THEN** `fix_pitfall_archive()` が Graduated → Candidate → New の優先順でアーカイブし、行数が 500 行以下になるまで繰り返す

#### Scenario: No cold layer items available
- **WHEN** `cap_exceeded` だが Cold 層（Graduated/Candidate/New）が 0 件
- **THEN** fix 関数は何も変更せず、`{resolved: false, remaining: "Cold層にアーカイブ対象がありません。Active pitfallの手動レビューが必要です"}` を返す

#### Scenario: Archive preserves pitfall content
- **WHEN** Cold 層の pitfall がアーカイブされる
- **THEN** `pitfalls-archive.md` に移動日時とともに完全な内容が保存される

### Requirement: Pre-flight script promotion proposal
Active pitfall のうち成熟条件を満たすものに対して、Pre-flight スクリプト化を proposable として提案する（SHALL）。成熟条件: (1) status が Active、(2) `Pre-flight対応` フィールドが `yes` であること、(3) Avoidance-count が卒業閾値の PREFLIGHT_MATURITY_RATIO（0.50）以上、(4) カテゴリが action/tool_use/output のいずれか（スクリプト化可能なカテゴリ）。`suggest_preflight_script()` を呼び出してテンプレートを解決し、提案テキストに含める（SHALL）。

#### Scenario: Mature active pitfall proposed for scriptification
- **WHEN** Active pitfall #5（カテゴリ: tool_use、Avoidance-count: 8、卒業閾値: 10）がある
- **THEN** `preflight_scriptification` issue が proposable として生成され、提案テキストに `suggest_preflight_script()` のテンプレート（tool_use.sh）が含まれる

#### Scenario: Active pitfall not mature enough
- **WHEN** Active pitfall #3（カテゴリ: action、Avoidance-count: 2、卒業閾値: 10）がある
- **THEN** `preflight_scriptification` issue は生成されない（50% 未満）

#### Scenario: Non-scriptifiable category excluded
- **WHEN** Active pitfall #7（カテゴリ: knowledge、Avoidance-count: 8）がある
- **THEN** `preflight_scriptification` issue は生成されない（knowledge はスクリプト化不可）

#### Scenario: Scriptification reduces pitfalls.md significantly
- **WHEN** 5 件の Active pitfall がスクリプト化提案を承認された
- **THEN** 各 pitfall が pitfalls.md から削除され、対応する Pre-flight スクリプトが生成される（atlas-browser の 75% 削減パターン）

### Requirement: Pitfall archive verification
VERIFY_DISPATCH に `cap_exceeded` と `line_guard` の検証関数を登録する（MUST）。検証内容: (1) Active 件数が cap 以下になっていること（cap_exceeded の場合）、(2) 行数が閾値以下になっていること（line_guard の場合）、(3) `pitfalls-archive.md` に移動先が存在すること。

#### Scenario: Successful cap verification
- **WHEN** アーカイブ後に Active pitfall が 10 件以下
- **THEN** `{resolved: true}` を返す

#### Scenario: Successful line guard verification
- **WHEN** アーカイブ後に `pitfalls.md` が 500 行以下
- **THEN** `{resolved: true}` を返す
