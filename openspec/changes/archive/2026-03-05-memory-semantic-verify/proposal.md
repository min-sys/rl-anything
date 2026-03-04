## Why

MEMORY（auto-memory / global CLAUDE.md）の記述がコードベースの実態と乖離しても検出する手段がない。v0.15.5 の Memory Health はパス存在チェックと肥大化警告のみで、「内容は正確だが誤解を招く」「重要な変更が MEMORY に反映されていない」ケースを捕まえられない。実例として、docs-platform で full-regen が差分更新に最適化済みなのに MEMORY に未反映のまま AI がフルリジェネ前提でコスト試算し、実際より高い見積もりを出す事故が発生した。Claude Code Max（サブスク）なら LLM コストを気にせず検証できる。

## What Changes

- **audit に LLM セマンティック検証ステップを追加**: MEMORY の各セクションをコードベース実態と LLM で突合し、陳腐化・誤解リスク・欠落を検出する（`audit --deep` または `audit` の Step 2 として）
- **openspec-archive スキルに Memory Sync ステップを追加**: change を archive する際に、MEMORY への影響を LLM で分析し更新ドラフトを提示する
- **検証対象スコープの拡張**: project auto-memory に加え、global memory（`~/.claude/CLAUDE.md`）も検証対象にする

## Capabilities

### New Capabilities

- `memory-semantic-audit`: audit 実行時に MEMORY の各セクションをコードベース・OpenSpec archive と LLM で突合し、整合性レポート（✓整合 / ⚠誤解リスク / ✗陳腐化）を出力する
- `archive-memory-sync`: openspec-archive 実行時に、完了した change が MEMORY に与える影響を LLM で分析し、更新ドラフト（diff 形式）をユーザーに提示する

### Modified Capabilities

- `audit-report`: Memory Health セクションに LLM 検証結果（Semantic Verification サブセクション）を追加

## Impact

- `skills/audit/scripts/audit.py`: `build_memory_health_section()` に LLM 検証ロジックを追加、`generate_report()` に統合
- `skills/audit/SKILL.md`: `--deep` フラグまたは Step 2 として LLM 検証の実行手順を追加
- openspec-archive スキル: Memory Sync ステップの追加（archive スキルの場所は要確認）
- `scripts/reflect_utils.py`: global memory 読み取りヘルパーの追加（`read_global_memory()`）
- テスト: 各機能のユニットテスト追加
