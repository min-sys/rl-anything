# Changelog

## [0.2.5] - 2026-03-03

### Added
- `/rl-anything:backfill` スキル: セッショントランスクリプトから Skill/Agent 呼び出しを抽出し usage.jsonl にバックフィル
- `skills/backfill/scripts/backfill.py`: トランスクリプトパーサー＋JSONL 書き出し
- `--force` フラグ: 既存バックフィルレコードを削除して全セッションを再処理
- `--project-dir` オプション: バックフィル対象プロジェクトの指定
- 重複防止（session_id + source=backfill チェック）
- パース失敗時のスキップ＋エラーカウント

## [0.2.4] - 2026-03-03

### Added
- SubagentStop フック `hooks/subagent_observe.py` で subagent の完了データを `subagents.jsonl` に記録
- PostToolUse で Agent ツール呼び出しを観測し `usage.jsonl` に `Agent:{subagent_type}` 形式で記録
- hooks 共通ユーティリティ `hooks/common.py`（`ensure_data_dir`, `append_jsonl`, `DATA_DIR` を集約）

### Fixed
- hooks.json の `$PLUGIN_DIR` を公式仕様 `${CLAUDE_PLUGIN_ROOT}` に修正

## [0.2.3] - 2026-03-03

### Fixed
- `detect_dead_globs` の誤検知: `{ts,tsx}` ブレース展開とカンマ区切り複数パターンに対応
- Python `Path.glob()` がブレース展開をサポートしないため、パターンを個別展開してからマッチ

## [0.2.2] - 2026-03-02

### Fixed
- スクリプトを各スキルの `scripts/` サブディレクトリに配置（プラグイン公式構造に準拠）
- `<PLUGIN_DIR>/skills/{name}/scripts/` 形式のフルパスに統一
- cross-import の `sys.path` をプラグインルートの `scripts/` に向ける

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
