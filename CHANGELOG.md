# Changelog

## [0.9.1] - 2026-03-03

### Fixed
- hooks が発火しない致命的バグを修正: `hooks.json` の配置場所をルート → `hooks/` に移動、matcher 形式をオブジェクト → 文字列に変更（claude-reflect 等の動作実績あるプラグインと同一形式に統一）

## [0.9.0] - 2026-03-03

### Added
- `scripts/rl/workflow_analysis.py`: workflows.jsonl からスキル別ワークフロー統計を算出し JSON 出力
  - 抽象パターン圧縮（連続同一エージェントを1つに集約）
  - `--min-workflows`, `--hints`, `--for-fitness` オプション
  - team-driven / agent-burst の統計キー対応
- `generate-fitness --ask`: ユーザーに品質基準を対話的に質問し `.claude/fitness-criteria.md` に保存
- rl-scorer にワークフロー効率性の補助シグナル（一貫性・ステップ効率・戦略明確さ）

### Changed
- `optimize.py`: mutation プロンプトにワークフロー分析ヒントを注入（統計がない場合はフォールバック）
- `analyze_project.py`: ワークフロー統計 JSON + `.claude/fitness-criteria.md` のマージ対応
- `fitness-template.py`: ワークフロー統計参照のスケルトンコメント追加

## [0.8.0] - 2026-03-03

### Added
- `Task` ツール対応: 旧 Claude Code の `Task`（= 現 `Agent`）を同等に処理（5PJ で 750+ 呼び出し復活）
- ビルトインコマンドフィルタ: `/clear`, `/compact`, `/model` 等 18 コマンドをスキル起動から除外
- `system` レコードの `api_error` からエラーカウント（従来の `tool_result` は実データに不在）
- session_meta 拡充: `thinking_count`, `compact_count`, `plan_mode_count`
- テスト 16 件追加（Task エイリアス 5 件、ビルトインフィルタ 6 件、メタデータ 5 件）

### Changed
- ワークフロー捕捉率: 5PJ 合計 50 → 301 ワークフロー（6 倍増）

## [0.7.0] - 2026-03-03

### Added
- team-driven ワークフロー検出: TeamCreate → Agent → TeamDelete パターンを追跡
- agent-burst ワークフロー検出: 300 秒以内の連続 Agent 呼び出しを自動グルーピング
- `command-name` ワークフローアンカー: `<command-name>` タグからもスキル起動を認識
- Skill tool_use 重複排除: command-name で既にアンカー済みの場合はスキップ
- `workflows_by_type` サマリー: skill-driven / team-driven / agent-burst の内訳
- テスト 14 件追加（team-driven 3 件、agent-burst 5 件、mixed 2 件、command-name 4 件）

### Changed
- ワークフロー捕捉率: 4.2% → 26.2%（8 → 50 ワークフロー）

## [0.6.0] - 2026-03-03

### Added
- `_classify_system_message()`: human メッセージのノイズフィルタ（中断シグナル、ローカルコマンド出力、タスク通知を除外）
- `<command-name>` タグからスキル名を抽出し `skill-invocation` として分類
- `user_prompts` 収集: user_intents と対になるプロンプトテキストを session_meta に記録
- `filtered_messages` カウント: フィルタされたシステムメッセージ数を session_meta に記録
- テスト 19 件追加（分類ロジック 6 件、統合テスト 6 件、既存テスト更新 7 件）

### Changed
- subprocess 廃止: `backfill.py` を直接 import して実行（セキュリティ改善）
- `parse_transcript()` の human メッセージ処理を分類ベースに全面刷新

## [0.5.0] - 2026-03-03

### Added
- `classify_artifact_origin(path)`: スキル/ルールの出自を custom / plugin / global に分類するユーティリティ関数
- `_load_plugin_skill_names()`: `installed_plugins.json` からプラグインインストール済みスキル名を取得（キャッシュ付き）
- `detect_zero_invocations()` がプラグイン由来スキルを淘汰候補から除外し `plugin_unused` として返す
- `run_prune()` の戻り値に `plugin_unused` キーを追加
- evolve レポートに Custom / Plugin / Global の出自別3セクション表示
- 全9スキル SKILL.md に YAML frontmatter 追加（name, description, disable-model-invocation）
- prune テスト 15 件追加（出自分類・プラグイン除外・installed_plugins.json フォールバック）

### Changed
- `/scripts/prune.py` を削除し `skills/prune/scripts/prune.py` に統一（DRY 違反解消）
- `scripts/evolve.py`, `skills/evolve/scripts/evolve.py` の import パスを修正

### Removed
- `.claude/commands/opsx/` ディレクトリ（SKILL.md に一本化）
- `/scripts/prune.py`（重複していた旧版）

## [0.4.1] - 2026-03-03

### Added
- `classify_prompt()` のキーワード拡充: 6 新カテゴリ（git-ops, deploy, debug, test, config, conversation）+ 既存カテゴリへの日本語キーワード追加
- カテゴリ優先順位制御（辞書順序で spec-review > code-review > git-ops > ... > conversation）
- LLM Hybrid 再分類: `reclassify.py` でキーワード分類で "other" に残ったプロンプトを Claude が再分類
- `analyze.py` が `reclassified_intents` フィールドを優先して使用
- SKILL.md に Step 2（Intent 再分類）を追加
- テスト 40+ 件追加（新カテゴリ・日本語・優先順位テスト）

### Changed
- `PROMPT_CATEGORIES` のカテゴリ数: 5 → 11（"other" 率 70% → 20-30% 目標）
- SKILL.md のステップ番号を再整理（Step 2: 再分類、Step 3: 分析、Step 4: --force）

## [0.4.0] - 2026-03-03

### Added
- `analyze.py` にプロジェクトフィルタ機能: `--project` CLI 引数でプロジェクト単位のデータ分析が可能に
- `get_project_session_ids()`: sessions.jsonl から project_name でフィルタした session_id セットを取得
- `load_jsonl()` に `session_ids` フィルタパラメータ追加
- テスト 10 件追加（project filter 関連）

### Changed
- `project_name_from_dir()` を `backfill.py` から `hooks/common.py` に移動し共通化
- `run_analysis()` が `project` 引数を受け取りフィルタ済みデータで分析を実行
- SKILL.md Step 2 コマンドに `--project "$(basename $(pwd))"` を追加

## [0.3.3] - 2026-03-03

### Added
- `/rl-anything:version` スキル: インストール済みバージョンとコミットハッシュを確認

## [0.3.2] - 2026-03-03

### Added
- Backfill データ収集範囲の拡張: 全 tool_use の名前+順序、セッションメタデータを `sessions.jsonl` に記録
- セッションメタデータ: tool_sequence, tool_counts, session_duration_seconds, error_count, human_message_count, user_intents, project_name
- `analyze.py` にセッション分析・プロジェクト別セクション追加

### Changed
- `backfill.py`: human メッセージの intent 分類、tool_result の error 検出、全 tool_use 名の収集を追加
- `backfill.py`: Skill/Agent がないセッションでもメタデータを sessions.jsonl に記録
- `--force` を project-scoped に変更（対象プロジェクトのみ再処理、他プロジェクトは保持）

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
