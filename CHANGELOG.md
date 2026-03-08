# Changelog

## [0.21.1] - 2026-03-08

### Fixed
- **optimize**: regression gate が LLM パッチによる YAML frontmatter 消失を検出できない問題を修正 (#20)

## [0.21.0] - 2026-03-07

### BREAKING CHANGES
- **optimize**: 遺伝的アルゴリズム（世代ループ）を廃止し、直接パッチモードに置換
  - `--generations`, `--population`, `--budget`, `--cascade`, `--parallel`, `--strategy` オプションを廃止（使用時にエラーメッセージ表示）
  - `GeneticOptimizer` → `DirectPatchOptimizer` に置換
  - 6モジュール削除: strategy_router, granularity, bandit_selector, early_stopping, model_cascade, parallel

### Added
- **optimize**: corrections/context ベースの LLM 1パス直接パッチ最適化
  - `--mode auto|error_guided|llm_improve` オプション追加
  - corrections.jsonl からエラー分類し直接パッチ（error_guided モード）
  - usage 統計・audit issues・pitfalls をコンテキストに含めた汎用改善（llm_improve モード）
  - history.jsonl に `strategy`/`corrections_used` フィールド追加
  - `_extract_markdown` を複数ブロック対応に改善（最長ブロック返却）
- LLM コール数を 6〜15+ → 1回に削減

### Changed
- README.md, CLAUDE.md, docs/evolve/optimize.md の遺伝的アルゴリズム記述を直接パッチに更新
- rl-loop-orchestrator SKILL.md の説明を直接パッチに更新、API コスト目安更新

## [0.20.0] - 2026-03-07

### Added
- **optimize**: 大規模スキル向け budget_mpo パイプライン — 6モジュール+205テスト
  - strategy_router: ファイルサイズに基づく self_refine/budget_mpo 自動選択
  - granularity: 適応的粒度制御（none/h2_h3/h2_only 3段階分割）
  - bandit_selector: Thompson Sampling によるセクション選択 + LOO 重要度推定
  - model_cascade: FrugalGPT 3段カスケード（haiku→sonnet→opus）
  - early_stopping: 4条件停止（品質到達/プラトー/バジェット/収穫逓減）
  - parallel: references/ 並行最適化 + de-dup consolidation
  - optimize.py に Phase 0-3 パイプライン統合、Prefix Caching 対応
  - SKILL.md に `--budget`/`--strategy`/`--cascade`/`--parallel` オプション追加

## [0.19.6] - 2026-03-06

### Added
- **discover**: 推奨ルール/hook 未導入検出を追加 — 先送り禁止ルール+Stop hook の導入提案
- **audit**: skill/rule内ハードコード値検出 — 5パターン+許容除外+インライン抑制

## [0.19.5] - 2026-03-06

### Fixed
- **audit**: パス抽出の偽陽性を修正 — MEMORY 内の説明的スラッシュ表現（`usage/errors`, `discover/audit` 等）がファイルパスとして誤検出されなくなった

### Added
- **classify**: conversation を5サブカテゴリに細分化（approval/confirmation/question/direction/thanks）

## [0.19.4] - 2026-03-06

### Fixed
- **optimize**: 最適化結果の accept/reject 確認フローを SKILL.md に追加 — `history.jsonl` に `human_accepted` が記録されるようになり、evolve-fitness が機能する

## [0.19.3] - 2026-03-06

### Added
- **tool-usage-analysis**: discover にツール利用分析フェーズを追加
  - セッション JSONL からツール呼び出しを抽出し、Bash コマンドを3カテゴリに分類（builtin_replaceable / repeating_pattern / cli_legitimate）
  - `--tool-usage` フラグで有効化、evolve 経由では自動有効化
  - builtin_replaceable をルール候補、repeating_pattern をスキル候補として出力

## [0.19.2] - 2026-03-06

### Added
- **remediation-engine**: evolve パイプラインに Remediation フェーズ（Step 7.5）を追加
  - confidence_score / impact_scope ベースの動的3カテゴリ分類（auto_fixable / proposable / manual_required）
  - 修正理由（rationale）付きの一括承認 / 個別承認フロー
  - 陳腐化参照の自動削除、行数超過に対する修正案生成
- **remediation-verification**: 修正後の2段階検証（Fix Verification + Regression Check）
  - regression 検出時に自動ロールバック
- 修正結果を `remediation-outcomes.jsonl` に記録（dry-run 時スキップ）

## [0.19.1] - 2026-03-06

### Added
- **reference-skill-classification**: 参照型スキルを自動判定し prune の淘汰対象から除外
- **reference-drift-detection**: 参照型スキルの内容とコードベースの乖離度を評価
- **audit-untagged-warning**: ゼロ呼び出し + `type` 未設定のスキルを audit レポートで警告

## [0.19.0] - 2026-03-06

### Added
- **missed-skill-detection**: 「スキルが存在するのに使われなかった」パターンを検出・レポート
- **scope-aware-routing**: reflect の修正反映先をプロジェクト固有シグナルで自動判定

## [0.18.1] - 2026-03-06

### Fixed
- backfill: usage/workflows/sessions レコードに `project` フィールドが欠落していた問題を修正

## [0.18.0] - 2026-03-06

### Added
- **cross-project-telemetry-isolation**: observe hooks に project フィールド追加、プロジェクト単位のテレメトリ分離
- discover/audit: `--project-dir` によるプロジェクト単位フィルタリング
- **interactive-merge-proposal**: reorganize 検出の中類似度ペアに対して対話的統合提案

## [0.17.0] - 2026-03-05

### Added
- **agent-type-classification**: 組み込み Agent をメインランキングから除外し `agent_usage_summary` に分離

### Changed
- `determine_scope()` が `agent_type` フィールドを優先参照するように拡張

## [0.16.0] - 2026-03-05

### Added
- **usage-scope-classification**: プラグインスキルの動的検出とレポート分離表示
- **OpenSpec Workflow Analytics**: ファネル・完走率・フェーズ別効率・品質トレンド・最適化候補

### Changed
- audit レポートの Usage を PJ 固有スキルのみに変更、Plugin usage サマリを追加

## [0.15.6] - 2026-03-05

### Added
- **Memory Semantic Verification**: audit に LLM セマンティック検証を追加（CONSISTENT / MISLEADING / STALE 判定）
- **archive Memory Sync**: openspec-archive 時に MEMORY への影響を分析し更新ドラフトを提示

## [0.15.5] - 2026-03-05

### Added
- **audit Memory Health**: MEMORY ファイルの健康度セクション追加（陳腐化参照検出・肥大化早期警告）
- **reflect memory_update_candidates**: corrections と既存 MEMORY のキーワードマッチによる更新候補検出

## [0.15.4] - 2026-03-04

### Added
- **merge-group-filter**: reorganize 由来 merge_groups に TF-IDF コサイン類似度フィルタを適用し偽陽性を排除

## [0.15.3] - 2026-03-04

### Added
- **quality_monitor**: 高頻度スキルの品質スコアを定期計測し劣化を検知
- audit レポートに "Skill Quality Trends" セクション追加（スパークライン・DEGRADED マーカー）

## [0.15.1] - 2026-03-04

### Added
- **similarity-engine**: TF-IDF + コサイン類似度の共通計算エンジン
- corrections の矛盾検出（`detect_contradictions()`）

### Changed
- `semantic_similarity_check()` を TF-IDF 実装に置換し誤検知 465 件を解消

## [0.15.0] - 2026-03-04

### Added
- **merge-suppression**: merge 統合候補の却下を記録し次回以降の再提案を抑制

## [0.14.0] - 2026-03-04

### Added
- **smart-prune-recommendation**: prune 候補に description + 推薦ラベル（archive推奨/keep推奨/要確認）を付与
- **2段階承認フロー**: AskUserQuestion の options 上限を遵守した段階的承認 UI

## [0.13.0] - 2026-03-04

### Breaking Changes
- **scripts/ 二重管理の解消**: `scripts/*.py` を削除し `skills/*/scripts/` に一本化

### Added
- **LLM 入力サニタイズ**: corrections データのサニタイズ（500文字切り詰め、制御文字除去、XML タグ除去）
- **偽陽性フィードバック機構**: corrections の偽陽性を SHA-256 ハッシュで管理・自動フィルタリング
- **ファイルパーミッション強化**: データディレクトリ 700、JSONL 新規作成時 600

## [0.12.0] - 2026-03-04

### Added
- **Reflect スキル**: `/rl-anything:reflect` — corrections.jsonl の修正フィードバックを CLAUDE.md/rules に反映
- **discover --session-scan**: セッション JSONL のユーザーメッセージを直接分析し繰り返しパターンを検出
- **セマンティック検証デフォルト有効**: corrections のセマンティック検証をバッチ送信でデフォルト有効化
- **evolve Reflect フェーズ**: evolve パイプラインに Reflect ステップを追加

## [0.11.0] - 2026-03-04

### Added
- **Enrich Phase**: Discover のパターンを既存スキルに Jaccard 係数で照合し改善提案を生成
- **Merge サブステップ**: Prune 内で重複スキルの統合版生成→ユーザー承認→アーカイブ
- **Reorganize Phase**: TF-IDF + 階層クラスタリングでスキル群を分析し統合/分割候補を提案

## [0.10.3] - 2026-03-03

### Added
- evolve に fitness 関数チェックステップ追加: 未生成時に `generate-fitness --ask` を促す
- evolve に fitness evolution ステップ追加: accept/reject データから評価関数の改善を提案
- rules を淘汰対象から除外し情報提供のみに変更

## [0.10.2] - 2026-03-03

### Fixed
- global スキル判定を hooks データのみに限定し、backfill データでの誤判定を解消

## [0.10.1] - 2026-03-03

### Fixed
- `load_usage_registry()` が usage-registry.jsonl 不在時にフォールバック（global スキルが全て未使用扱いになる問題を修正）

## [0.10.0] - 2026-03-03

### Added
- **Correction Detection**: ユーザーの修正フィードバックをリアルタイム検出し `corrections.jsonl` に記録
- **Confidence Decay**: 時間減衰 + correction ペナルティで淘汰精度を向上
- **Pin 保護**: `.pin` ファイル配置でスキルを淘汰対象から除外
- **Multi-Target Routing**: 改善先の自動振り分け（correction > prune > claude_md > rule）
- **Backfill Corrections**: 過去トランスクリプトから修正パターンを遡及抽出

## [0.9.1] - 2026-03-03

### Fixed
- hooks が発火しない致命的バグを修正: `hooks.json` の配置場所と matcher 形式を修正

## [0.9.0] - 2026-03-03

### Added
- ワークフロー統計分析: workflows.jsonl からスキル別統計を算出
- `generate-fitness --ask`: 品質基準を対話的に質問し `fitness-criteria.md` に保存
- rl-scorer にワークフロー効率性の補助シグナル追加

## [0.8.0] - 2026-03-03

### Added
- `Task` ツール対応: 旧 Claude Code の `Task`（= 現 `Agent`）を同等に処理
- ビルトインコマンドフィルタ: `/clear`, `/compact` 等 18 コマンドをスキル起動から除外

### Changed
- ワークフロー捕捉率: 5PJ 合計 50 → 301 ワークフロー（6倍増）

## [0.7.0] - 2026-03-03

### Added
- team-driven ワークフロー検出: TeamCreate → Agent → TeamDelete パターンを追跡
- agent-burst ワークフロー検出: 300秒以内の連続 Agent 呼び出しを自動グルーピング
- `command-name` ワークフローアンカー

### Changed
- ワークフロー捕捉率: 4.2% → 26.2%

## [0.6.0] - 2026-03-03

### Added
- システムメッセージのノイズフィルタ（中断シグナル、ローカルコマンド出力、タスク通知を除外）
- `user_prompts` 収集: セッションメタに記録

### Changed
- subprocess 廃止: `backfill.py` を直接 import して実行（セキュリティ改善）

## [0.5.0] - 2026-03-03

### Added
- **出自分類**: スキル/ルールを custom / plugin / global に分類
- プラグイン由来スキルを淘汰候補から除外し `plugin_unused` として表示
- evolve レポートに Custom / Plugin / Global の出自別3セクション表示

## [0.4.1] - 2026-03-03

### Added
- `classify_prompt()` のキーワード拡充: 6 新カテゴリ + 日本語キーワード
- LLM Hybrid 再分類: キーワードで "other" に残ったプロンプトを Claude が再分類

## [0.4.0] - 2026-03-03

### Added
- プロジェクト単位のデータ分析: `--project` フィルタ

## [0.3.3] - 2026-03-03

### Added
- `/rl-anything:version` スキル: インストール済みバージョンとコミットハッシュを確認

## [0.3.2] - 2026-03-03

### Added
- Backfill データ収集範囲の拡張: セッションメタデータ（tool_sequence, duration, error_count 等）

## [0.3.1] - 2026-03-03

### Added
- Backfill ワークフロー構造抽出: ワークフロー境界検出 + workflows.jsonl 生成

## [0.3.0] - 2026-03-03

### Added
- ワークフロートレーシング: Skill 呼び出し時にワークフロー文脈を記録
- Discover に contextualized/ad-hoc/unknown の3分類追加

## [0.2.5] - 2026-03-03

### Added
- `/rl-anything:backfill` スキル: セッショントランスクリプトから usage.jsonl にバックフィル

## [0.2.4] - 2026-03-03

### Added
- SubagentStop フック: subagent 完了データを `subagents.jsonl` に記録
- PostToolUse で Agent ツール呼び出しを観測

### Fixed
- hooks.json の `$PLUGIN_DIR` を公式仕様 `${CLAUDE_PLUGIN_ROOT}` に修正

## [0.2.3] - 2026-03-03

### Fixed
- `detect_dead_globs` の誤検知: `{ts,tsx}` ブレース展開に対応

## [0.2.2] - 2026-03-02

### Fixed
- スクリプトをプラグイン公式構造に準拠する配置に修正

## [0.2.1] - 2026-03-02

### Fixed
- SKILL.md の `$PLUGIN_DIR` 記法を `<PLUGIN_DIR>` に統一

## [0.2.0] - 2026-03-02

### Added
- **Observe hooks**: PostToolUse/Stop/PreCompact/SessionStart の4フック
- **Audit**: `/rl-anything:audit` 環境健康診断
- **Prune**: `/rl-anything:prune` 未使用アーティファクト淘汰
- **Discover**: `/rl-anything:discover` 行動パターン発見
- **Evolve**: `/rl-anything:evolve` 全フェーズ統合実行
- **Evolve-fitness**: `/rl-anything:evolve-fitness` 評価関数の改善提案
- **Feedback**: `/rl-anything:feedback` フィードバック収集

## [0.1.0] - 2026-03-01

### Added
- **Genetic Prompt Optimizer**: `/rl-anything:optimize` スキル/ルールの遺伝的最適化
- **RL Loop Orchestrator**: `/rl-anything:rl-loop` 自律進化ループ
- **Generate Fitness**: `/rl-anything:generate-fitness` 適応度関数の自動生成
- **rl-scorer エージェント**: 技術品質 + ドメイン品質 + 構造品質の3軸採点
