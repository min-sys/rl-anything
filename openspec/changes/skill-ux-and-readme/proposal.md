## Why

現在の rl-anything は使い方が `python3 <PLUGIN_DIR>/skills/.../optimize.py --target ...` という長いコマンドで、ユーザーが Plugin ディレクトリのパスを知っている必要がある。Claude Code Plugin としてインストールした意味が薄い。また README.md にはプロジェクトが抱える課題と導入効果のストーリーがなく、「なぜこの Plugin を入れるべきか」が伝わらない。

## What Changes

- **SKILL.md のスキル名変更**: `genetic-prompt-optimizer` → `optimize`、SKILL.md の instructions を「Claude がスクリプトを自動実行する」形式に書き換え（実施済み）
- **README.md の全面更新**: 使い方をスラッシュコマンド中心に書き直し、導入ストーリー（Before/After の物語）を追加
- **CLAUDE.md の同期更新**: README と齟齬がないよう CLAUDE.md のクイックスタートもスラッシュコマンド形式に更新

## Capabilities

### New Capabilities

- `slash-command-ux`: スラッシュコマンド（`/optimize`, `/rl-loop`）でスクリプト実行を Claude に委ねる UX
- `readme-story`: 導入前の課題 → 導入 → 効果を描く物語風ストーリーを README に追加

### Modified Capabilities

（なし）

## Impact

- `skills/genetic-prompt-optimizer/SKILL.md`: スキル名・instructions 変更（実施済み）
- `skills/rl-loop-orchestrator/SKILL.md`: instructions 変更（実施済み）
- `README.md`: 全面更新
- `CLAUDE.md`: クイックスタート部分の更新
