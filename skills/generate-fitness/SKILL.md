---
name: generate-fitness
effort: medium
description: |
  プロジェクト固有の fitness 関数を自動生成。CLAUDE.md・rules・skills を分析し、
  ドメイン特性に基づいた評価関数を scripts/rl/fitness/ に出力する。
  使用タイミング: (1) rl-anything をプロジェクトに導入した直後
  (2) プロジェクト固有の品質基準で --fitness を使いたい
  トリガーワード: generate-fitness, fitness生成, 評価関数生成
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

## Arguments
- `--name NAME`: 生成する fitness 関数名（省略時: ドメイン名を自動使用）
- `--dry-run`: 分析のみ実行（fitness 関数は生成しない）
- `--project-root DIR`: プロジェクトルート（デフォルト: カレントディレクトリ）
- `--ask`: ユーザーに品質基準を対話的に質問し、`.claude/fitness-criteria.md` に保存してから生成を実行

## 概要

2段階パイプラインでプロジェクト固有の fitness 関数を生成する:

```
[analyze_project.py] CLAUDE.md・rules・skills をルールベースで分析
    ↓ JSON（domain, keywords, criteria）
[Claude CLI] テンプレート + 分析結果から fitness 関数の Python コードを生成
    ↓
[scripts/rl/fitness/{name}.py] 既存の --fitness {name} でそのまま利用可能
```

## ワークフロー

### Step 0: ユーザー品質基準の収集（--ask 指定時のみ）

`--ask` が指定された場合、まずユーザーに品質基準を質問する。

1. `.claude/fitness-criteria.md` が既に存在する場合:
   - 既存の内容をユーザーに提示し、更新するか確認する
   - ユーザーが更新を選択した場合は次のステップへ
   - ユーザーが現状維持を選択した場合は Step 1 にスキップ

2. AskUserQuestion ツールでユーザーに質問:
   - 「このプロジェクトの品質基準は何ですか？以下の形式で記述してください:」
   - 例: `- ゲーマーがワクワクする表現かどうか (weight: 0.4)`

3. 回答を `.claude/fitness-criteria.md` に保存:
```bash
cat > .claude/fitness-criteria.md << 'EOF'
## 品質基準
{ユーザーの回答}
EOF
```

`--ask` なしでも `.claude/fitness-criteria.md` が存在すれば自動的に読み込まれる。

### Step 1: プロジェクト分析

analyze_project.py を実行して、プロジェクトの特性を JSON で取得する。

```bash
python3 <PLUGIN_DIR>/skills/generate-fitness/scripts/analyze_project.py \
  --project-root .
```

出力例:
```json
{
  "domain": "game",
  "keywords": ["narrative", "character", "dialogue", "quest"],
  "criteria": {
    "axes": [
      {"name": "narrative_consistency", "weight": 0.3, "description": "物語の一貫性"},
      {"name": "character_voice", "weight": 0.3, "description": "キャラクターの声の一貫性"},
      {"name": "instruction_clarity", "weight": 0.2, "description": "指示の明確さ"},
      {"name": "structure_quality", "weight": 0.2, "description": "構造の品質"}
    ],
    "anti_patterns": ["曖昧な指示", "矛盾する設定"]
  },
  "sources": ["CLAUDE.md", ".claude/rules/tone.md", ".claude/skills/narrative/SKILL.md"]
}
```

### Step 2: fitness 関数の生成

分析結果の JSON とテンプレートを Claude CLI に渡し、fitness 関数を生成する。

```bash
# 1. 分析結果を取得
ANALYSIS=$(python3 <PLUGIN_DIR>/skills/generate-fitness/scripts/analyze_project.py --project-root .)

# 2. ドメイン名を取得（--name 未指定の場合）
DOMAIN=$(echo "$ANALYSIS" | python3 -c "import sys,json; print(json.load(sys.stdin)['domain'])")

# 3. テンプレートを読み込み
TEMPLATE=$(cat <PLUGIN_DIR>/skills/generate-fitness/templates/fitness-template.py)

# 4. Claude CLI で生成
echo "以下の分析結果とテンプレートに基づいて、プロジェクト固有の fitness 関数を生成してください。

## 分析結果
$ANALYSIS

## テンプレート
\`\`\`python
$TEMPLATE
\`\`\`

テンプレートの evaluate() 関数内のロジックを、分析結果の criteria に基づいて実装してください。
- 各 axis の name, weight, description に従った評価ロジックを実装
- anti_patterns をペナルティとして反映
- stdin からスキル内容を受け取り、0.0〜1.0 のスコアを stdout に出力するインターフェースを維持
- Python コードのみ出力（説明不要）
- \`\`\`python と \`\`\` で囲んでください" | claude -p --model sonnet --output-format text > /tmp/fitness_generated.py

# 5. Python コードブロックを抽出して保存
python3 -c "
import re, sys
text = open('/tmp/fitness_generated.py').read()
m = re.search(r'\`\`\`python\s*\n(.*?)\`\`\`', text, re.DOTALL)
if m:
    print(m.group(1).strip())
else:
    print(text.strip())
" > scripts/rl/fitness/${DOMAIN}.py
```

### Step 3: 既存ファイルの処理

生成先に既存ファイルがある場合は `.backup` にリネームしてから上書きする。

```bash
TARGET="scripts/rl/fitness/${DOMAIN}.py"
if [ -f "$TARGET" ]; then
  mv "$TARGET" "${TARGET}.backup"
  echo "既存ファイルをバックアップ: ${TARGET}.backup"
fi
```

### Step 4: 出力先ディレクトリの作成

```bash
mkdir -p scripts/rl/fitness/
```

### Step 5: 動作確認

```bash
# 対象スキルを stdin に渡してスコアが返るか確認
cat .claude/skills/my-skill/SKILL.md | python3 scripts/rl/fitness/${DOMAIN}.py
# 0.0〜1.0 の数値が出力されれば OK

# optimize.py から利用
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target .claude/skills/my-skill/SKILL.md \
  --fitness ${DOMAIN} --dry-run
```

## 適応度関数のインターフェース

生成される関数は既存の `--fitness {name}` と完全互換:
- **入力**: stdin からスキル/ルールの内容（Markdown テキスト）
- **出力**: stdout に 0.0〜1.0 のスコア（浮動小数点数）
- **配置先**: プロジェクトの `scripts/rl/fitness/{name}.py`

## 依存

| 依存先 | 用途 |
|--------|------|
| analyze_project.py | プロジェクト分析（ルールベース、LLM 不使用） |
| Claude CLI (`claude -p`) | fitness 関数コード生成 |
| fitness-template.py | 生成のスケルトン |
