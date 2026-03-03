# rl-anything Plugin

スキル/ルールの **自律進化パイプライン** と **遺伝的最適化** を提供する Claude Code Plugin。

## 2つの柱

| 柱 | スキル | 説明 |
|----|--------|------|
| 自律進化 | backfill, discover, prune, evolve, audit | Observe→Discover→Prune→Evolve のデータ駆動パイプライン |
| 遺伝的最適化 | optimize, rl-loop, generate-fitness, evolve-fitness | LLM でバリエーション生成 → 適応度評価 → 進化 |
| ユーティリティ | feedback, update, version | フィードバック・更新・バージョン確認 |

## コンポーネント

| コンポーネント | 説明 |
|----------------|------|
| Observe hooks (6個) | LLM コストゼロで使用・エラー・ワークフローを自動記録 |
| `genetic-prompt-optimizer` | LLM でバリエーションを生成し、適応度関数で評価して進化 |
| `rl-loop-orchestrator` | ベースライン取得→バリエーション生成→評価→人間確認のループ統合 |
| `rl-scorer` エージェント | 技術品質 + ドメイン品質 + 構造品質の3軸で採点 |

## クイックスタート

```
# 1. 構造テスト（LLM 呼び出しなし）
/rl-anything:optimize my-skill --dry-run

# 2. 最適化実行（3世代 x 集団3）
/rl-anything:optimize my-skill --generations 3 --population 3

# 3. 自律進化パイプライン（日次運用）
/rl-anything:evolve --dry-run

# 4. バックアップから復元
/rl-anything:optimize my-skill --restore
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
python3 -m pytest skills/ -v
```
