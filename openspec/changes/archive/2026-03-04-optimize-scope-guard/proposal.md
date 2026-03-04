## Why

`/optimize` で global スキル（全プロジェクト共通）を最適化する際、現在のプロジェクト文脈（CLAUDE.md 等）が評価に混入し、特定プロジェクトに偏った最適化が行われるリスクがある。global スキルは汎用的な評価基準で最適化すべき。

## What Changes

- optimize 実行時にターゲットスキルの scope（global / project）を自動判定する
- global スキルの場合、プロジェクト固有コンテキスト（CLAUDE.md 等）を評価から除外し、汎用的な評価基準のみで最適化する
- ターゲット選択 UI に scope ラベル（`[global]` / `[project]`）を表示する
- global スキル選択時に「汎用評価モードで最適化します」旨を通知する

## Capabilities

### New Capabilities

- `scope-detection`: スキルのファイルパスから scope（global / project）を判定するロジック
- `generic-evaluation-mode`: global スキル向けにプロジェクト固有コンテキストを除外した汎用評価モード

### Modified Capabilities

（なし）

## Impact

- `skills/genetic-prompt-optimizer/scripts/optimize.py` — scope 判定 + 評価コンテキスト切替ロジック追加
- `skills/genetic-prompt-optimizer/SKILL.md` — scope 表示・汎用評価モードの説明追加
- 適応度評価パイプライン（CoT 評価プロンプト）— global 時にプロジェクト文脈を注入しない分岐
