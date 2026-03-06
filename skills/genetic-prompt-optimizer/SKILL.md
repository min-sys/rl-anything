---
name: optimize
description: スキル/ルールの遺伝的最適化。/optimize で呼び出し。LLM でバリエーションを生成し、適応度関数で評価して進化させる。
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# 遺伝的プロンプト最適化

スキル/ルール（SKILL.md）を遺伝的アルゴリズムで自動最適化する。

## 実行手順

ユーザーが `/optimize` を呼び出したら、以下の手順で実行する。

### 1. 引数をパースする

ユーザーの入力から以下の引数を抽出する。指定がなければデフォルト値を使用。

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `TARGET` | 最適化対象のスキルファイルパス（スキル名 or ファイルパス） | 必須 |
| `--generations N` | 世代数 | 3 |
| `--population N` | 集団サイズ | 3 |
| `--fitness FUNC` | 適応度関数名 | default |
| `--dry-run` | 構造テスト（LLM 評価なし） | false |
| `--restore` | バックアップから復元 | false |

TARGET がスキル名（例: `my-skill`）の場合、`.claude/skills/{name}/SKILL.md` に解決する。
ファイルパスが直接指定された場合はそのまま使用する。

### スコープ判定

ターゲット選択時、各候補に scope ラベルを表示する:
- `[global]` — `~/.claude/skills/` 配下のスキル。汎用評価モードで最適化（プロジェクト CLAUDE.md を除外）
- `[project]` — プロジェクト内のスキル。プロジェクトコンテキストを含めて最適化

### 2. スクリプトを実行する

```bash
python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py \
  --target <TARGET> [OPTIONS]
```

### 3. 結果をユーザーに報告する

- 実行が成功したら、最適化結果のサマリ（世代数・最良スコア・主な変更点）を表示する
- `--dry-run` の場合は構造チェック結果を表示する
- `--restore` の場合は復元完了を報告する
- エラーが発生した場合はエラー内容と対処法を提示する

### 4. accept/reject を確認する（`--dry-run`・`--restore` 以外）

最適化が正常に完了した場合（`--dry-run` および `--restore` を除く）、結果サマリを表示してから AskUserQuestion で採否を確認する。

1. スクリプト出力のサマリ（スコア推移テーブル、CoT 評価内訳、変更サマリ）をユーザーに表示する
2. `score_delta == 0` の場合は「改善なし: ベースラインからの変更はありません」と明示する
3. AskUserQuestion で「この最適化結果を採用しますか？」と確認する（options: 「Accept（結果を採用）」「Reject（却下して理由を記録）」）
2. **Accept の場合**: 以下を実行して `history.jsonl` に `human_accepted: true` を記録する
   ```bash
   python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py --target <TARGET> --accept
   ```
3. **Reject の場合**: AskUserQuestion（open-ended）で却下理由を確認し、以下を実行して `history.jsonl` に `human_accepted: false` と `rejection_reason` を記録する
   ```bash
   python3 <PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/optimize.py --target <TARGET> --reject --reason "<理由>"
   ```

## 使用例

```
/optimize my-skill                          # 基本実行（3世代 x 集団3）
/optimize my-skill --dry-run                # 構造テスト
/optimize my-skill --fitness skill_quality  # カスタム適応度関数
/optimize my-skill --generations 5          # 5世代実行
/optimize my-skill --restore               # バックアップから復元
```

## 適応度関数

カスタム適応度関数の検索順序:
1. プロジェクトの `scripts/rl/fitness/{name}.py` — プロジェクト固有の評価
2. Plugin 内の `scripts/fitness/{name}.py` — 汎用評価

| 関数 | 説明 |
|------|------|
| `default` | LLM による汎用評価（明確性・完全性・構造・実用性） |
| `skill_quality` | ルールベースの汎用スキル品質評価 |

## 出力

世代ごとの結果は `<PLUGIN_DIR>/skills/genetic-prompt-optimizer/scripts/generations/{run_id}/` に保存。
