## 1. audit.py に動的プラグインスキャンを実装

- [x] 1.1 `_load_plugin_skill_map()` を実装（`installed_plugins.json` → `{skill_name: plugin_name}` マッピング）
- [x] 1.2 `_load_plugin_skill_names()` を後方互換ラッパーとして維持
- [x] 1.3 `aggregate_usage()` に `exclude_plugins` パラメータ追加
- [x] 1.4 `aggregate_plugin_usage()` 関数を追加

## 2. OpenSpec ワークフロー分析

- [x] 2.1 `_match_openspec_phase()` を実装（スキル名 → ライフサイクルフェーズの推定）
- [x] 2.2 `build_openspec_analytics_section()` を実装（ファネル・効率・品質・最適化候補）
- [x] 2.3 `generate_report()` に `plugin_usage` と `openspec_analytics` パラメータ追加
- [x] 2.4 `run_audit()` でプラグインフィルタと OpenSpec 分析を組み込み

## 3. discover.py のプラグインフィルタ

- [x] 3.1 `_load_plugin_skill_map_lazy()` を追加（audit.py からの遅延インポート）
- [x] 3.2 `detect_behavior_patterns()` でプラグインスキルを除外し plugin_summary に集約

## 4. evolve SKILL.md の更新

- [x] 4.1 Step 7 に Plugin usage / OpenSpec Workflow Analytics の表示指示を追加

## 5. テスト

- [x] 5.1 `_load_plugin_skill_map()` のユニットテスト
- [x] 5.2 `aggregate_usage()` のプラグインフィルタテスト
- [x] 5.3 `build_openspec_analytics_section()` のユニットテスト
- [x] 5.4 `detect_behavior_patterns()` のプラグインフィルタテスト
- [x] 5.5 既存テストが通ることを確認
