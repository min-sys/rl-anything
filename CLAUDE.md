# rl-anything Plugin

スキル/ルールの遺伝的最適化と自律進化ループを提供する Claude Code Plugin。

## 概要

Claude Code のスキルファイル（SKILL.md）やルールファイル（.claude/rules/*.md）を、
遺伝的アルゴリズムで自動改善するパイプライン。

## コンポーネント

| コンポーネント | 説明 |
|----------------|------|
| `genetic-prompt-optimizer` | LLM でバリエーションを生成し、適応度関数で評価して進化 |
| `rl-loop-orchestrator` | ベースライン取得→バリエーション生成→評価→人間確認のループ統合 |
| `rl-scorer` エージェント | 技術品質 + ドメイン品質 + 構造品質の3軸で採点 |

## クイックスタート

```
# 1. 構造テスト（LLM 呼び出しなし）
/optimize my-skill --dry-run

# 2. 最適化実行（3世代 x 集団3）
/optimize my-skill --generations 3 --population 3

# 3. 自律進化ループ
/rl-loop my-skill --dry-run

# 4. バックアップから復元
/optimize my-skill --restore
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
