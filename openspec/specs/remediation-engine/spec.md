## ADDED Requirements

### Requirement: Confidence-based issue classification
remediation engine は audit の検出結果を受け取り、各問題に対して `confidence_score`（修正の確実性 0.0〜1.0）と `impact_scope`（file / project / global）を算出し、閾値ベースで `auto_fixable`、`proposable`、`manual_required` の3カテゴリに動的分類する（SHALL）。

#### Scenario: High-confidence file-scoped issue classified as auto_fixable
- **WHEN** audit が通常の MEMORY ファイル内の陳腐化参照を検出した
- **THEN** confidence_score ≥ 0.9 かつ impact_scope = file と判定され、`auto_fixable` カテゴリに分類される

#### Scenario: Same type escalated by impact scope
- **WHEN** audit が CLAUDE.md 内の陳腐化参照を検出した
- **THEN** impact_scope = project と判定され、`proposable` カテゴリに格上げされる

#### Scenario: Minor line limit violation downgraded
- **WHEN** スキルの行数が制限値を1〜5行だけ超過している
- **THEN** confidence_score ≥ 0.9 と判定され、空行除去等の `auto_fixable` に格下げ可能

#### Scenario: Major line limit violation escalated
- **WHEN** スキルの行数が制限値の160%以上（例: 800/500行）である
- **THEN** confidence_score < 0.5 と判定され、`manual_required` カテゴリに格上げされる

#### Scenario: No issues detected
- **WHEN** audit の検出結果に fixable な問題がない
- **THEN** remediation engine は空の結果を返し、フェーズをスキップする

#### Scenario: Dry-run mode
- **WHEN** evolve が `dry_run=True` で実行されている
- **THEN** 問題の分類結果（confidence_score、impact_scope 含む）のみを出力し、修正アクションは一切行わない

### Requirement: Structured issue collection from audit
audit.py の `collect_issues()` 関数は、既存の検出関数（`check_line_limits`、`build_memory_health_section` 内部データ、`detect_duplicates_simple`）の結果を統一フォーマットの issue リストとして返す（SHALL）。

#### Scenario: collect_issues returns structured data
- **WHEN** `collect_issues(project_dir)` が呼び出された
- **THEN** 各 issue は `{"type": str, "file": str, "detail": dict, "source": str}` 形式で返される

#### Scenario: collect_issues preserves existing audit behavior
- **WHEN** `collect_issues()` が呼び出された
- **THEN** 既存の `run_audit()` や `generate_report()` の動作に影響を与えない

### Requirement: Auto-fixable action execution with rationale
auto_fixable カテゴリの問題に対して、修正アクションと修正理由（rationale）を生成し、AskUserQuestion で一括承認を求める（SHALL）。承認後に修正を実行する。

#### Scenario: Batch approval with rationale display
- **WHEN** auto_fixable な問題が3件検出された
- **THEN** 3件をまとめて表示し、各修正に対する rationale（例:「ディスク上に存在しないパス参照を削除」）を併記した上で、AskUserQuestion で「一括修正」「スキップ」を選択させる

#### Scenario: User skips auto-fix
- **WHEN** ユーザーが auto_fixable の一括修正をスキップした
- **THEN** 修正は実行されず、次のカテゴリの処理に進む。user_decision = "skipped" が記録される

### Requirement: Proposable action generation with explanation
proposable カテゴリの問題に対して、具体的な修正案と「なぜこの修正が必要か」「なぜこの方法か」の説明を生成する（SHALL）。各修正案は AskUserQuestion で個別に承認を求める。

#### Scenario: Line limit violation with reference extraction proposal
- **WHEN** スキルが行数制限を超過している
- **THEN** reference ファイルへの切り出し提案（どのセクションを切り出すか）と理由（例:「Step X が全体の40%を占めており、reference に切り出すことで行数を制限内に収められます」）を生成し、ユーザーに提示する

#### Scenario: Near-limit warning with split proposal
- **WHEN** MEMORY ファイルが NEAR_LIMIT_RATIO（80%）以上に達している
- **THEN** トピック別ファイル分割の提案と理由を生成し、ユーザーに提示する

#### Scenario: User approves proposable fix
- **WHEN** ユーザーが proposable な修正案を承認した
- **THEN** 修正を実行し、結果を表示する。user_decision = "approved" が記録される

#### Scenario: User rejects proposable fix
- **WHEN** ユーザーが proposable な修正案を却下した
- **THEN** 修正は実行されず、user_decision = "rejected" と却下パターンが記録される

### Requirement: Manual-required issue reporting
manual_required カテゴリの問題は、問題の説明、推奨アクション、および分類理由（なぜ自動修正できないか）をテキストで表示する（SHALL）。自動修正や対話的提案は行わない。

