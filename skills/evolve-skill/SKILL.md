---
name: evolve-skill
description: |
  特定スキルに自己進化パターン（Pre-flight / Failure-triggered Learning / pitfalls.md）を
  組み込む独立コマンド。適性判定→テンプレート組み込み→人間確認を1コマンドで実行。
  トリガーワード: evolve-skill, スキル進化, 自己進化パターン, self-evolve
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# スキル自己進化パターン組み込み

特定スキルに自己進化パターン（Pre-flight Check / Failure-triggered Learning / pitfalls.md）を組み込む。

## 実行手順

ユーザーが `/rl-anything:evolve-skill` を呼び出したら、以下の手順で実行する。

### 1. 対象スキルを解決する

引数からスキルディレクトリを解決する:

- **スキル名** (例: `my-skill`): `.claude/skills/{name}/` に解決
- **ファイルパス** (例: `.claude/skills/my-skill/SKILL.md`): 親ディレクトリをスキルディレクトリとして使用
- **引数なし**: 対象スキルの指定を求めるメッセージを表示して終了

`--dry-run` が指定されている場合はファイル変更を行わないモードとして記憶する。

### 2. 適性判定を実行する

```python
import sys
from pathlib import Path

plugin_root = Path("<PLUGIN_DIR>")
sys.path.insert(0, str(plugin_root / "scripts" / "lib"))
from skill_evolve import assess_single_skill

result = assess_single_skill(skill_name, skill_dir)
```

### 3. 判定結果を表示する

5軸スコアと適性レベルを表示する:

```
## 自己進化適性判定: {skill_name}

| 軸 | スコア |
|----|--------|
| 実行頻度 | {frequency}/3 |
| 失敗多様性 | {diversity}/3 |
| 出力評価可能性 | {evaluability}/3 |
| 外部依存度 | {external_dependency}/3 |
| 判断複雑さ | {judgment_complexity}/3 |

合計: {total_score} / 適性: {suitability}
推奨: {recommendation}
```

アンチパターンがある場合はその詳細も表示する。

`workflow_checkpoints` が存在する場合（ワークフロースキル判定 True）、チェックポイントギャップを表示する:

```
### Workflow Checkpoint Gaps
| Category | Evidence | Confidence |
|----------|----------|------------|
| infra_deploy | 3 | 0.75 |
```

ギャップがない場合は「チェックポイントギャップなし」と表示する。

### 4. 適性に応じた処理

- **already_evolved**: 「既に自己進化対応済みです」と表示して終了
- **low / rejected**: 「変換非推奨」と表示して終了
- **medium / high**: 次のステップ（承認フロー）に進む
- **--dry-run**: 判定結果のみ表示し、ファイル変更を行わず終了

### 5. パターン組み込みの承認と実行

```python
from skill_evolve import evolve_skill_proposal, apply_evolve_proposal

proposal = evolve_skill_proposal(skill_name, skill_dir)
# proposal の内容（追加セクション概要）をユーザーに表示

# ユーザーに承認を求める（AskUserQuestion）
# 承認された場合:
result = apply_evolve_proposal(proposal)
```

承認された場合のみ実行し、結果サマリーを表示:
- 追加されたセクション一覧
- `references/pitfalls.md` の作成
- バックアップパス（`.md.pre-evolve-backup`）

却下された場合はファイルに変更を加えず終了。

## 使用例

```
/rl-anything:evolve-skill my-skill                # スキル名指定
/rl-anything:evolve-skill .claude/skills/my-skill/SKILL.md  # パス指定
/rl-anything:evolve-skill my-skill --dry-run       # 判定結果のみ
```
