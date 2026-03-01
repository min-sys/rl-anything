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

```bash
# 1. 構造テスト（LLM 呼び出しなし）
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target .claude/skills/my-skill/SKILL.md --dry-run

# 2. 最適化実行（3世代 x 集団3）
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target .claude/skills/my-skill/SKILL.md --generations 3 --population 3

# 3. 自律進化ループ
python3 <PLUGIN_DIR>/skills/rl-loop-orchestrator/scripts/run-loop.py \
  --target .claude/skills/my-skill/SKILL.md --dry-run

# 4. バックアップから復元
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target .claude/skills/my-skill/SKILL.md --restore
```

## 適応度関数

### 組み込み関数

| 関数 | 説明 |
|------|------|
| `default` | LLM による汎用評価 |
| `skill_quality` | ルールベースの汎用品質評価（Plugin内蔵） |

### プロジェクト固有の適応度関数

プロジェクトの `scripts/rl/fitness/{name}.py` に配置すると、`--fitness {name}` で使用可能。

**インターフェース**: stdin からスキル内容を受け取り、0.0〜1.0 のスコアを stdout に出力。

## rl-scorer のドメイン自動判定

rl-scorer エージェントはプロジェクトの CLAUDE.md を読んでドメインを推定し、
評価軸を自動切替します:

- **ゲーム** → 没入感・面白さ・バランス・具体性
- **API/バックエンド** → 正確性・堅牢性・保守性・セキュリティ
- **Bot/対話** → パーソナリティ適合・有用性・トーン一貫性
- **ドキュメント** → 正確性・可読性・実行可能性・完全性

## テスト

```bash
cd <PLUGIN_DIR>
python3 -m pytest skills/ -v
```
