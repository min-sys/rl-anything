# Changelog

## [0.3.1] - 2026-03-03

### Added
- Backfill ワークフロー構造抽出: parse_transcript() がワークフロー境界を検出し workflows.jsonl を生成
- `skills/backfill/scripts/analyze.py`: ワークフロー分析スクリプト（一貫性・バリエーション・介入・Discover/Prune 比較）
- `hooks/common.py` に `PROMPT_CATEGORIES` / `classify_prompt()` を共通化（DRY 解消）

### Changed
- `hooks/session_summary.py`: `_PROMPT_CATEGORIES`/`_classify_prompt` を `common.classify_prompt()` に置換
- `skills/discover/scripts/discover.py`: `_PROMPT_CATEGORIES` を `common.PROMPT_CATEGORIES` に置換
- `skills/backfill/scripts/backfill.py`: ParseResult dataclass 導入、backfill() が workflows.jsonl を出力

## [0.3.0] - 2026-03-03

### Added
- ワークフロートレーシング: Skill 呼び出し時に PreToolUse hook でワークフロー文脈を記録
- `hooks/workflow_context.py`: PreToolUse handler（文脈ファイル書き出し）
- `hooks/common.py` に `read_workflow_context()`: 文脈ファイル読み取りの共通関数（24h expire、サイレント失敗）
- PostToolUse/SubagentStop で `parent_skill`, `workflow_id` を usage.jsonl/subagents.jsonl に付与
- Stop hook で `workflows.jsonl` にワークフローシーケンスレコードを書き出し
- Discover に contextualized/ad-hoc/unknown の3分類を追加（ad-hoc のみスキル候補に）
- Prune に `parent_skill` 経由使用のカウントを追加（plan mode 経由使用の誤検出を解消）
- hooks.json に PreToolUse エントリを追加

### Changed
- `hooks/observe.py`: Agent 呼び出しに parent_skill/workflow_id を付与
- `hooks/subagent_observe.py`: SubagentStop に parent_skill/workflow_id を付与
- `hooks/session_summary.py`: ワークフローシーケンス組み立て + 文脈ファイルクリーンアップ
- `skills/discover/scripts/discover.py`: parent_skill ベースの分類ロジック
- `skills/prune/scripts/prune.py`: parent_skill 経由カウント

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
