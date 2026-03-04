# Roadmap

rl-anything の将来計画。現在の実装状況は [README.md](../README.md) を参照。

## 1. 自動トリガー（Zero-Touch Auto Evolve）

現状は `/evolve` を手動で呼ぶ必要がある。自動化に必要なのは「いつ・何をきっかけに最適化を走らせるか」のトリガー設計。

### 候補トリガー

| トリガー | タイミング | やること |
|---------|-----------|---------|
| スキル変更検知 | `.claude/skills/*/SKILL.md` が編集されたとき（hook） | 変更されたスキルに `/optimize --dry-run` でスコア計測 → 閾値以下なら最適化提案 |
| セッション終了時 | Claude Code セッション終了時（hook） | 変更されたスキルを git diff で検出 → 最適化対象リストを提示 |
| 定期スコア計測 | 月1回（手動 or cron） | 全スキルのスコアを計測 → 前回比で劣化したスキルを報告 |
| corrections 蓄積閾値 | corrections.jsonl に新規パターンが N 件蓄積されたとき | 関連スキルの再最適化を提案 |

### 実装アプローチ案

1. **Claude Code hooks**: `PostToolUse` や `Stop` hook でスキル変更を検知し、バックグラウンドでスコア計測
2. **Wrapper skill**: `/auto-evolve` スキルとして、全スキルのスコア計測→劣化検知→最適化→人間確認を一括実行
3. **Passive mode**: 最適化は走らせないが、スコアの記録と劣化検知のみ行い、レポートを出力

### 設計時に考慮すべきこと

- 人間確認ステップは維持する（完全自律はリスクが高い）
- バックグラウンド実行のコスト管理（全スキル×毎回は重い）
- スコア履歴の永続化（推移を可視化できるように）
- 「最適化不要」マークの仕組み（安定したスキルは除外）

## 2. 自動圧縮トリガー

bloat check レポートは audit スキルで実装済み。以下は自動化の将来計画:

| トリガー | アクション |
|---------|-----------|
| rules 総数 > 100 | 重複検出 + 統合提案を自動実行 |
| skill 総数 > 30 | 使用頻度分析 + archive 提案を自動実行 |
| MEMORY.md > 150行 | トピック別ファイルへの分割を自動提案 |

詳細は [bloat-control.md](./evolve/bloat-control.md) を参照。

## 3. Plugin Bundling

evolve が「常に一緒に使われるスキル群」を検出したら plugin 化を提案する機能。
Layer 1/2（Usage Registry + Scope Advisor）の運用データが十分に蓄積された後に着手予定。

詳細は [bloat-control.md](./evolve/bloat-control.md#layer-3-plugin-bundling将来計画--未実装) を参照。
