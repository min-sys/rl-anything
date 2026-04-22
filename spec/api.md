# API / Interface Spec

> このファイルは SPEC.md から分離された詳細仕様です。
> 概要は [SPEC.md](../SPEC.md) を参照してください。

Last updated: 2026-04-22

## スキルコマンド

| コマンド | 説明 | effort |
|----------|------|--------|
| `/rl-anything:evolve` | 3ステージ自律進化パイプライン（日次運用） | high |
| `/rl-anything:discover` | パターン検出 + スキル/ルール候補生成 | medium |
| `/rl-anything:reflect` | corrections → CLAUDE.md/rules 反映 | medium |
| `/rl-anything:audit` | 環境健康診断レポート | medium |
| `/rl-anything:optimize <skill>` | 特定スキルの直接パッチ最適化 | high |
| `/rl-anything:rl-loop` | 自律進化ループオーケストレーター | high |
| `/rl-anything:agent-brushup` | エージェント品質診断 | medium |
| `/rl-anything:evolve-skill <skill>` | 特定スキルに自己進化パターン組み込み | medium |
| `/rl-anything:generate-fitness` | PJ固有 fitness 関数自動生成 | medium |
| `/rl-anything:evolve-fitness` | 評価関数キャリブレーション | medium |
| `/rl-anything:second-opinion` | Claude Agent セカンドオピニオン（startup/builder/general） | low |
| `/rl-anything:handover` | セッション作業状態の構造化ノート書き出し | low |
| `/rl-anything:implement` | plan artifact → 構造化実装（Standard/Parallel）→ テレメトリ記録 | high |
| `/rl-anything:version` | バージョン・ステータス表示 | low |
| `/rl-anything:spec-keeper` | SPEC.md + ADR 管理（init/update/adr/status） | medium |
| `/rl-anything:philosophy-review` | セッション履歴を Judge LLM で評価し哲学原則違反を corrections.jsonl 注入 | medium |
| `/rl-anything:cleanup` | PR マージ・デプロイ後の後片付け（マージ済みブランチ / remote refs prune / 一時 worktree / 一時ディレクトリ / close 候補 Issue / PR Test plan 残件）を候補提示→個別承認→実行 | low |
| `/rl-anything:feedback` | フィードバック送信 | low |

## 適応度関数

組み込み9個: `default`, `skill_quality`, `coherence`, `telemetry`, `constitutional`（+ /cso security軸）, `chaos`, `environment`（動的重み）, `plugin`（プラグイン統合）, `principles`。`config.py` で閾値集約

PJ固有: `scripts/rl/fitness/{name}.py` に配置 → `--fitness {name}`
