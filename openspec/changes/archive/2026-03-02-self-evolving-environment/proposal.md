## Why

rl-anything は現在スキルの最適化（`/optimize`, `/rl-loop`）のみを提供している。
しかし Claude Code 環境（skills / rules / memory / CLAUDE.md）は最適化だけでは不十分で、
「発見 → 生成 → 最適化 → 淘汰」の全ライフサイクルを管理しなければ環境は成長しない。
使えば使うほど環境が賢くなる自律進化エンジンへの拡張が必要。

## What Changes

- **環境観測基盤の新設**: async hooks でスキル使用・エラー・セッション情報を自動記録。LLM 呼び出しなし、コストゼロ
- **最適化テレメトリの追加**: 遺伝的操作の戦略タグ（elite/mutation/crossover）、CoT reason、rejection_reason を記録
- **フィードバックコマンドの新設**: `/rl-anything:feedback` でユーザーフィードバックを GitHub Issue として送信
- **健康診断の新設**: `/rl-anything:audit` で skills/rules/memory の棚卸し + クロスラン集計レポート
- **淘汰機能の新設**: `/rl-anything:prune` で未使用・重複・dead glob のアーティファクトをアーカイブ
- **パターン発見の新設**: `/rl-anything:discover` で繰り返しパターンからスキル/ルール候補を自動生成
- **統合コマンドの新設**: `/rl-anything:evolve` で全フェーズをワンコマンド実行
- **評価関数の自己成長**: accept/reject 相関・rejection_reason 分析から fitness function を自動改善
- **肥大化制御の自動化**: サイズバリデーション、Usage Registry によるスコープ最適化、Plugin Bundling 提案
- **GitHub Issue テンプレートの追加**: フィードバック用 YAML Issue Forms

## Capabilities

### New Capabilities

- `observe`: 環境観測 hooks + 最適化テレメトリ + Usage Registry（async、LLM 呼び出しなし）
- `feedback`: ユーザーフィードバック収集 → GitHub Issue 送信（プライバシー保護付き）
- `audit-report`: skills/rules/memory の棚卸し + クロスラン集計 + 1画面レポート
- `prune`: 未使用・重複・dead glob の検出 → アーカイブ提案 → 人間承認 → 復元可能
- `discover`: 観測データからスキル/ルール候補を発見 → 構造的制約バリデーション付き生成
- `evolve-orchestrator`: Observe → Discover → Optimize → Prune → Report の全フェーズ統合
- `fitness-evolution`: 評価関数の score-acceptance 相関追跡 + rejection_reason 分析 + 自動改善提案
- `bloat-control`: コードによる構造的制約 + Usage Registry + Scope Advisor + Plugin Bundling 提案

### Modified Capabilities

- `genetic-prompt-optimizer`: Individual クラスに strategy / cot_reasons フィールド追加。history.jsonl に rejection_reason / human_accepted 追加

## Impact

- **新規ファイル**: hooks/（4ファイル）、skills/feedback/、skills/audit/、skills/prune/、skills/discover/、skills/evolve/、skills/evolve-fitness/、scripts/aggregate-runs.py、.github/ISSUE_TEMPLATE/（2ファイル）
- **既存変更**: skills/genetic-prompt-optimizer/（Individual クラス拡張）、history.jsonl フォーマット拡張
- **データストレージ**: ~/.claude/rl-anything/（usage.jsonl, errors.jsonl, sessions.jsonl, usage-registry.jsonl）
- **依存関係**: gh CLI（フィードバック送信用、オプション）。新規外部依存なし
- **全変更は人間承認が必要**（自動適用なし）
