# ADR-008: All-Layer Compile Dispatch Pattern

Date: 2026-03-08
Status: Accepted

## Context

evolve の Compile ステージは Skill レイヤーの修正のみを実行していた（optimize: corrections からパッチ生成、remediation: audit collect_issues() の結果を分類して修正、reflect: corrections からメモリルーティング）。Phase 2（all-layer-diagnose）で `diagnose_all_layers()` が全レイヤーの問題リストを統一フォーマットで出力するようになったが、remediation の fix/verify は Skill レイヤー（stale_ref, line_limit_violation）しか対応しておらず、`orphan_rule`, `stale_rule`, `stale_memory`, `memory_duplicate`, `claudemd_phantom_ref`, `claudemd_missing_section` に対する修正アクションが存在しなかった。

## Decision

- fix 関数をレイヤー別に個別関数として追加し、`FIX_DISPATCH: Dict[str, Callable]` テーブルで issue type から fix 関数にマッピングする dispatch パターンを採用。既存の `fix_stale_references()` も FIX_DISPATCH に統合
- fix 関数のスコープは「確実に安全な修正」に限定。auto_fixable（confidence >= 0.9, scope in ("file", "project")）のみ自動修正。orphan_rule/stale_memory/memory_duplicate は proposable（提案のみ）、hooks_unconfigured は manual_required
- `verify_fix()` も `VERIFY_DISPATCH: Dict[str, Callable]` テーブルで dispatch。FIX_DISPATCH と対称設計にすることで、新 type 追加時に fix/verify の両方を一貫して拡張可能
- `check_regression()` は Rules ファイル用の行数チェックを追加。既存の Markdown チェック（見出し構造保持、コードブロック対応、空ファイルチェック）は全レイヤーに適用可能
- `classify_issue()` の auto_fixable 条件を `scope in ("file", "project")` に緩和（従来は "file" のみ）。CLAUDE.md 修正は project scope だが AskUserQuestion で一括承認を求めるため安全

## Alternatives Considered

- **1つの `fix_all()` 関数で全 type を処理**: 関数が肥大化しテスト困難になるため却下。dispatch パターンにより各レイヤーの修正ロジックは独立してテスト可能
- **verify_fix() を if/elif で分岐**: FIX_DISPATCH と非対称になり、type 追加時に修正箇所が分散するため却下
- **orphan_rule を auto_fixable にする**: 意図的に単独配置されたルールを誤削除するリスクがあるため、proposable に留める
- **hooks_unconfigured を自動修正する**: hooks 設定の自動生成は意図しない副作用のリスクが高いため manual_required に留める
- **classify_issue() の scope 条件を変更せず spec を proposable に修正**: claudemd_phantom_ref / claudemd_missing_section は高信頼度で安全な修正であり、proposable にする必要がないため却下

## Consequences

**良い影響:**
- 全レイヤーの issue に対して統一的な fix/verify/regression check の仕組みが整備され、新しい issue type の追加が容易（dispatch テーブルに1行追加するだけ）
- confidence ベースの3カテゴリ分類（auto_fixable/proposable/manual_required）により、安全性とユーザー体験のバランスが取れる
- 後続のパイプライン拡張（新レイヤー追加等）の基盤が整う

**悪い影響:**
- CLAUDE.md の phantom_ref 行削除で前後の文脈が壊れるリスクがある。check_regression() の見出し構造チェックと連続空行の正規化で緩和
- memory_duplicate の統合はセマンティックな判断が必要で、LLM 支援なしでは品質が担保できない。proposable として提案のみに留める
