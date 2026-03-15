## Context

evolve の remediation は現在 10 種の issue type を FIX_DISPATCH で自動修正できるが、実運用で検出される問題の多くは「検出のみ・提案表示のみ」で止まっている。具体的には：

- **MEMORY.md**: `stale_memory` は VERIFY_DISPATCH に登録済みだが FIX_DISPATCH に未登録。179/200行で上限接近
- **スキル分割**: reorganize が `split_candidates` を検出するが、remediation に接続されていない
- **pitfall 肥大化**: `cap_exceeded`/`line_guard` は検出のみ。Cold 層の自動アーカイブロジックが未実装
- **重複統合**: `duplicate` は confidence < 0.5 で manual_required に固定
- **verify フェーズ**: 42回中3回しか使われていない（利用率 7%）

## Goals / Non-Goals

**Goals:**
- evolve の dry-run なし実行で、現在 manual_required に分類されている問題の一部を proposable/auto_fixable に昇格させる
- MEMORY.md の stale エントリ削除を自動化し、行数上限到達を防止する
- reorganize → remediation のデータフローを確立し、分割提案を proposable として表示する
- pitfall Cold 層の機械的アーカイブを自動化する
- verify を廃止し、archive に軽量チェックを統合してワークフローを簡素化する

**Non-Goals:**
- MEMORY.md の「統合」（memory_duplicate）の自動実行 — セクション統合は意味理解が必要なため proposable 提案に留める
- スキル分割の自動実行 — 分割粒度の判断が自動化困難なため、LLM 生成の分割案を proposable として表示するに留める
- verify の機能を archive に完全移植 — 仕様カバレッジ等の重い検証は不要。タスク完了率のみ

## Decisions

### D1: stale_memory の FIX_DISPATCH 登録

**決定**: `stale_memory` を FIX_DISPATCH に追加。fix 関数は MEMORY.md から該当エントリ行を削除する。

**代替案**: LLM でエントリを更新する → 却下（更新先の正解を機械的に判定できない。削除のほうが安全）

**実装**: `fix_stale_memory()` — MEMORY.md を読み、`detail.path` に一致するセクション/行を特定して削除。MEMORY.md はインデックスファイルなので、ポインタ行の削除のみ（参照先の個別メモリファイルも存在しなければ削除不要）。

### D2: memory near_limit の proposable 化

**決定**: MEMORY.md が `NEAR_LIMIT_RATIO`（0.8）× MEMORY_LIMIT（200行）= 160行超の場合、`near_limit` issue を生成し proposable として提示。既存定数 `NEAR_LIMIT_RATIO`（audit.py L59）を再利用し、新たな閾値定数は作成しない。提案内容は「最も古い/大きいセクションの個別ファイル分離」。

**代替案**: auto_fixable にする → 却下（どのセクションを分離するかはドメイン知識が必要）

### D3: split_candidates → issue_schema 変換

**決定**: reorganize の `split_candidates` を `make_split_candidate_issue()` で issue_schema 形式に変換し、remediation に渡す。confidence は `SPLIT_CANDIDATE_CONFIDENCE`（0.70、issue_schema.py）で proposable。fix 関数は LLM でセクション分析→分割案テキストを生成して表示する（ファイル変更は行わない）。

**代替案**: 分割を auto_fixable にする → 却下（分割後の逆参照修正が必要で、自動化リスクが高い）

### D4: pitfall Cold 層自動アーカイブ + Cold 層定義拡張

**決定**: `cap_exceeded` と `line_guard` を FIX_DISPATCH に追加。Cold 層の定義を拡張し、Graduated + Candidate に加えて **New** も含める。aws-deploy の実態（New 13件が最大の肥大化要因）から、New を Cold 層に含めないと実効性がない。

**アーカイブ優先順位**: Graduated（役割終了）> Candidate（未昇格）> New（未検証）

**代替案**: Active pitfall も対象にする → 却下（Active は現在進行中の知見なので自動削除は危険）

**実装**: `fix_pitfall_archive()` — Cold 層からアーカイブ優先順位に従ってタイトルリストを選択し、`pitfall_manager.execute_archive(pitfalls_path, titles)` を呼び出す。N は `cap_exceeded` の場合 Active 超過分、`line_guard` の場合は行数が閾値以下になるまで。

**定数**: `CAP_EXCEEDED_CONFIDENCE = 0.90`（pitfall_manager.py）、`PREFLIGHT_MATURITY_RATIO = 0.50`（pitfall_manager.py）

### D4.1: Pre-flight スクリプト化提案（atlas-browser パターン）

**決定**: 成熟した Active pitfall に対して Pre-flight スクリプト化を proposable として提案する。atlas-browser プロジェクトで pitfalls.md 294行→74行（75%削減）を達成した実績パターンを活用。

**成熟条件**: (1) status: Active, (2) Avoidance-count ≥ 卒業閾値の50%, (3) カテゴリが action/tool_use/output（スクリプト化可能）

**実装**: pitfall_hygiene() が `preflight_candidates` を検出 → `preflight_scriptification` issue を生成 → remediation で proposable として提示。`suggest_preflight_script()` が既に pitfall_manager.py に存在するため、これを呼び出してテンプレートを解決する。

**代替案**: auto_fixable にする → 却下（スクリプト生成はプロジェクト固有のパス・ツールに依存するため、提案テキスト表示に留める）

### D5: duplicate の proposable 昇格

**決定**: `duplicate` issue の confidence を similarity ベースに変更（現在 flat 0.4 で manual_required）。similarity ≥ `DUPLICATE_PROPOSABLE_SIMILARITY`（0.75、remediation.py）の場合、`DUPLICATE_PROPOSABLE_CONFIDENCE`（0.60、remediation.py）を返す。LLM で統合案テキストを生成して proposable として提示する。実際の統合は行わない。

**代替案**: auto_fixable にする → 却下（統合対象の選択・内容マージは LLM でも確実性が低い）

### D6: verify 廃止 + archive 軽量チェック統合

**決定**: openspec-verify-change スキルを廃止。archive スキルの既存タスク完了チェックに `ARCHIVE_COMPLETION_THRESHOLD`（0.80、openspec-archive-change SKILL.md 内定数）による閾値判定を追加。ファネル分析から verify を除外。

**代替案A**: verify を残してオプショナルとして扱う → 却下（利用率 7% のスキルを残すメリットがない。ファネル分析のノイズ）
**代替案B**: archive に verify の全機能を統合 → 却下（仕様カバレッジチェック等は archive 時に重すぎる）

## Risks / Trade-offs

- **[stale_memory 誤削除]** → Mitigation: 削除前に AskUserQuestion で確認。auto_fixable だが一括承認フローで個別確認可能
- **[pitfall アーカイブで知見喪失]** → Mitigation: `pitfalls-archive.md` に移動するため復元可能。Active は対象外
- **[duplicate confidence 引き上げで誤提案]** → Mitigation: proposable なのでユーザー承認が必須。LLM 統合案はテキスト提示のみでファイル変更なし
- **[verify 廃止で品質低下]** → Mitigation: 現状でも 93% がスキップしており実質的な品質ゲートになっていない。archive のタスク完了率チェックで最低限のガードは維持
