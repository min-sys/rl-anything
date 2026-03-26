# rl-anything Plugin

スキル/ルールの **自律進化パイプライン**、**修正フィードバックループ**、**直接パッチ最適化** を提供する Claude Code Plugin。

## 3つの柱

| 柱 | スキル | 説明 |
|----|--------|------|
| 自律進化 | evolve, discover, reorganize, prune, audit | Observe → Diagnose → Compile → Housekeeping → Report の3ステージパイプライン |
| フィードバック | reflect | 修正パターン検出 → corrections.jsonl → CLAUDE.md/rules に反映 |
| 直接パッチ最適化 | optimize, rl-loop, generate-fitness, evolve-fitness | corrections/context → LLM 1パスパッチ → regression gate（`scripts/lib/regression_gate.py` に共通化） |
| エージェント管理 | agent-brushup | エージェント定義の品質診断・改善提案・新規作成・削除候補 |
| セカンドオピニオン | second-opinion | Claude Agent による独立した cold-read セカンドオピニオン（codex 代替） |
| 仕様管理 | spec-keeper | SPEC.md + ADR の管理、Progressive Disclosure L1/L2 自動昇格 |
| ユーティリティ | feedback, update, version, backfill | フィードバック・更新・バージョン確認・初期セットアップ |

## コンポーネント

| コンポーネント | 説明 |
|----------------|------|
| Observe hooks (11個) | LLM コストゼロで使用・エラー・修正フィードバック・ワークフロー・ファイル変更を自動記録 |
| Auto Trigger | セッション終了・corrections 蓄積・ファイル変更時に evolve/audit 実行を自動提案（`trigger_engine.py`） |
| `userConfig` | CC v2.1.83 manifest.userConfig で trigger 閾値（auto_trigger/interval/cooldown 等6項目）をプラグイン有効化時に設定可能 |
| `genetic-prompt-optimizer` | corrections/context ベースの LLM 1パス直接パッチで最適化 |
| `rl-loop-orchestrator` | ベースライン取得→バリエーション生成→評価→人間確認のループ統合 |
| `rl-scorer` エージェント | オーケストレーター(haiku) + 3サブエージェント並列(tech/struct=haiku, domain=sonnet)で3軸採点 |
| `skill-triage` | テレメトリ+trigger evalで CREATE/UPDATE/SPLIT/MERGE/OK の5択判定（`scripts/lib/skill_triage.py`） |
| `trigger-eval-generator` | sessions.jsonl+usage.jsonl → skill-creator互換 evals.json 自動生成（`scripts/lib/trigger_eval_generator.py`） |
| `evolve-skill` | 特定スキルに自己進化パターン（Pre-flight / pitfalls.md）をピンポイント組み込み（`assess_single_skill` + `apply_evolve_proposal`） |
| `agent-brushup` | エージェント定義の品質診断・改善提案・upstream監視（`scripts/lib/agent_quality.py`） |
| `critical-instruction-compliance` | スキル指示の遵守保証サイクル — critical行抽出+calm/directリフレーズ+違反検出+pitfall自動学習（`scripts/lib/critical_instruction_extractor.py`） |
| `second-opinion` エージェント | cold-read セカンドオピニオン（startup/builder/general 3モード）。codex 不要で Agent ツールのみで動作 |
| `growth-level` | env_score (0.0-1.0) → Lv.1-10 + 日英称号マッピング。audit がキャッシュに保存、greeting で表示（`scripts/lib/growth_level.py`） |

## クイックスタート

```
# 日次運用（全フェーズ一括）
/rl-anything:evolve

# 修正フィードバックの反映
/rl-anything:reflect

# 特定スキルの最適化
/rl-anything:optimize my-skill

# 環境の健康診断
/rl-anything:audit

# エージェント品質診断
/rl-anything:agent-brushup

# セカンドオピニオン（codex代替）
/rl-anything:second-opinion

# SPEC.md の初期化・更新
/rl-anything:spec-keeper init
/rl-anything:spec-keeper update
```

## 適応度関数

組み込み: `default`（LLM汎用評価）、`skill_quality`（ルールベース構造品質）、`coherence`（構造的整合性4軸）、`telemetry`（テレメトリ3軸）、`constitutional`（原則ベースLLM Judge評価 + /cso security軸）、`chaos`（仮想除去ロバストネス）、`environment`（coherence+telemetry+constitutional+skill_quality 動的重み統合、`config.py` で閾値集約）。
プロジェクト固有: `scripts/rl/fitness/{name}.py` に配置 → `--fitness {name}` で使用。
環境スコア: `audit --coherence-score --telemetry-score --constitutional-score` で構造品質+行動実績+原則遵守の統合スコアを表示。

詳細は [README.md](README.md#適応度関数) を参照。

## rl-scorer のドメイン自動判定

CLAUDE.md からドメイン（ゲーム/API/Bot/ドキュメント）を推定し評価軸を自動切替。
詳細は [README.md](README.md#rl-scorer-のドメイン自動判定) を参照。

## Superpowers 共存

Superpowers プラグインがインストールされている場合、メタ操作時（evolve/audit/reflect/optimize/discover）は Superpowers の TDD/SDD/debugging スキルを発火させない。開発タスク時はフル活用する。

## Compaction Instructions

コンテキスト圧縮時、以下の情報をサマリーに必ず含めること:

1. **完了済みタスクと未完了タスクの区別** — 完了タスクを再実行しないこと
2. **呼び出されたスキルの実行結果** — 完了/未完了/エラーの状態
3. **変更したファイルの一覧** — パスと変更内容の要約
4. **ユーザーの最後の指示** — 次に何をすべきかの文脈

## テスト

```bash
cd <PLUGIN_DIR>
python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v

# プラグイン定義の整合性チェック
claude plugin validate
```

## Specification
- 現在の仕様全体像: [SPEC.md](SPEC.md)
- 詳細仕様: [spec/](spec/)
- 設計判断の記録: [docs/decisions/](docs/decisions/)
