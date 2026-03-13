## Why

optimize が rule を修正する際、行数制限（グローバル3行/PJ5行）を超過するとregression gateで**リジェクトするだけ**で、解決策（skill/referencesへの分離）を提案しない。ユーザーが手動で気づいてリファクタするまで放置される。closes #28

## What Changes

- optimize の regression gate 不合格時に「行数超過 → skill/references 分離」の具体的リファクタ提案を生成
- evolve/remediation の既存 `fix_line_limit_violation` を「LLM圧縮」から「分離提案生成」へ拡張
- reflect 実行時にも rule 行数チェックを追加し、超過パターンを検出・提案

## Capabilities

### New Capabilities

- `separation-proposal`: 行数超過 rule を skill/references に分離するリファクタ提案の生成・実行ロジック

### Modified Capabilities

- `optimize-gate-feedback`: optimize の regression gate 不合格時に分離提案を返すフィードバック拡張
- `reflect-line-check`: reflect 実行時の rule 行数チェック追加

## Impact

- `skills/genetic-prompt-optimizer/scripts/optimize.py` — gate 不合格時のフィードバック拡張
- `skills/evolve/scripts/remediation.py` — `fix_line_limit_violation` の分離ロジック追加
- `scripts/lib/reflect_utils.py` — rule 行数チェック追加（既存の suggest_claude_file フロー内）
- `scripts/lib/line_limit.py` — 分離先パス生成ヘルパー追加
