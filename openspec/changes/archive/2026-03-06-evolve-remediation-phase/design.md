## Context

evolve パイプラインは Step 7（Report）で audit レポートを表示して終了する。audit.py は行数制限違反（`check_line_limits`）、メモリの陳腐化参照（`build_memory_health_section`）、重複候補（`detect_duplicates_simple`）等を検出するが、これらは情報表示のみで修正アクションに繋がらない。

現在の audit.py は `violations`（行数超過）、`stale_refs`（陳腐化参照）、`near_limits`（肥大化警告）、`duplicates`（重複候補）を個別に生成している。Remediation はこれらの既存データ構造を入力として受け取り、修正アクションを分類・生成する。

## Goals / Non-Goals

**Goals:**
- Report フェーズで検出された問題に対する修正アクションの自動分類と提案
- auto-fixable な問題（陳腐化参照削除等）のワンクリック修正
- proposable な問題（行数超過等）に対する具体的な修正案の生成
- 修正後の再検証による修正完了の確認
- Remediation で必要となる検出カテゴリの追加（既存の検出では不足する場合）

**Non-Goals:**
- audit.py の既存検出ロジック自体の改善（Issue #1 の scope）

## Decisions

### D1: Remediation を evolve の Step 7.5 として追加

**決定**: Report（Step 7）の後に Remediation（Step 7.5）を追加。audit レポートの構造化データを入力として受け取る。`dry_run=True` の場合は問題分類結果のみ出力し、修正アクションは実行しない（Report のみ）。

**理由**: Report が audit データを生成した直後に修正を提案するのが最も自然なフロー。evolve.py の `run_evolve()` にフェーズを追加するだけで統合可能。dry-run 時はレポートの延長として分類情報を見せるだけで十分。

**代替案**: audit 単体に remediation を組み込む案 → 却下。evolve のオーケストレーション責務と一致しないため。

### D2: Confidence-based action tiers（信頼度ベースの段階的分類）

**決定**: 検出された問題を `auto_fixable`、`proposable`、`manual_required` の3カテゴリに分類する。分類は問題タイプの固定マッピングではなく、`confidence_score`（修正の確実性 0.0〜1.0）と `impact_scope`（影響範囲: file / project / global）を算出し、閾値ベースで動的に決定する。

| カテゴリ | 条件 | アクション |
|----------|------|-----------|
| auto_fixable | confidence ≥ 0.9 かつ impact_scope = file | AskUserQuestion で一括承認 → 自動実行 |
| proposable | confidence ≥ 0.5、または impact_scope = project | 具体的な修正案を生成し個別承認 |
| manual_required | confidence < 0.5、または impact_scope = global | 問題と推奨アクションを表示のみ |

同じ問題タイプでも文脈により分類が変わる例:
- stale ref が通常の memory ファイル → auto_fixable
- stale ref が CLAUDE.md（全会話に影響）→ proposable に格上げ
- 行数超過 501/500（1行超過）→ auto_fixable に格下げ可能
- 行数超過 800/500（大幅超過）→ manual_required

**理由**: 問題タイプの固定マッピングでは文脈を無視した分類になる。業界標準（Cranium AI の confidence-based tiers、CodeScene の Code Health ベースの優先度制御）に倣い、リスクと信頼度で動的に分類する。

**代替案**: 問題タイプ固定の3分類 → 却下。CLAUDE.md の stale ref と通常 memory の stale ref を同列に扱うのは不適切。

### D3: remediation.py を新規スクリプトとして作成

**決定**: `skills/evolve/scripts/remediation.py` に問題分類 + 修正アクション生成ロジックを配置。

**理由**: evolve.py のフェーズとして呼び出されるが、ロジックが独立しているため別ファイルに分離。audit.py の出力データ構造（violations, stale_refs 等）を入力として受け取る純粋な変換関数。

### D4: audit.py に構造化データ出力の関数を追加

**決定**: audit.py に `collect_issues()` 関数を追加し、既存の検出結果を統一フォーマットで返す。`generate_report()` のテキスト出力とは別に、remediation.py が消費する構造化 JSON を提供する。

**理由**: 既存の `run_audit()` はテキストレポートを返すが、remediation は構造化データを必要とする。`check_line_limits()` や `build_memory_health_section()` の内部データを再利用する。

### D5: 再検証は Fix Verification + Regression Check の2段構成

**決定**: 修正後の再検証を2段階で実施する。

1. **Fix Verification**: 修正対象ファイルに対して該当する検出関数を再実行し、元の問題が解消されたか確認する。
2. **Regression Check**: 修正が副作用を起こしていないか検証する。具体的には:
   - stale ref の行削除後 → MEMORY の見出し構造（## セクション）が壊れていないか
   - reference 切り出し後 → 元ファイルからの参照リンクが正しいか
   - 空行除去後 → Markdown のフォーマットが崩れていないか

対象は修正されたファイルのみ。全体の audit 再実行は行わない。

**理由**: Cranium AI の研究で「43% of patches introduce new failures」とされており、元問題の解消だけでは不十分。修正による副作用の検出が必要。ただしスコープはファイル単位に限定し、コストを抑制する。

### D6: Remediation outcome の記録（テレメトリ）

**決定**: 修正結果を `~/.claude/rl-anything/remediation-outcomes.jsonl` に記録する。各レコードは `{timestamp, issue_type, category, confidence_score, impact_scope, action, result, user_decision, rationale}` を含む。

**理由**: 修正結果を蓄積することで、(1) 分類精度の評価と改善（evolve-fitness で利用可能）、(2) auto_fixable の拡大判断に必要な実績データの収集、(3) ユーザーが却下した修正パターンの学習、が可能になる。rl-anything は既に corrections.jsonl / usage.jsonl の蓄積基盤を持っており、同じパターンで追加できる。

### D7: Explainability（修正理由の説明）

**決定**: 各修正アクションに `rationale` フィールドを付与する。auto_fixable の一括承認画面では各修正の理由を併記し、proposable では修正案とともに「なぜこの修正が必要か」「なぜこの方法か」を説明する。

**理由**: 一括承認時にユーザーが個々の修正内容を精査しない可能性が高い。監査証跡としても、各修正に対する理由の記録が必要（Cranium AI の Explainability Agent パターン）。

## Risks / Trade-offs

- **[Risk] auto_fixable の誤分類** → Mitigation: confidence_score ≥ 0.9 かつ impact_scope = file の厳格な閾値を設定。remediation-outcomes.jsonl の実績データで閾値を検証・調整する。
- **[Risk] proposable の修正案が不適切** → Mitigation: 全ての proposable 修正は AskUserQuestion で個別承認を必須とし、rationale で理由を明示する。
- **[Risk] audit.py への変更が既存機能に影響** → Mitigation: `collect_issues()` は新規関数として追加。既存の `run_audit()` や `generate_report()` には変更を加えない。
- **[Risk] 修正が副作用を起こす** → Mitigation: Regression Check で構造破壊（見出し欠損、リンク切れ、フォーマット崩壊）を検出。問題発見時は修正をロールバックし manual_required に格上げする。
- **[Risk] テレメトリの肥大化** → Mitigation: remediation-outcomes.jsonl は修正実行時のみ記録（dry-run 時は記録しない）。レコード数は evolve 実行回数 × 検出問題数に比例し、爆発的増加はない。
