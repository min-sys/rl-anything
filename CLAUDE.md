# rl-anything Plugin

スキル/ルールの **自律進化パイプライン**、**修正フィードバックループ**、**遺伝的最適化** を提供する Claude Code Plugin。

## 3つの柱

| 柱 | スキル | 説明 |
|----|--------|------|
| 自律進化 | backfill, discover, prune, evolve, audit | Observe→Discover→Prune→Evolve のデータ駆動パイプライン |
| フィードバック | reflect | 修正パターン検出 → corrections.jsonl → CLAUDE.md/rules に反映 |
| 遺伝的最適化 | optimize, rl-loop, generate-fitness, evolve-fitness | LLM でバリエーション生成 → 適応度評価 → 進化 |
| ユーティリティ | feedback, update, version | フィードバック・更新・バージョン確認 |

## コンポーネント

| コンポーネント | 説明 |
|----------------|------|
| Observe hooks (7個) | LLM コストゼロで使用・エラー・修正フィードバック・ワークフローを自動記録 |
| `genetic-prompt-optimizer` | LLM でバリエーションを生成し、適応度関数で評価して進化 |
| `rl-loop-orchestrator` | ベースライン取得→バリエーション生成→評価→人間確認のループ統合 |
| `rl-scorer` エージェント | 技術品質 + ドメイン品質 + 構造品質の3軸で採点 |

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
```

## 適応度関数

組み込み: `default`（LLM汎用評価）、`skill_quality`（ルールベース構造品質）。
プロジェクト固有: `scripts/rl/fitness/{name}.py` に配置 → `--fitness {name}` で使用。
インターフェース: stdin でスキル内容を受け取り、0.0〜1.0 を stdout に出力。

詳細は [README.md](README.md#適応度関数) を参照。

## rl-scorer のドメイン自動判定

CLAUDE.md からドメイン（ゲーム/API/Bot/ドキュメント）を推定し評価軸を自動切替。
詳細は [README.md](README.md#rl-scorer-のドメイン自動判定) を参照。

## テスト

```bash
cd <PLUGIN_DIR>
python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v
```
