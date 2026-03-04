## Why

MEMORY ファイルは時間とともに陳腐化（削除済みパス参照）・重複・肥大化が蓄積するが、現状の plugin はMEMORYの行数超過チェックのみで内容の品質には触れない。ユーザーが自発的に気づかない限り、古い情報が残り続ける。2つの経路で修正提案を出すことで、MEMORY の品質を維持する。

## What Changes

- **audit に Memory Health セクション追加**: `/rl-anything:audit` 実行時にMEMORYファイルの内容を分析し、陳腐化参照・肥大化警告・改善提案を含む "## Memory Health" セクションをレポートに追加する
- **reflect に Memory Update Candidates 追加**: `/rl-anything:reflect` 実行時に corrections と既存MEMORYエントリを照合し、既存エントリの更新が必要な候補を `memory_update_candidates` として出力に追加する

## Capabilities

### New Capabilities
- `memory-health`: audit レポートに MEMORY ファイルの健康度セクション（陳腐化参照検出・肥大化警告・改善提案）を追加する
- `memory-update-candidates`: reflect 出力に corrections 起点の既存 MEMORY エントリ更新候補を追加する

### Modified Capabilities
- `audit-report`: Memory Health セクションを generate_report() に統合
- `reflect`: build_output() に memory_update_candidates フィールドを追加

## Impact

- `skills/audit/scripts/audit.py` — `build_memory_health_section()` 追加、`generate_report()` に統合
- `skills/reflect/scripts/reflect.py` — `find_memory_update_candidates()` 追加、`build_output()` に統合
- `scripts/reflect_utils.py` — 既存の `read_auto_memory()` / `read_all_memory_entries()` をそのまま利用（変更なし）
- テストファイル追加・拡張
- CHANGELOG.md / plugin.json バージョン更新
