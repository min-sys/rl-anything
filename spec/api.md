# API / Interface Spec

> このファイルは SPEC.md から分離された詳細仕様です。
> 概要は [SPEC.md](../SPEC.md) を参照してください。

Last updated: 2026-04-22 (userConfig: cleanup_tmp_prefixes 追加)

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

組み込み8個: `default`, `skill_quality`, `coherence`, `telemetry`, `constitutional`（+ /cso security軸）, `chaos`, `environment`（動的重み）, `plugin`（プラグイン統合）。`config.py` / `principles.py` は supporting（閾値集約 / 原則抽出）

PJ固有: `scripts/rl/fitness/{name}.py` に配置 → `--fitness {name}`

## userConfig（manifest.userConfig 経由の環境変数）

`.claude-plugin/plugin.json::userConfig` で公開している設定キー。インストール時の UI または `CLAUDE_PLUGIN_OPTION_<key>` 環境変数で上書き可能。`scripts/lib/rl_common.py::load_user_config` がデフォルトとマージする。

| キー | 型 | default | 用途 |
|------|-----|---------|------|
| `auto_trigger` | boolean | true | evolve/audit 自動提案の有効化 |
| `evolve_interval_days` | number | 7 | evolve 提案の間隔（日） |
| `audit_interval_days` | number | 30 | audit 提案の間隔（日） |
| `min_sessions` | number | 10 | evolve 提案の最小セッション数 |
| `cooldown_hours` | number | 24 | trigger 評価 cooldown |
| `language` | string | `ja` | trigger メッセージ言語（ja/en） |
| `growth_display` | boolean | true | セッション開始時の Growth phase 表示 |
| `cleanup_tmp_prefixes` | string | `rl-anything-` | cleanup 対象の /tmp prefix（カンマ区切り）。`scan_tmp_dirs` の `_DEFAULT_TMP_EXCLUDE_PATTERNS` 安全ネットは常時有効（ADR-021）|
