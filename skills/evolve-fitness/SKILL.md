---
name: evolve-fitness
effort: medium
description: |
  Analyze accept/reject data to find score-acceptance correlation issues and propose
  fitness function improvements. All changes require human approval.
  Trigger: evolve-fitness, 評価関数改善, fitness improvement, calibration, キャリブレーション
---

# /rl-anything:evolve-fitness — 評価関数の改善提案

accept/reject データから score-acceptance 相関を分析し、
評価関数の改善を提案する。全変更は人間承認が必須（MUST）。

## Usage

```
/rl-anything:evolve-fitness
```

## 前提

accept/reject が30件以上蓄積されていること（SHALL）。

## 実行手順

### Step 1: データ分析

```bash
python3 <PLUGIN_DIR>/skills/evolve-fitness/scripts/fitness_evolution.py
```

### Step 2: データ不足時

30件未満の場合:
- 「データ不足」メッセージを表示（MUST）
- 必要なデータ量を案内
- 現在の件数と残り必要件数を表示

### Step 3: レポート表示

十分なデータがある場合、以下を表示:
1. **score-acceptance 相関**: 相関 < 0.50 なら「再キャリブレーション推奨」警告（MUST）
2. **欠落評価軸提案**: 同じ rejection_reason が3回以上なら新軸追加を提案（SHALL）
3. **adversarial probe 結果**: ゲーミング脆弱性の検出

### Step 4: 改善提案と承認フロー（MUST）

提案を提示し、AskUserQuestion でユーザーの承認を得る。
評価関数の自動変更を行ってはならない（MUST NOT）。

承認されたもののみ適用:
- 評価軸の重み調整
- 新しい評価軸の追加
- anti-pattern の追加

## allowed-tools

Read, Bash, AskUserQuestion, Write

## Tags

fitness, evolution, calibration
