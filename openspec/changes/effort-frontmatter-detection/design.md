## Context

CC v2.1.80 で SKILL.md frontmatter に `effort: low|medium|high` を記述するとスキル呼び出し時の effort level を自動設定できる。rl-anything プラグインは自身の15スキルに effort を設定済みだが、ユーザー環境のプロジェクトスキルには未設定のものが多い。既存の audit → evolve → remediation パイプラインに検出・推定・提案を統合する。

## Goals / Non-Goals

**Goals:**
- effort 未設定スキルを audit/evolve で自動検出する
- スキル特性（行数・frontmatter・キーワード）からレベルを推定する
- remediation ハンドラで frontmatter 自動追加を提案する

**Non-Goals:**
- effort レベルの精密な最適化（テレメトリベースの動的調整等）
- CC バージョンチェック（v2.1.80 未満の環境では effort が無視されるだけで害はない）

## Decisions

### D1: 推定ヒューリスティクスの設計

**決定**: 6段階の優先順位ルールで判定する。

| 優先順位 | 条件 | 判定 | confidence |
|---------|------|------|------------|
| 1 | `disable-model-invocation: true` | low | 0.90 |
| 2 | `allowed-tools` に Agent 含む | high | 0.90 |
| 3 | コンテンツ行数 < 80 | low | 0.75 |
| 4 | コンテンツ行数 >= 300 | high | 0.75 |
| 5 | パイプライン系キーワード >= 2 | high | 0.75 |
| 6 | デフォルト | medium | 0.75 |

**理由**: frontmatter フラグ（disable-model-invocation, allowed-tools）は明確な意図を示すため高 confidence。行数やキーワードは推定のためやや低い confidence。

### D2: 統合ポイント

**決定**: audit の `collect_issues()` に検出を追加し、remediation の `FIX_DISPATCH` でハンドラを登録する。

**代替案**: verification_catalog に追加 → verification_catalog はルール生成向けのパターンで、frontmatter 追加とは性質が異なるため不採用。

### D3: モジュール構成

**決定**: `scripts/lib/effort_detector.py` を新規作成し、検出と推定のロジックを集約する。

**理由**: audit.py / remediation.py にインラインで書くと責務が混在する。独立モジュールにすることで単体テストが容易。

## Risks / Trade-offs

- [推定精度] 行数やキーワードだけでは effort の最適値を決められないケースがある → confidence を付与し、ユーザーに最終判断を委ねる（proposable 分類）
- [CC バージョン非互換] v2.1.80 未満では effort frontmatter が無視される → 害はないため許容
