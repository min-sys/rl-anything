# /rl-anything:audit — 環境の健康診断

全 skills / rules / memory の棚卸し + 行数チェック + 使用状況集計 + Scope Advisory を含む1画面レポートを出力する。

## Usage

```
/rl-anything:audit [project-dir]
```

## 実行手順

### Step 1: Audit スクリプト実行

```bash
python3 <PLUGIN_DIR>/skills/audit/scripts/audit.py "$(pwd)"
```

出力されるレポートをユーザーに表示する。

### Step 2: クロスラン集計（オプション）

optimize / rl-loop の実行履歴がある場合:

```bash
python3 <PLUGIN_DIR>/skills/audit/scripts/aggregate_runs.py
```

### Step 3: 意味的類似度の検出（オプション）

行数超過や重複候補が検出された場合、改善アクションを提案する:
- 行数超過 → 分割を提案
- 重複候補 → 統合を提案
- Scope Advisory → スコープ最適化を提案

## allowed-tools

Read, Bash, Glob, Grep

## Tags

audit, health-check, report