#### Scenario: Manual issue displayed with reasoning
- **WHEN** manual_required な問題（例: 行数が制限値の160%超過）が検出された
- **THEN** 問題の概要、推奨される手動アクション、および「大幅な超過のため自動修正では対応できません（confidence: 0.3）」等の分類理由を表示する

### Requirement: Remediation outcome recording
修正結果を `~/.claude/rl-anything/remediation-outcomes.jsonl` に記録する（SHALL）。dry-run 時は記録しない。

#### Scenario: Successful fix recorded
- **WHEN** auto_fixable な修正が成功した
- **THEN** `{timestamp, issue_type, category, confidence_score, impact_scope, action, result: "success", user_decision: "approved", rationale}` が remediation-outcomes.jsonl に追記される

#### Scenario: Skipped fix recorded
- **WHEN** ユーザーが修正をスキップした
- **THEN** `{..., result: "skipped", user_decision: "skipped"}` が記録される

#### Scenario: Dry-run does not record
- **WHEN** evolve が `dry_run=True` で実行されている
- **THEN** remediation-outcomes.jsonl への書き込みは行われない

### Requirement: remediation は新レイヤーの issue type を分類できる
`classify_issue()` は、全レイヤー診断由来の issue type（`orphan_rule`, `stale_rule`, `stale_memory`, `memory_duplicate`, `hooks_unconfigured`, `claudemd_phantom_ref`, `claudemd_missing_section`）に対して適切な `confidence_score` を算出しなければならない（MUST）。

#### Scenario: orphan_rule の confidence_score
- **WHEN** `orphan_rule` issue が分類される
- **THEN** `confidence_score` は 0.4〜0.6 の範囲で算出される（孤立判定は不確実性があるため）

#### Scenario: stale_rule の confidence_score
- **WHEN** `stale_rule` issue（参照先ファイルが存在しない）が分類される
- **THEN** `confidence_score` は 0.9 以上で算出される（ファイル不存在は確実）

#### Scenario: claudemd_phantom_ref の confidence_score
- **WHEN** `claudemd_phantom_ref` issue が分類される
- **THEN** `confidence_score` は 0.85 以上で算出される（スキル/ルールの実在確認は確実性が高い）

#### Scenario: stale_memory の confidence_score
- **WHEN** `stale_memory` issue が分類される
- **THEN** `confidence_score` は 0.5〜0.7 の範囲で算出される（セマンティックパターン検出の不確実性があるため）

#### Scenario: memory_duplicate の confidence_score
- **WHEN** `memory_duplicate` issue が分類される
- **THEN** `confidence_score` は 0.6〜0.8 の範囲で算出される（Jaccard 係数ベースの類似度判定の精度に依存）

#### Scenario: claudemd_missing_section の confidence_score
- **WHEN** `claudemd_missing_section` issue が分類される
- **THEN** `confidence_score` は 0.9 以上で算出される（セクション有無は確実に判定可能）

#### Scenario: hooks_unconfigured の confidence_score
- **WHEN** `hooks_unconfigured` issue が分類される
- **THEN** `confidence_score` は 0.3〜0.5 の範囲で算出される（hooks 未設定は意図的な場合もあるため）

### Requirement: remediation は新レイヤーの issue type に rationale を生成できる
`generate_rationale()` は、全レイヤー診断由来の issue type に対して日本語の修正理由テキストを生成しなければならない（MUST）。

#### Scenario: orphan_rule の rationale
- **WHEN** `orphan_rule` issue の rationale を生成する
- **THEN** 「ルール「{name}」はどのスキル・CLAUDE.md からも参照されていません。」のようなテキストが返される

#### Scenario: claudemd_phantom_ref の rationale
- **WHEN** `claudemd_phantom_ref` issue の rationale を生成する
- **THEN** 「CLAUDE.md 内で言及された{ref_type}「{name}」が存在しません。」のようなテキストが返される

#### Scenario: stale_memory の rationale
- **WHEN** `stale_memory` issue の rationale を生成する
- **THEN** 「MEMORY.md 内の「{path}」への言及は実体が見つかりません。エントリの更新または削除を検討してください。」のようなテキストが返される

#### Scenario: memory_duplicate の rationale
- **WHEN** `memory_duplicate` issue の rationale を生成する
- **THEN** 「MEMORY.md のセクション「{sections[0]}」と「{sections[1]}」は内容が重複しています（類似度: {similarity}）。統合を検討してください。」のようなテキストが返される

#### Scenario: claudemd_missing_section の rationale
- **WHEN** `claudemd_missing_section` issue の rationale を生成する
- **THEN** 「CLAUDE.md に {section} セクションがありませんが、{skill_count} 個のスキルが存在します。セクションの追加を検討してください。」のようなテキストが返される

#### Scenario: hooks_unconfigured の rationale
- **WHEN** `hooks_unconfigured` issue の rationale を生成する
- **THEN** 「hooks 設定が見つかりません。observe hooks の設定を検討してください。」のようなテキストが返される
