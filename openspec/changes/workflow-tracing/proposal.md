## Why

observe hooks は「どのツールを呼んだか」を記録するが「どのワークフローの一部として呼んだか」が欠落している。rl-anything 自身のバックフィルデータ分析で、Discover が `Agent:Explore 22回 → 新スキル候補` と的外れな提案をし、Prune が `opsx:refine` を使用0回と誤検出する問題を確認した。原因は Skill 経由の Agent 呼び出しと手動の Agent 呼び出しが区別できないこと。

### 戦略的位置づけ（B+C 戦略）

この問題に対して3つのアプローチを検討した結果、**B+C 戦略**を採用した:
- **Pattern A（Discover 分析改善のみ）**: prompt キーワード分類の精度向上だけでは contextualized/ad-hoc の区別ができないためスキップ
- **Phase B（本 change）**: ワークフロートレーシングでデータ収集。observe hooks に文脈情報を付与し、Discover/Prune の精度を即座に改善する
- **Phase C（次ステップ）**: Phase B で蓄積したワークフローシーケンスデータを基に、ワークフロー構造自体の進化を実現する

本 change は Phase B に該当し、Phase C の設計判断に必要なデータを収集する位置づけである。詳細な戦略分析は [docs/evolve/workflow-tracing.md](../../docs/evolve/workflow-tracing.md) を参照。

## What Changes

- PreToolUse hook を追加し、Skill 呼び出し時にワークフロー文脈ファイル（`$TMPDIR/rl-anything-workflow-{session_id}.json`）を書き出す
- PostToolUse / SubagentStop hook で文脈ファイルを読み取り、usage.jsonl / subagents.jsonl のレコードに `parent_skill`, `workflow_id` を付与する
- Stop hook でワークフロー単位のシーケンスレコードを `workflows.jsonl` に書き出す（Phase C: ワークフロー構造進化の入力データ）
- Discover を改修し、`parent_skill` の有無で `contextualized`（スキル内）/ `ad-hoc`（手動）を分類する
- Prune を改修し、`parent_skill` 経由の使用も使用回数にカウントする

## Capabilities

### New Capabilities
- `workflow-context`: PreToolUse hook によるワークフロー文脈の記録と、PostToolUse/SubagentStop/Stop hook での文脈付与・シーケンス記録

### Modified Capabilities

## Impact

- 新規ファイル: `hooks/workflow_context.py`（PreToolUse handler）
- 変更ファイル: `hooks/observe.py`（parent_skill 読み取り追加）, `hooks/subagent_observe.py`（同）, `hooks/session_summary.py`（workflows.jsonl 書き出し + 文脈ファイル削除）
- 変更ファイル: `skills/discover/scripts/discover.py`（contextualized/ad-hoc 分類）, `skills/prune/scripts/prune.py`（parent_skill 経由カウント）
- 変更ファイル: `hooks.json`（PreToolUse エントリ追加）
- 新規データ: `~/.claude/rl-anything/workflows.jsonl`
- 既存データ拡張: usage.jsonl, subagents.jsonl に `parent_skill`, `workflow_id` フィールド追加（null 許容で後方互換）
