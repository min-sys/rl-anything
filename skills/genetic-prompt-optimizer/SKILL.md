---
name: genetic-prompt-optimizer
description: スキル/ルールの遺伝的最適化。/optimize で呼び出し。LLM でバリエーションを生成し、適応度関数で評価して進化させる。
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# 遺伝的プロンプト最適化

Claude Code のスキル/ルール（SKILL.md）を遺伝的アルゴリズムで最適化するフレームワーク。

## 使い方

```bash
# 基本実行（3世代 x 集団3）
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target .claude/skills/my-skill/SKILL.md \
  --generations 3 --population 3

# 構造テスト（LLM 呼び出しなし）
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target .claude/skills/my-skill/SKILL.md --dry-run

# カスタム適応度関数を使用
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target .claude/skills/my-skill/SKILL.md \
  --fitness skill_quality

# バックアップから復元
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target .claude/skills/my-skill/SKILL.md --restore
```

`<PLUGIN_DIR>` は Plugin のインストール先パスに置き換えてください。

## 引数

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--target PATH` | 最適化対象のスキルファイルパス | 必須 |
| `--generations N` | 世代数 | 3 |
| `--population N` | 集団サイズ | 3 |
| `--fitness FUNC` | 適応度関数名 | default |
| `--dry-run` | 構造テスト（LLM 評価なし） | false |
| `--restore` | バックアップから元のスキルを復元 | false |

## ワークフロー

1. 対象スキルを読み込み、バックアップ作成（`.md.backup`）
2. LLM（claude CLI）でバリエーション生成（突然変異 + 交叉）
3. 各バリエーションを適応度関数で評価
4. エリート選択 + 突然変異/交叉で次世代生成
5. 最良のバリエーションを保存、結果をレポート

## 適応度関数

カスタム適応度関数の検索順序:
1. プロジェクトの `scripts/rl/fitness/{name}.py` — プロジェクト固有の評価
2. Plugin 内の `scripts/fitness/{name}.py` — 汎用評価

stdin からスキル内容を受け取り、0.0〜1.0 のスコアを stdout に出力。

| 関数 | 場所 | 説明 |
|------|------|------|
| `default` | 組み込み | LLM による汎用評価（明確性・完全性・構造・実用性） |
| `skill_quality` | Plugin | ルールベースの汎用スキル品質評価 |

## 出力

世代ごとの結果は `<PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/generations/{run_id}/` に保存。

```
generations/
  20260301_143000/
    gen_0/
      gen0_143000_000001.json
      gen0_143000_000002.json
    gen_1/
      ...
    result.json
```

## テスト

```bash
python3 -m pytest <PLUGIN_DIR>/skills/genetic-prompt-optimizer/tests/test_optimizer.py -v
```
