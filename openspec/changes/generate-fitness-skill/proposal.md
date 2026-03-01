## Why

rl-anything を各プロジェクトにインストールしても、組み込みの評価関数（`default`, `skill_quality`）はドメイン非依存の汎用チェックしかできない。プロジェクト固有の品質基準（例: docs-platform の front matter 必須ルール、ooishi-kun の personality 適合性）を反映した評価関数を手動で書く必要があり、導入障壁が高い。

## What Changes

- **新スキル `/generate-fitness`** を rl-anything plugin に追加
- インストール先PJの CLAUDE.md・`.claude/rules/`・`.claude/skills/` を分析し、ドメイン特性と品質基準を自動推定
- 推定結果に基づいて `scripts/rl/fitness/{name}.py` を自動生成（既存インターフェース: stdin → 0.0-1.0 準拠）
- 生成された評価関数は `--fitness {name}` でそのまま利用可能

## Capabilities

### New Capabilities

- `project-analyzer`: CLAUDE.md・rules・skills からドメイン特性・品質基準・命名規約を抽出する分析機能
- `fitness-generator`: 分析結果を元にプロジェクト固有の fitness 関数（Python）を生成する機能

### Modified Capabilities

（なし）

## Impact

- 新規ファイル: `skills/generate-fitness/SKILL.md`, `skills/generate-fitness/scripts/analyze-project.py`, `skills/generate-fitness/templates/fitness-template.py`
- 既存コードへの変更なし（既存の `--fitness {name}` インターフェースをそのまま活用）
- 依存: Claude CLI（`claude -p` でのLLM呼び出し、分析・生成に使用）
