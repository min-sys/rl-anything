---
name: rl-loop
description: |
  自律進化ループオーケストレーター。3役分担（実装者・採点者・進化者）で
  スキル/ルールを自律的に改善するループを回す。
  トリガーワード: rl-loop, 自律進化, 自律ループ, evolution loop
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Agent
---

# 自律進化ループ

ベースライン取得 → 直接パッチ → 評価 → 人間確認のサイクルを回し、スキル/ルールを自律的に改善する。

## 実行手順

ユーザーが `/rl-loop` を呼び出したら、以下の手順で実行する。

### 1. 引数をパースする

ユーザーの入力から以下の引数を抽出する。指定がなければデフォルト値を使用。

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `TARGET` | 改善対象のスキルファイルパス（スキル名 or ファイルパス） | 必須 |
| `--loops N` | ループ回数 | 1 |
| `--auto` | 人間確認ステップをスキップ | false |
| `--dry-run` | 構造テスト（実際の変更は行わない） | false |
| `--output-dir DIR` | 出力ディレクトリ | `.rl-loop/` |
| `--evolve` | 自己進化パターン組み込みを有効化（Step 5.5） | false |

TARGET がスキル名（例: `my-skill`）の場合、`.claude/skills/{name}/SKILL.md` に解決する。
ファイルパスが直接指定された場合はそのまま使用する。

### 2. スクリプトを実行する

```bash
python3 <PLUGIN_DIR>/skills/rl-loop-orchestrator/scripts/run-loop.py \
  --target <TARGET> [OPTIONS]
```

### 3. 結果をユーザーに報告する

- ベースラインスコアと最終スコアの比較を表示する
- 最高スコアのバリエーションの差分を提示する
- `--auto` でない場合、ユーザーに承認/却下を確認する
- エラーが発生した場合はエラー内容と対処法を提示する

## 使用例

```
/rl-loop my-skill                    # 1ループ実行（人間確認あり）
/rl-loop my-skill --dry-run          # 構造テスト
/rl-loop my-skill --loops 3          # 3ループ実行
/rl-loop my-skill --auto             # 人間確認スキップ
/rl-loop my-skill --evolve           # 最適化 + 自己進化パターン組み込み
/rl-loop my-skill --evolve --dry-run # 判定結果のみ表示
```

## ループの流れ

```
[Step 1] ベースライン取得: 現在のスキルを rl-scorer で採点
    ↓
[Step 2] 直接パッチ: genetic-prompt-optimizer で corrections/context ベースの LLM 1パスパッチを生成
    ↓
[Step 3] 評価: 各バリエーションを rl-scorer で採点、ベースラインと比較
    ↓
[Step 4] 選択と人間確認: 最高スコアのバリエーションを提示 → 承認/却下
    ↓
[Step 5] 記録: 結果を出力ディレクトリに保存
    ↓
[Step 5.5] 自己進化（--evolve 時のみ）: 未対応スキルに自己進化パターン組み込みを提案
    ↓
(次ループへ)
```

## 採点エージェント

rl-scorer エージェント（`agents/rl-scorer.md`）が統合スコアを算出する。

スコア構成:
- **技術品質スコア** (40%): 明確性・完全性・一貫性・エッジケース・テスト可能性
- **ドメイン品質スコア** (40%): CLAUDE.md からドメインを推定し、評価軸を自動選択
- **構造スコア** (20%): スキルファイルの構造的品質

## 出力先

```
.rl-loop/                         # デフォルト（--output-dir で変更可）
├── {run_id}/
│   ├── baseline.json      # ベースラインスコア
│   ├── variants/           # 各バリエーション
│   ├── scores.json         # 各バリエーションのスコア
│   └── result.json         # 最終結果
└── history.jsonl           # 全ループの履歴
```

## 注意事項

- 最初のループは必ず人間確認ステップを含める（`--auto` は使わない）
- スコアが下降した場合は自動的にバックアップから復元
- 1ループの API コスト目安: sonnet x 1回（直接パッチ）+ haiku x 1回（評価）
