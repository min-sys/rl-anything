# ADR-003: Direct Patch over Genetic Algorithm

Date: 2026-03-07
Status: Accepted

## Context

genetic-prompt-optimizer は世代ループ（mutate -> evaluate -> select）で 6~15+ LLM コールを消費していたが、bench 結果では long_skill の score 改善がほぼゼロだった。corrections.jsonl には「何がどう悪いか」のテキスト情報が既にあるにもかかわらず、fitness スカラー（0.0-1.0）に圧縮して遺伝的に探索し直すのは情報損失かつコスト過大であった。

## Decision

- **遺伝的アルゴリズムの世代ループを廃止し、DirectPatchOptimizer に置換**: corrections 有無で分岐する2モード（`error_guided` / `llm_improve`）を統合パイプラインとして実装。LLM コールを 1~2 回に削減
- **コンテキスト収集の最大化**: corrections.jsonl、workflow_stats.json、audit collect_issues()、pitfalls.md を入力とし、1パスの質を上げる。corrections の取得件数上限は `MAX_CORRECTIONS_PER_PATCH = 10`
- **6モジュールを削除**: strategy_router / granularity / bandit_selector / early_stopping / model_cascade / parallel は世代ループ専用のため不要
- **history.jsonl フォーマット拡張**: `strategy` フィールドと `corrections_used` フィールドを追加
- **CLI オプション整理**: `--generations`, `--population`, `--budget`, `--cascade`, `--parallel` を廃止。`--mode error_guided|llm_improve|auto` を新設（デフォルト auto）

## Alternatives Considered

- **corrections モードのみ実装し、なしの場合は既存 GA を残す**: corrections なしのケースでも GA のコスト問題は解消されないため却下
- **sunk cost として既存モジュールを維持**: bench で効果が証明されなかったコードを維持するコストのほうが高い

リスク軽減として、LLM 1パスの質が低い場合は `_regression_gate()` で構造的品質ガード + 人間の accept/reject で最終判断する。GA 時代も改善率は低かったため実質リスク増なし。corrections 大量時はプロンプト肥大を防ぐため直近 N 件に制限し関連度でソートする。

## Consequences

**良い影響:**
- LLM コールが 6~15+ から 1~2 回に大幅削減され、コスト効率が劇的に改善
- corrections の豊富なテキスト情報を直接活用することで、改善精度が向上
- 6モジュール削除によりコードベースが大幅に簡素化され、保守性が向上
- rl-loop-orchestrator との CLI 互換性を維持し、ユーザーへの影響を最小化

**悪い影響:**
- BREAKING CHANGE: GA ベースの最適化は完全に廃止され、過去の GA パラメータは利用不可
- 1パスのみのため、多様なバリエーションの探索はできなくなった
