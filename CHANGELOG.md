# Changelog

## [0.2.1] - 2026-03-02

### Fixed
- SKILL.md の `$PLUGIN_DIR` 記法を `<PLUGIN_DIR>` に統一（パス解決エラーの修正）

## [0.2.0] - 2026-03-02

### Added
- **Observe hooks**: PostToolUse/Stop/PreCompact/SessionStart の4フック（hooks.json）
- **Audit**: 環境健康診断 `/rl-anything:audit`
- **Prune**: 未使用アーティファクト淘汰 `/rl-anything:prune`
- **Discover**: 行動パターン発見 `/rl-anything:discover`
- **Evolve**: 全フェーズ統合実行 `/rl-anything:evolve`
- **Evolve-fitness**: 評価関数の改善提案 `/rl-anything:evolve-fitness`
- **Feedback**: フィードバック収集 `/rl-anything:feedback` + GitHub Issue テンプレート
- **Telemetry**: Individual に strategy/cot_reasons フィールド、history.jsonl 記録
- **Bloat control**: サイズバリデーション・肥大化検出
- **Cross-run aggregation**: 戦略効果・accept/reject 比率の集計

## [0.1.0] - 2026-03-01

### Added
- **Genetic Prompt Optimizer**: `/rl-anything:optimize` スキル/ルールの遺伝的最適化
- **RL Loop Orchestrator**: `/rl-anything:rl-loop` 自律進化ループ
- **Generate Fitness**: `/rl-anything:generate-fitness` 適応度関数の自動生成
- **rl-scorer エージェント**: 技術品質 + ドメイン品質 + 構造品質の3軸採点
