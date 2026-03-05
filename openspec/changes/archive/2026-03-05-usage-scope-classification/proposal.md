## Why

evolve/discover/audit のレポートで openspec 系ツール（propose, refine, apply-change 等）が常に上位を占め、プロジェクト固有のパターン検出を妨げている。インフラ層ツールとプロジェクト固有ツールを分離し、レポートの signal/noise 比を改善する必要がある。

## What Changes

- `audit.py` の `_load_plugin_skill_names()` → `_load_plugin_skill_map()` に拡張。`installed_plugins.json` から `{skill_name: plugin_name}` マッピングを動的構築
- evolve の Discover/Audit レポートで plugin_map ベースのフィルタリングを実施し、PJ固有パターンのみをメインランキングに表示
- プラグインツールの使用状況は別セクション「Plugin usage」としてサマリ表示
- OpenSpec プラグインが検出された場合、ワークフロー分析（ファネル・効率・品質トレンド）を追加表示

## Capabilities

### New Capabilities
- `dynamic-plugin-scan`: `installed_plugins.json` からプラグインスキルを動的検出し、ハードコード prefix を不要にする
- `scoped-report-filtering`: レポート生成時にプラグインスキルをフィルタし、PJ固有とプラグイン利用を分離表示
- `openspec-workflow-analytics`: OpenSpec ライフサイクルのファネル分析・フェーズ別効率・最適化候補の表示

### Modified Capabilities

（既存 spec の要件変更なし。`scope-detection` は optimize.py 用であり、usage 記録とは別軸）

## Impact

- `skills/audit/scripts/audit.py` — `_load_plugin_skill_map()` 追加、`aggregate_usage()` にプラグインフィルタ追加、`build_openspec_analytics_section()` 追加
- `skills/discover/scripts/discover.py` — `detect_behavior_patterns()` でプラグインスキル除外 + plugin_summary 追加
- `skills/evolve/SKILL.md` — Step 7 に表示指示追加
- observe.py への変更は不要（レポート生成時に動的分類するため後方互換問題なし）
