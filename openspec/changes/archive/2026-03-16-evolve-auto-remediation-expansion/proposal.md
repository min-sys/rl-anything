## Why

evolve の Compile ステージ（remediation）は現在 10 種の issue type を自動修正できるが、実運用で頻出する「MEMORY.md 肥大化」「スキル分割」「pitfall 肥大化」「重複統合」は検出のみで修正できず、手動対応が必要になっている。加えて OpenSpec の verify フェーズは利用率 7%（3/42）と事実上スキップされており、ファネル分析のノイズになっている。

## What Changes

- **MEMORY.md 自動整理**: `stale_memory` の FIX_DISPATCH 登録（参照先消失エントリの自動削除）と `near_limit` 時のセクション分離提案
- **スキル分割の proposable 化**: reorganize の `split_candidates` を remediation に接続し、LLM で分割案を生成して proposable として提示
- **pitfall 肥大化の自動剪定**: `cap_exceeded`/`line_guard` の Cold 層（Graduated + Candidate + New）自動アーカイブを FIX_DISPATCH に登録。加えて成熟した Active pitfall の Pre-flight スクリプト化提案（atlas-browser の 294→74行 75%削減パターンを参考）
- **重複統合の proposable 昇格**: `duplicate` issue の confidence を引き上げ、LLM 統合案を proposable として提示
- **verify フェーズの簡素化**: verify スキルを廃止し、archive スキルにタスク完了率チェック（軽量版）を統合。ファネル分析から verify を除外

## Capabilities

### New Capabilities
- `memory-auto-cleanup`: MEMORY.md の stale エントリ自動削除 + near_limit 時のセクション分離
- `skill-split-proposal`: スキル分割の LLM 提案生成 + proposable 化
- `pitfall-auto-archive`: pitfall Cold 層の自動アーカイブ（cap_exceeded/line_guard 対応）+ Pre-flight スクリプト化提案
- `duplicate-merge-proposal`: 重複 artifact の LLM 統合案生成 + proposable 昇格
- `archive-completion-check`: archive 実行時のタスク完了率チェック（verify 代替の軽量版）

### Modified Capabilities
- `remediation-engine`: FIX_DISPATCH に 3 種追加（stale_memory, pitfall_archive, split_candidate）、classify_issue の confidence 調整
- `pitfall-hygiene`: execute_archive() の自動実行パス追加
- `reorganize`: split_candidates を issue_schema 形式で出力、remediation 連携

## Impact

- `skills/evolve/scripts/remediation.py`: FIX_DISPATCH/VERIFY_DISPATCH 拡張、新 fix 関数追加
- `scripts/lib/pitfall_manager.py`: Cold 層自動アーカイブのエントリポイント追加
- `scripts/lib/issue_schema.py`: 新 issue type の factory 関数追加
- `.claude/skills/openspec-archive-change/SKILL.md`: タスク完了率チェック統合
- `.claude/skills/openspec-verify-change/SKILL.md`: 廃止
- `skills/evolve/SKILL.md`: ファネル分析の verify 除外
- `scripts/lib/telemetry_query.py`: ファネル集計から verify 除外
