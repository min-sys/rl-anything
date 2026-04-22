# Changelog

## [Unreleased]

## [1.33.0] - 2026-04-22

### Changed
- **`scripts/lib/audit.py` の `DATA_DIR` を `rl_common.DATA_DIR` へ統一** — `audit.py:42` でハードコードされていた `DATA_DIR = Path.home() / ".claude" / "rl-anything"` を削除し、`from rl_common import DATA_DIR` に差し替え。`rl_common.py` は既に `CLAUDE_PLUGIN_DATA` env var をサポートしているため、`audit.py` 経由でも fleet 構想（issue #68）で必要な cross-project データ切替が動作するようになる。`bloat_control.py` の `from audit import DATA_DIR` と既存テストの `patch("audit.DATA_DIR", ...)` は再エクスポート (`audit.DATA_DIR is rl_common.DATA_DIR`) によって互換維持。5 tests 追加（env 未設定/env 指定/空文字 fallback/identity/bloat_control 経路）、全 1547 tests pass

### Added
- **cleanup スキル**: `skills/cleanup/SKILL.md` + `scripts/lib/cleanup_scanner.py` — PR マージ・デプロイ後に残る後片付け（マージ済みローカルブランチ削除・remote refs prune・一時 worktree 削除・一時ディレクトリ削除・関連 Issue close 候補提案・元 PR の Test plan 残件リマインド）を、候補提示→`AskUserQuestion` で個別承認→実行で安全に処理する `/rl-anything:cleanup`。`locked` worktree・現在 checkout 中のブランチ・`main`/`master`/`develop` は削除候補から除外。スキャナは純粋関数 6 本（TDD 24 tests）(closes #69)
- **cleanup: tmp prefix を userConfig 化** — `manifest.userConfig` に `cleanup_tmp_prefixes` (string, カンマ区切り, default `"rl-anything-"`) を追加。`scripts/lib/cleanup_scanner.py::parse_prefix_config` で string → list 変換（trim / 空要素除去 / 重複排除 / `None` 許容）。SKILL.md は `load_user_config` + `parse_prefix_config` 経由で prefix を取得し、実行時に scan scope を `[cleanup] tmp scan scope: [...]` で宣言表示。scanner 側 `_DEFAULT_TMP_EXCLUDE_PATTERNS` は常時有効なので、ユーザーが `claude-` を再追加しても Claude Code runtime / MCP bridge は保護される (closes #71)

### Fixed
- **SPEC.md L75 の PR #38 記載誤り** — 「PR #38 で基盤完了」と記述していたが PR #38 は実際は v1.15.0 (FileChanged hook + MEMORY.md + userConfig) であり cross-project audit の基盤ではなかった。fleet 構想 (issue #68) として再設計する旨に修正。TODOS.md に rl-fleet Phase 3 の `resolve_auto_memory_dir` 特殊文字ケーステスト P2 エントリを追加
- **cleanup scanner: 一時ディレクトリ prefix の危険領域除外** — dogfood (#70) で `scan_tmp_dirs` デフォルト prefix (`claude-` / `gstack-` / `rl-anything-`) が `/tmp/claude-<uid>` (Claude Code runtime) や `/tmp/claude-mcp-*` (実行中 MCP bridge) を削除候補に含めるクリティカルバグを検出。SKILL.md のデフォルト prefix を `rl-anything-` のみに narrow し、scanner 側に `exclude_patterns` を追加して `claude-\d+` / `claude-mcp-*` を二重保護。userConfig 化の拡張は #71 で追跡
- **agents: Stop hook を rl-scorer/second-opinion に追加** — CC v2.1.116 で agent frontmatter `hooks:` が `--agent` 経由でも発火するようになったため、`subagent_observe.py` を Stop フックとして追加。main-thread 起動時もテレメトリが記録される

## [1.32.0] - 2026-04-17

### Added
- **agent-brushup: 自己進化プロトコル** — `create` サブコマンドで生成するエージェント scaffold に Self-Evolution Protocol セクションを必須埋め込み。global/project スコープに応じた定義ファイルパスを生成時に確定し、セッション末尾での自己診断→ユーザー承認→定義更新のサイクルをエージェントに内蔵
- **rl-anything-advisor エージェント** — プロジェクト専用エージェント（`.claude/agents/`）として追加。rl-anything 操作・スキル設計・環境診断・テレメトリ分析に特化

## [1.31.0] - 2026-04-17

### Added
- **agent-brushup: 知識陳腐化防止パターン** — `agent_quality.py` に `knowledge_hardcoding` アンチパターン（閾値3/10で low/medium 分岐）と `jit_file_references` ベストプラクティスを追加。エージェントが知識をハードコードして陳腐化するパターンを診断で検出し、JIT識別子戦略（回答前にファイルを動的確認）の採用を促す。5テスト追加 (closes #67)

## [1.30.1] - 2026-04-17

### Changed
- **implement スキル: plan ファイル名仕様を追記**: `skills/implement/SKILL.md` — CC v2.1.111 以降、plan ファイル名がプロンプト内容由来（例: `fix-auth-race-snug-otter.md`）になった仕様と最新ファイル特定コマンドを追記

## [1.30.0] - 2026-04-16

### Added
- **implement スキル: タスク境界の認知分離**: `skills/implement/SKILL.md` — context: fresh 相当の「認知汚染防止」をStandard モードに追加。タスク開始前にスコープ・インターフェース契約・完了条件を明示し、前タスクの実装詳細はメモリから参照せず Read ツールで確認するよう規定
- **ScorerOutput スキーマバリデーション**: `scripts/lib/scorer_schema.py` — rl-scorer エージェント出力の型付き検証。`frozen dataclass` による `AxisResult` / `ScorerOutput` + `validate_scorer_output()` で必須キー欠損・型不正・範囲外を `ScorerValidationError` で早期検出。`output_evaluator.py` の `_score_axis` を `parsed.get(key, 0.0)` → `parsed[key]` に変更しキー欠損を明示。28テスト

## [1.29.0] - 2026-04-16

### Added
- **TBench2-rl Week 1**: `scripts/bench/golden_extractor.py` — usage.jsonl + corrections.jsonl から GoldenCase（正例/負例ペア）を抽出する基盤を TDD で実装。GoldenCase dataclass / GoldenExtractor クラス / CLI エントリーポイント。24テスト
- **TBench2-rl スパイク**: `scripts/bench/spike_rl_scorer_output_eval.py` — rl-scorer 3軸（技術/ドメイン/構造）の LLM 出力評価転用可否を haiku で検証。結果: 転用可能（integrated 0.767 / domain 0.82 が rl-anything 固有観点を正確評価）
- **TBench2-rl Week 3**: `scripts/bench/mutation_injector.py` — harness に劣化を注入する sentinel system。3パターン（rule_delete / trigger_invert / prompt_truncate）× MutationInjector + SentinelRunner。ライブファイル非書き換え、インメモリ変換。detection_threshold=0.5 で自動判定。39テスト
- **TBench2-rl Week 2**: `scripts/bench/run_benchmark.py` + `output_evaluator.py` — golden_cases.jsonl → haiku 出力生成 → 3軸採点 → benchmark_results.jsonl。BenchmarkResult / BenchmarkRunner / OutputEvaluator / AxisScores。--max-api-calls 100 / --dry-run / score_pre・delta 差分追跡。33テスト。pytest -m bench マーカー追加

### Changed
- **release-notes-review Step 6**: 実装後レビューステップを追加。ファイル変更後に `git diff` が存在する場合、`Skill` tool で `/review` を呼び出して品質ゲートをかける（CC v2.1.108 の built-in slash command via Skill tool 対応）

## [1.28.0] - 2026-04-15

### Added
- **philosophy-review スキル**: Claude Code native セッション履歴 (`~/.claude/projects/<slug>/*.jsonl`) を Judge LLM (haiku) で評価し、`category: "philosophy"` 原則の違反例を corrections.jsonl に注入する月1手動レビュー機能。`reflect` ループに乗せて rule/memory 化判断する設計
- **philosophy seed principles**: `SEED_PRINCIPLES` (principles.py) に Karpathy 4原則 (think-before-coding / simplicity-first / surgical-changes / goal-driven-execution) を `seed: true, category: "philosophy"` で追加。コード経由で全環境配布 (ADR-020)
- **principles.py category enum 拡張**: `_build_extraction_prompt` の category enum に `philosophy` を追加。openspec の seed セクションを「数値固定」から「カテゴリ別構造」に再構造化

### Fixed
- **philosophy-review SEED フォールバック**: principles.json cache が SEED 追加前に生成されていた場合でも philosophy 原則を評価対象にできるよう、`SEED_PRINCIPLES` から直接マージ。cache の `user_defined: true` エントリは優先される
- **philosophy-review hardening (1回目)**: LLM が hallucinate した principle_id を drop、confidence を [0.0, 1.0] に clamp + 非数値を reject、`_slug_from_cwd` を Claude Code 仕様（`.`/`_` 置換+連続 dash 圧縮）に整合し実在 dir fallback を追加、token cap をブロック境界 truncation に変更、prompt injection hardening (BEGIN/END markers + data-not-instructions 宣言)、cache 破損 entry ガード
- **philosophy-review hardening (2回目)**: 先頭巨大ブロック時に後続 tail を保持（以前は head/tail 両方空の場合のみ fallback）、transcript 内の marker 文字列を `[BEGIN_MARKER]`/`[END_MARKER]` に置換し prompt 境界偽装を防止、`_sanitize_violation` が入力 dict を mutate せず shallow copy を返すよう変更

## [1.27.1] - 2026-04-13

## [1.27.1] - 2026-04-13

### Added
- **PostCompact hook**: Compact 後に PreCompact で保存した checkpoint から作業コンテキスト（ブランチ・直近コミット・未コミットファイル）を systemMessage として注入。コンテキスト復元精度が向上

### Fixed
- **usage.jsonl カラム名統一**: `observe.py` の書き込みと DuckDB クエリ層が `timestamp` を使用していたが、実データは `ts` カラムだったため `skill_evolve` フェーズで Binder Error が発生。書き込み・クエリ・テストデータを `ts` に統一 (#59, #61)
- **Skill 使用の self-report 方式に移行**: PostToolUse が Skill ツールに対して発火しない問題の回避策。`bin/rl-usage-log` コマンドを新設し、全17スキルの preamble から self-report。PostToolUse matcher を Agent のみに変更 (#62, #63)

### Moved from SPEC.md Recent Changes
- 2026-04-02: v1.24.0 — **spec-keeper README.md 5層構造** — README.md を外部向け最外層として位置づけ（init/update/status 対応）→ 詳細は [1.24.0] セクション参照
- 2026-04-07: v1.26.0 — **bin/ 移行 (ADR-019)** — bareコマンド13個追加（`rl-audit` 等）、`scripts/lib/` に移設、hooks/common.py re-exporter化、pytest P0解消 → 詳細は [1.26.0] セクション参照
- 2026-04-12: v1.27.0 — **CC v2.1.94+ 統合** — `correction_detect.py` で `explicit`/`guardrail` 系 correction 検出時に `hookSpecificOutput.sessionTitle` を JSON 出力。`implement` / `rl-loop-orchestrator` SKILL.md に CC v2.1.98+ `Monitor` tool ガイド追記（sleep ポーリング代替）→ 詳細は [1.27.0] セクション参照
- 2026-04-13: **PostCompact hook** — Compact 後に checkpoint から作業コンテキスト（ブランチ・直近コミット・未コミットファイル）を systemMessage 注入。hooks/ 14個体制

## [1.27.0] - 2026-04-11

### Added
- **correction_detect.py: hookSpecificOutput.sessionTitle 出力**: CC v2.1.94+ の UserPromptSubmit フック仕様に対応。`explicit` / `guardrail` 系の correction（`remember:`, `don't ... unless` 等）を検出した際、`[{correction_type}] {message 抜粋}` 形式のセッションタイトルを JSON 出力する。plain-text trigger message との混在を避けるため、trigger 発火時は emit しない
- **implement / rl-loop-orchestrator: Monitor tool ガイド**: CC v2.1.98+ の `Monitor` tool を、長時間バックグラウンド subagent の進捗追跡手段として SKILL.md に明記（sleep ポーリング代替）

## [1.26.0] - 2026-04-07

### Added
- **bin/ ディレクトリ**: `rl-evolve`, `rl-audit`, `rl-discover`, `rl-prune`, `rl-reorganize`, `rl-reflect`, `rl-handover`, `rl-optimize`, `rl-loop`, `rl-backfill`, `rl-backfill-analyze`, `rl-backfill-reclassify`, `rl-audit-aggregate` の bare コマンドを追加。PATH に bin/ を追加すれば `python3 <PLUGIN_DIR>/skills/...` 形式の長いコマンド不要 ([ADR-019](docs/decisions/019-plugin-bin-directory-migration.md))

### Changed
- **ライブラリ再設計 (ADR-019)**: `hooks/common.py` のロジックを `scripts/lib/rl_common.py` に移設し、`hooks/common.py` は re-exporter に変更。`scripts/lib/` 配下に `audit.py`, `discover.py`, `prune.py`, `reorganize.py`, `remediation.py` を移設（元の場所は importlib shim に変更）。共通ロジック 30→38 モジュール
- **SKILL.md コマンド更新**: 全スキルの実行コマンドを `python3 <PLUGIN_DIR>/skills/...` から bare コマンド（`rl-audit` 等）に変更
- **pytest P0 解消**: `pytest.ini` に `--import-mode=importlib` を追加し、同名テストファイルのモジュール衝突を解消。1563 tests pass

## [1.25.0] - 2026-04-03

### Changed
- **リリース**: v1.22.2-v1.24.0 の変更を main にマージ（checkpoint セッション分離 / PermissionDenied hook / spec-keeper 5層構造）

## [1.24.0] - 2026-04-02

### Added
- **spec-keeper: README.md 管理対応（5層構造）**: README.md を外部向け（人間ファースト）の最外層として位置づけ。init で情報源に追加・存在しなければ生成提案、update で外部向け変化のみ README.md に反映、status で鮮度チェックを追加。README テンプレート（MVP積み上げ型・頻繁改善型）も同梱

## [1.23.0] - 2026-04-01

### Added
- **PermissionDenied hook**: CC v2.1.89 の新フックイベント対応。auto mode でのパーミッション拒否を errors.jsonl に `type:"permission_denied"` として記録し、discover/evolve でパーミッション設定の改善提案に活用
- **グローバルエージェント maxTurns 設定**: ambiguous-intent-resolver (15), updater-senior-engineer (20) に明示的な maxTurns を追加

### Changed
- **SKILL.md description 250文字対応**: CC v2.1.86 の `/skills` リスト表示 250文字上限に対応。6スキル（evolve-skill, generate-fitness, second-opinion, implement, release-notes-review, spec-keeper）の description を短縮
- **MEMORY.md 圧縮**: プロジェクト構造セクションからコード導出可能な実装詳細を削除（180→73行、60%削減）

## [1.22.2] - 2026-04-01

### Fixed
- **handover checkpoint セッション分離**: checkpoint.json がグローバル1ファイルだったため別プロジェクト・並行セッションのデータで汚染されていた問題を修正。`checkpoints/{session_id}.json` に分離し、`project_dir` フィールドで復元時にフィルタ。旧 checkpoint.json は後方互換で読み取り可能。48h TTL で自動 cleanup。closes #50

## [1.22.1] - 2026-03-31

### Added
- **evolve 通知スヌーズ機能**: `snooze_trigger(hours)` で通知を一時抑制。スヌーズ中は pending-trigger を配信せずファイルを保持。期限切れで自動解除、`clear_snooze()` で手動解除。closes #52

## [1.22.0] - 2026-03-31

### Added
- **implement スキル追加**: plan artifact → タスク分解 → 実装（Standard/Parallel）→ 計画準拠チェック → テレメトリ記録の構造化実装スキル。gstack plan artifact 連携（オプション）、usage.jsonl + growth-journal 記録、worktree 並列対応
- **implement backfill**: git log のリリースコミット間から実装セッションを推定し、テレメトリにバックフィル。冪等性保証付き

## [1.21.3] - 2026-03-31

### Fixed
- **deploy-lock description に PostToolUse lock 解放要件を追記**: デプロイ完了後に lock を自動解放する仕組みが必要であることを明記。lock 未解放による次回 deploy ブロック問題の防止

## [1.21.2] - 2026-03-31

### Added
- **kill-guard RECOMMENDED_ARTIFACT 追加**: deploy-lock 保持中のプロセス kill をブロックする独立エントリ。sys-bots 実運用フィードバックから追加

### Changed
- **worktree-parallel-work description 強化**: `git checkout -b` でのブランチ作成も worktree に誘導。feature-branch rule との PJ 上書き必要性を明記
- **deploy-lock を deploy コマンド専用に分離**: kill ガードは kill-guard エントリに委譲

## [1.21.1] - 2026-03-31

### Fixed
- **deploy-lock description 更新**: 実運用フィードバックを反映 — deploy コマンドだけでなく kill 系コマンドもガード対象であることを明記

## [1.21.0] - 2026-03-30

### Added
- **release-notes-review グローバル環境対応**: `~/.claude/` 配下の rules/skills/agents/settings hooks/memory もスキャン・健康診断できるように。`--env-only` で環境診断だけ実行可能。レポートは Part 1 (Release Notes) + Part 2 (Global Environment Health) の2セクション構成
- **spec-keeper プラグイン一本化**: グローバル版を廃止し、プラグイン版 `/rl-anything:spec-keeper` に統合。handover/discover のパス参照もプラグイン内に更新
- **gstack flow chain 動的化**: `~/.gstack/flow-chain.json` から audit の gstack ワークフロー分析を動的構築。ファイル不在時は fallback 値を使用

### Fixed
- **release-notes-review `--env-only` ガード**: `--env-only` 時に Step 5 バージョン記録をスキップ（リリースノート未確認時の誤記録防止）
- **adversarial review 対応**: phase 型チェック + テスト temp file 修正

### Removed
- **gstack-refine 全参照削除**: audit/discover/spec-keeper から gstack-refine 参照を削除

## [1.19.1] - 2026-03-31

### Fixed
- **handover corrections フィルタ**: `collect_handover_data()` が corrections.jsonl から読み込む際に `project_path` でフィルタリングし、別プロジェクトのデータ混入を防止 (#53)
- **handover usage フィルタ**: usage.jsonl のスキル使用記録も `project` フィールドでフィルタリング（corrections と同じバグパターン）(#53)
- **handover パス正規化**: project_path 比較に `Path.resolve()` を使用し、macOS のシンボリックリンク差異を安全に処理 (#53)
- **handover GitHub リポデフォルト Issue モード**: GitHub リポではフラグなしでもデフォルトで Issue モードを使用するよう変更。`is_github` フィールドをデフォルト出力に追加 (#53)
- **handover --issue 重複呼び出し**: `--issue` パスで `is_github_repo()` が二重に呼ばれていた問題を修正 (#53)

## [1.19.0] - 2026-03-27

### Added
- **handover Issue モード**: `--issue` フラグで GitHub Issue として引き継ぎノートを作成可能に。GitHub リポ検出時は自動提案

### Fixed
- **handover --project-dir cwd 伝播**: `_run_git()` に `cwd` パラメータを追加し、`--project-dir` が git コマンドの実行ディレクトリに正しく反映されるように修正 (#49)
- **synonym_verb テスト安定化**: LLM judge 実呼び出しを mock に変更し非決定的テストを修正

_SPEC.md Recent Changes から移動（既存エントリへの参照）:_
- _2026-03-26: v1.15.0 — [1.15.0] 参照_
- _2026-03-25: handover Deploy State — [Unreleased] 参照_
- _2026-03-27: v1.19.0 — handover Issue モード — [1.19.0] 参照_
- _2026-03-26: v1.18.0 — NFD Level System — [1.18.0] 参照_
- _2026-03-26: v1.17.2 — worktree 並行開発パターン提案 — [1.17.2] 参照_
- _2026-03-26: v1.16.0 — NFD Living Agent Identity — [1.16.0] 参照_

## [1.18.0] - 2026-03-26

### Added
- **NFD Level System**: env_score (0.0-1.0) を Lv.1-10 の 10段階レベル + 日英称号にマッピングする `growth_level.py` を追加。セッション greeting に `Lv.7 Experienced` 形式で表示
- **Fast Shipper trait**: personality_traits に「速攻派」を追加。workflows.jsonl の commit スキル使用頻度 > 2/session で判定
- **audit Growth Report にレベル表示**: `--growth` で env_score + Level + Phase を一覧表示。キャッシュに env_score/level/title を保存

### Fixed
- **η計算反転修正**: 結晶化効率 η が `events/targets` (値域 0-∞) だったのを `crystallized_rules/total_corrections` (0.0-1.0) に修正
- **evolve フェーズ降格防止**: evolve が coherence_score=0.0 でフェーズ判定→キャッシュ上書きしていた問題を修正。audit を唯一のキャッシュ更新権威に変更、evolve は journal 記録のみ
- **journal phase 精度向上**: evolve の emit_crystallization で phase をキャッシュからフォールバック取得するよう変更

### Changed
- **audit coherence_score 正確化**: `_build_growth_report()` が `compute_environment_fitness()` から実際の coherence_score を取得してフェーズ判定に使用

## [1.17.2] - 2026-03-26

### Added
- **worktree 並行開発パターン提案**: discover の RECOMMENDED_ARTIFACTS に `worktree-parallel-work`（stash+checkout 事故防止）と `deploy-lock`（同一環境への並行デプロイ防止）を追加。未導入 PJ に自動提案

## [1.17.1] - 2026-03-26

### Fixed
- **ルール行数カウント誤検出**: `count_content_lines()` が frontmatter 直後の空行をコンテンツ行としてカウントしていた問題を修正 (#47)
- **untagged_reference 分類精度向上**: CLAUDE.md Skills セクション記載スキルの除外 + コンテンツヒューリスティックによるユーザー呼び出し型スキル除外を追加 (#47)

## [1.17.0] - 2026-03-26

### Added
- **spec-keeper スキル同梱**: SPEC.md + ADR 管理スキルを rl-anything プラグインに同梱。`/rl-anything:spec-keeper init` でプロジェクトの仕様全体像を初期化、`update` で最新化
- **Progressive Disclosure レイヤーシステム**: SPEC.md の段階的開示対応。PJ 規模に応じて L1（単一ファイル ~100行）/ L2（hot + cold 2層構造）を自動昇格。Context rot 防止
- **SPEC.md L2 昇格**: rl-anything 自身の SPEC.md を L2 に昇格 — Architecture 詳細を spec/architecture.md に分離し hot 層を 166行→95行に圧縮

## [1.16.0] - 2026-03-26

### Added
- **NFD Growth Engine**: NFD 論文 (arXiv:2603.10808) の Spiral Development Model を実装 — 環境の成熟度を 4 フェーズ（Bootstrap / Initial Nurturing / Structured Nurturing / Mature Operation）で自動判定し、進捗率を可視化
- **結晶化イベント記録**: evolve/reflect が rule/skill を生成・更新するたびに growth-journal.jsonl に結晶化イベントを記録。成長ストーリーの素材に
- **セッション開始時 Growth greeting**: InstructionsLoaded hook 拡張 — セッション開始時に `GROWTH: structured_nurturing 72%` のようなフェーズ情報を stdout 出力（LLM コストゼロ、キャッシュ読み取りのみ）
- **audit --growth**: Growth Report セクション追加 — フェーズ・進捗率・結晶化ログ・環境プロファイル（得意分野・性格特性）・成長ストーリーを一画面表示
- **環境プロファイル**: テレメトリから環境の個性を自動抽出 — 5 つの性格特性（慎重派・整理好き・速攻派・フィードバッカー・探検家）をデータドリブンで判定
- **git log backfill**: 過去の evolve/reflect/remediation コミットから結晶化イベントを復元。既存ユーザーが即座に正しいフェーズ表示を得られる
- **growth_display userConfig**: プラグイン設定で Growth greeting の表示/非表示を制御可能（default: true）

## [1.15.0] - 2026-03-26

### Added
- **ファイル変更の即時検知**: CLAUDE.md や SKILL.md を編集すると、セッション終了を待たずに `/rl-anything:audit` を提案。rules ファイルも watchPaths で自動登録（CC v2.1.83 FileChanged hook）
- **MEMORY.md 25KB ガード**: CC v2.1.83 の 25KB 切り詰め上限を事前検知。audit と bloat_check がバイトサイズを監視し、80%（20KB）到達で警告
- **プラグイン設定の対話化**: plugin enable 時に evolve/audit の頻度やクールダウンを設定可能に。6項目の userConfig（CC v2.1.83 manifest.userConfig）

### Changed
- **トリガー設定の3層マージ**: デフォルト → evolve-state.json → userConfig（環境変数）の優先順位で設定を解決。明示的にセットされた値のみ上書きし、既存設定を潰さない
- **auto_trigger ゲート**: session_summary と file_changed の両方で userConfig の auto_trigger=false を尊重

## [1.14.2] - 2026-03-25

### Fixed
- **SPEC.md**: 構造突合リカバリーで未記載コンポーネントを修正 — hooks 7→11, scripts/lib 25+→27, fitness 7→8

## [Unreleased]

### Changed
- **handover**: checkpoint.json 優先で重複データ収集を廃止 — テンプレートを判断記録 + 次アクションに特化（Summary/Related Files 廃止）。closes #43

### Added
- **handover**: Deploy State セクション追加 — デプロイ状態を構造化記録し、セッション復元時に Deploy State / Next Actions を優先表示。`--deploy-state` CLI で machine-readable アクセスも提供。closes #44
- **second-opinion**: Claude Agent によるセカンドオピニオン機能 — codex 不要で Agent ツールのみで動作。startup/builder/general 3モード対応。gstack office-hours Phase 3.5 の codex 代替として、または汎用的に利用可能。closes #42
- **critical-instruction-compliance**: スキルに書いた「必ず守れ」がちゃんと守られる — MUST/禁止等の重要指示を自動抽出し、穏やかな表現にリフレーズして注入。ユーザーの修正（corrections）とスキル指示を突合して違反を自動検出、pitfall に登録して次から守るよう自動学習。対立動詞検出（move↔delete）+ LLM Judge の2段階マッチング。closes #39
- instruction compliance — スキル指示の遵守保証サイクル（Extract→Inject→Detect→Learn 4フェーズ、対立動詞+LLM Judge 2段階マッチング）。closes #39
- **remediation**: 修正の独立検証 — auto_fixable な修正に対してヒューリスティクスベースのダブルチェックを実施。見出し保持・コードブロック対応・空ファイル・行数制限を自動検証し、FP 率を低減
- **remediation**: 12 パターンの FP 自動除外 — テストファイル・アーカイブパス・外部 URL・コードブロック内参照等を false positive として自動分類。`fp_excluded` カテゴリで明示的に追跡
- **remediation**: 原則ベース自動昇格 — completeness/pragmatic/DRY/explicit_over_clever の 4 原則で、proposable な修正を auto_fixable に自動昇格。gstack /autoplan のパターンを移植
- **layer_diagnose**: Skills セクションの synonym マッチ — "Key Skills", "Available Skills", "スキル" 等のバリエーションを自動認識。missing_section の false positive を削減
- **evolve**: 環境規模の自動判定 — スキル/ルール数に応じて small/medium/large を判定し、evolve/audit の走査深度を自動調整。大規模環境でのパフォーマンス改善
- **fitness**: 全 fitness モジュールの閾値を `config.py` に集約 — 1箇所で全閾値を管理可能に。各モジュールは config.py からの import + フォールバックで後方互換
- **environment**: 動的重み計算 — 利用可能な軸に応じて重みを自動正規化。ハードコード 4 パターンを 1 つの `_normalize_weights()` に置換。skill_quality を 4 軸目として統合
- **constitutional**: gstack /cso セキュリティ監査との連携 — /cso 実行結果があれば constitutional score に security 軸としてブレンド。結果がなければ graceful degradation
- **audit**: gstack /retro global とのクロスプロジェクト連携 — `--cross-project` フラグで複数プロジェクトのテレメトリを集約表示。/retro global の結果を自動参照

## [1.13.0] — 2026-03-22

### SPEC.md から移動（Recent Changes ローテーション）
- 2026-03-24: gstack v0.10-v0.11 改善パターン6項目移植 — 独立検証、FP排除(12条件)、規模適応、fitness config.py集約、動的重み、/cso×fitness連携、/retro×audit cross-project、原則ベース昇格
- 2026-03-23: handover に SPEC.md 同期ステップ追加（`/spec-keeper update` を自動実行）
- 2026-03-22: v1.13.0 — 検証系スキルのテレメトリ非依存昇格
- 2026-03-22: v1.12.0 — handover スキル追加 + OpenSpec→gstack 移行 Phase 1-2
- 2026-03-20: agent-brushup スキル追加（品質診断 + upstream 監視）

### Added
- **evolve-skill**: 検証系スキル（verify/validate/check/qa等）はテレメトリが少なくても suitability を medium に自動昇格 — 失敗インパクトが大きい検証系は常に自己進化を推奨
- **handover**: Step 4 に SPEC.md 同期を追加 — SPEC.md があれば `/spec-keeper update` を自動実行し、次セッションの Next Actions を最新化

## [1.12.1] — 2026-03-22

### Fixed
- **handover**: PreCompact 提案のクールダウン（1h）を削除 — compaction 自体がレートリミッターなので毎回提案する

## [1.12.0] — 2026-03-22

### SPEC.md から移動（Recent Changes ローテーション）
- 2026-03-20: effort frontmatter 全15スキルに追加
- 2026-03-18: rl-loop --evolve フラグ + evolve-skill 独立コマンド
- 2026-03-18: Superpowers 知見 cherry-pick（合理化防止テーブル + CSO）
- 2026-03-15: pitfall ライフサイクル自動化 + プラグインスキル編集保護
- 2026-03-13: verification knowledge catalog + side-effect 検出
- 2026-03-09: self-evolution + auto-evolve/compression trigger

### Added
- **handover**: 新スキル `/rl-anything:handover` — セッション作業を構造化ノート（.claude/handovers/）に書き出し、別セッションへ引き継ぐ
- **handover**: PreCompact hook でコンテキスト圧縮前に handover を自動提案（1h クールダウン）
- **handover**: SessionStart hook で最新 handover ノートをプレビュー表示（48h staleness）
- **gstack**: audit の Workflow Analytics を OpenSpec → gstack に移行（plan→refine→ship→document→spec→retro ファネル）
- **gstack**: discover の RECOMMENDED_ARTIFACTS に gstack ツール5件追加（gstack-flow-chain, living-spec-awareness, spec-keeper, ship, gstack-refine）
- **gstack**: aggregate_plugin_usage に gstack スキル分類追加

### Removed
- **openspec**: OpenSpec スキル5件を削除（propose/apply/explore/verify/archive）— 新規ユーザーに openspec コマンドが表示されなくなる

### Added
- **agent-brushup**: 新スキル `/rl-anything:agent-brushup` — エージェント定義（~/.claude/agents/）の品質診断・改善提案・新規作成・削除候補提示
- **agent_quality**: `scan_agents()` — global/project エージェント走査（重複時 project 優先）
- **agent_quality**: `check_quality()` — 7項目品質チェック + 6アンチパターン検出 + 6ベストプラクティス照合
- **agent_quality**: `check_upstream()` — agency-agents リポジトリ更新監視（gh api、graceful degradation）
- **observe**: Agent ツール使用時に `agent_name` フィールドを usage.jsonl に記録
- **subagent_observe**: SubagentStop イベントに `agent_name` フィールドを subagents.jsonl に記録
- **skills**: 全15スキルに `effort` frontmatter 追加（CC v2.1.80対応、low/medium/high 3段階）
- **effort_detector**: `infer_effort_level()` — スキル特性から effort レベルを6段階ヒューリスティクスで推定（disable-model-invocation/Agent/行数/キーワード）
- **effort_detector**: `detect_missing_effort_frontmatter()` — プロジェクトスキル走査で effort 未設定を検出+レベル提案
- **issue_schema**: `MISSING_EFFORT_CANDIDATE` 定数 + `make_missing_effort_issue()` factory 関数
- **audit**: `collect_issues()` に effort 未設定スキル検出を統合
- **remediation**: `fix_missing_effort()` / `_verify_missing_effort()` — FIX_DISPATCH/VERIFY_DISPATCH 登録

### Fixed
- **marketplace.json**: `claude plugin validate` で未サポートの `$schema`/`description` を除去

## [1.11.0] - 2026-03-19

### Added
- **tool_usage_analyzer**: `extract_tool_calls_by_session()` — セッションtranscriptからセッション単位でBashコマンドを抽出（recencyフィルタ付き）
- **tool_usage_analyzer**: `detect_stall_recovery_patterns()` — Long→Investigation→Recovery→Longの停滞パターンをセッション横断で検出（confidence算出付き）
- **tool_usage_analyzer**: `stall_pattern_to_pitfall_candidate()` — 停滞パターンからpitfall candidate変換（Jaccard重複排除統合）
- **issue_schema**: `STALL_RECOVERY_CANDIDATE` 定数 + `make_stall_recovery_issue()` factory関数
- **discover**: `run_discover()` に `stall_recovery_patterns` フィールド追加
- **discover**: `RECOMMENDED_ARTIFACTS` に `process-stall-guard` エントリ追加
- **evolve**: Diagnose ステージに stall_recovery_patterns → issue_schema 変換を統合
- **evolve**: レポート Step 10.5「Process Stall Patterns」セクション追加
- **workflow_checkpoint**: `is_workflow_skill()` — frontmatter `type: workflow` 優先 + ヒューリスティクスフォールバックによるワークフロースキル判定
- **workflow_checkpoint**: `CHECKPOINT_CATALOG` — 4カテゴリ（infra_deploy/data_migration/external_api/secret_rotation）のチェックポイントテンプレート + `_CHECKPOINT_DETECTION_DISPATCH` による detection_fn 解決
- **workflow_checkpoint**: `detect_checkpoint_gaps()` — テレメトリ（corrections/errors）から `last_skill` フィルタでチェックポイント不足を検出（タイムアウト保護付き）
- **issue_schema**: `WORKFLOW_CHECKPOINT_CANDIDATE` 定数 + `make_workflow_checkpoint_issue()` factory 関数
- **remediation**: `fix_workflow_checkpoint()` / `_verify_workflow_checkpoint()` — FIX_DISPATCH/VERIFY_DISPATCH 登録
- **discover**: `run_discover()` に `workflow_checkpoint_gaps` フィールド追加（ワークフロースキル走査）
- **evolve**: Diagnose ステージに workflow_checkpoint_gaps → issue_schema 変換を統合
- **evolve**: レポート Step 10.4「Workflow Checkpoint Gaps」セクション追加
- **verification_catalog**: `detect_iac_project()` — IaCプロジェクト判定ゲート（CDK/Serverless/SAM/CloudFormation対応）
- **verification_catalog**: `detect_cross_layer_consistency()` — コード↔IaC間クロスレイヤー整合性検出（環境変数参照・AWS SDK使用 + detected_categories）
- **verification_catalog**: `cross-layer-consistency` カタログエントリ + content-aware install check
- **frontmatter**: `count_content_lines()` — YAML frontmatter を除外したコンテンツ行数カウント
- **path_extractor**: `extract_paths_outside_codeblocks()` 共通モジュール化（audit.py から抽出）
- **reflect_utils**: `PathsSuggestion` dataclass + `suggest_paths_frontmatter()` — correction テキストから paths frontmatter グロブパターンを自動提案
- **reflect**: `route_corrections()` に paths_suggestion 付与（globs 代替注記付き）
- **optimize**: 最適化後の paths frontmatter 提案表示
- **remediation**: `generate_proposals()` が rule_candidate issue に `paths_suggestion` フィールド付加

### Changed
- **line_limit**: `check_line_limit()` / `suggest_separation()` がルールファイルの frontmatter 除外カウントに対応
- **audit**: `check_line_limits()` がルールの frontmatter 除外カウントに対応
- **prune**: `detect_dead_globs()` を `parse_frontmatter()` ベースにリファクタ、`paths` / `globs` 両キー対応

## [1.10.0] - 2026-03-18

### Added
- **skill_evolve**: `assess_single_skill()` — 単一スキルの自己進化適性判定（5軸スコアリング + アンチパターン検出）
- **skill_evolve**: `apply_evolve_proposal()` — SKILL.md セクション追記 + references/pitfalls.md 作成 + バックアップの共通関数
- **evolve-skill**: 独立コマンド `/rl-anything:evolve-skill` — 特定スキルに自己進化パターンをピンポイント組み込み
- **rl-loop**: `--evolve` フラグ + Step 5.5 `_try_evolve_skill()` — 最適化後に自己進化パターン組み込みを提案

### Changed
- **remediation**: `fix_skill_evolve()` を `apply_evolve_proposal()` 呼び出しにリファクタ（DRY 改善、3箇所から共通関数を利用）

## [1.9.0] - 2026-03-18

### Added
- **hooks**: 長時間コマンド検出による subagent 移譲提案 hook（deploy/build/test-suite/install/push/migration の6カテゴリ、同一カテゴリ1セッション1回制限）
- **pitfall_manager**: 合理化防止テーブル自動生成 — corrections.jsonl からスキップパターン検出→テレメトリ突合テーブル生成（`detect_rationalization_patterns` + `generate_rationalization_table`）
- **fitness**: skill_quality に CSO (Claude Search Optimization) 8軸目追加 — description 要約ペナルティ/トリガー語ボーナス/行動促進ボーナス/長さペナルティ
- **verification_catalog**: evidence-before-claims パターン追加 — 「証拠提示義務」の自動検出・未導入PJへの提案
- **discover**: RECOMMENDED_ARTIFACTS に evidence-before-claims エントリ追加
- **evolve**: Housekeeping Phase 4.6 に合理化テーブル生成統合 + レポートに合理化防止テーブルセクション
- **rules**: `verify-before-claim.md`（証拠提示義務）、`root-cause-first.md`（根本原因調査優先）追加

## [1.8.0] - 2026-03-18

### Added
- **hooks**: `StopFailure` hook — APIエラー（rate limit/認証失敗等）によるセッション中断を errors.jsonl に記録
- **hooks**: `InstructionsLoaded` hook — CLAUDE.md/rules ロードを sessions.jsonl に記録（flag file dedup + stale TTL ガード）
- **hooks**: observe.py の Agent 記録に `agent_id` フィールド追加（event payload 由来）
- **hooks**: 全テレメトリレコード（usage/errors/subagents）に `worktree` 情報（name/branch）を追加
- **hooks**: `common.py` に `extract_worktree_info()` ヘルパー + `INSTRUCTIONS_LOADED_FLAG_PREFIX`/`STALE_FLAG_TTL_HOURS` 定数
- **agents**: rl-scorer に `maxTurns: 15` + `disallowedTools: [Edit, Write, Bash]` でコスト制御・安全性向上

### Changed
- **hooks**: `DATA_DIR` が `CLAUDE_PLUGIN_DATA` 環境変数を優先し、未設定時に `~/.claude/rl-anything/` にフォールバック

## [1.7.0] - 2026-03-16

### Added
- **skill_triage**: テレメトリ+trigger evalで CREATE/UPDATE/SPLIT/MERGE/OK の5択スキルライフサイクル判定（Jaccard階層クラスタリング、D10 confidence計算式）
- **trigger_eval_generator**: sessions.jsonl+usage.jsonl → skill-creator互換 evals.json 自動生成（near-miss優先、confidence_weight付き）
- **issue_schema**: `SKILL_TRIAGE_CREATE`/`UPDATE`/`SPLIT`/`MERGE` 定数 + `make_skill_triage_issue()` factory関数
- **evolve**: Diagnose Phase 2.6 に skill triage 統合（discover後、audit前）
- **discover**: `detect_missed_skills()` に `eval_set_path`/`eval_set_status` フィールド追加

## [1.6.0] - 2026-03-16

### Added
- **remediation**: `fix_stale_memory()` — MEMORY.md staleエントリの自動削除（FIX_DISPATCH登録）
- **remediation**: `fix_pitfall_archive()` — pitfall Cold層（Graduated/Candidate/New）の自動アーカイブ（cap_exceeded/line_guard対応）
- **remediation**: `fix_split_candidate()` — LLMによるスキル分割案提示（proposable、ファイル変更なし）
- **remediation**: `fix_preflight_scriptification()` — Pre-flightスクリプト化テンプレート提案（proposable）
- **remediation**: VERIFY_DISPATCH に cap_exceeded/line_guard/split_candidate/preflight_scriptification を追加
- **remediation**: `DUPLICATE_PROPOSABLE_SIMILARITY`/`DUPLICATE_PROPOSABLE_CONFIDENCE` 定数 — duplicate のsimilarityベース proposable 昇格
- **issue_schema**: `SPLIT_CANDIDATE` 定数 + `make_split_candidate_issue()` factory関数
- **pitfall_manager**: `CAP_EXCEEDED_CONFIDENCE`/`PREFLIGHT_MATURITY_RATIO` 定数
- **pitfall_manager**: `pitfall_hygiene()` に `issues`/`preflight_candidates` フィールド追加
- **reorganize**: `run_reorganize()` 出力に `issues` フィールド追加（split_candidates → issue_schema変換）

### Changed
- **pitfall_manager**: Cold層定義を拡張（Graduated + Candidate → + New）、`get_cold_tier()` 更新
- **remediation**: `compute_confidence_score()` で duplicate を similarity ベースに変更（sim≥0.75→confidence 0.60→proposable）
- **openspec-archive-change**: タスク完了率チェック追加（`ARCHIVE_COMPLETION_THRESHOLD = 0.80`、80%未満で警告）
- **evolve SKILL.md**: ファネル分析から verify フェーズを除外（propose→refine→apply→archive の4段階）

### Removed
- **openspec-verify-change**: スキル廃止（利用率7%、archive にタスク完了率チェック統合）

### Previous Unreleased
- **rl-scorer**: オーケストレーター(haiku) + 3サブエージェント並列構成に変更（technical/structural=haiku, domain=sonnet）。評価精度向上 + コスト同等
- **run-loop.py**: `score_variant()` / `get_baseline_score()` を ThreadPoolExecutor で3軸並列スコアリングに改修
- **evolve**: Step 5.6 /simplify ゲート — remediation で .py ファイル変更時に自動品質チェック（後方互換あり）
- **run-loop.py**: `_parallel_score()` / `_score_single_axis()` 関数追加、`AXIS_WEIGHTS` 定数追加

## [1.5.0] - 2026-03-15

### Added
- **pitfall_manager**: pitfall ライフサイクル自動化 — corrections/errors からの自動検出、SKILL.md 統合済み判定、TTL アーカイブ、行数ガード、Pre-flight テンプレート提案 (#30)
  - `extract_pitfall_candidates()`: corrections/errors.jsonl から pitfall Candidate を自動抽出（D6 重複排除、Occurrence-count increment）
  - `detect_integration()`: SKILL.md/references セクション単位 Jaccard 突合で統合済み判定
  - `detect_archive_candidates()`: Graduated TTL（30日）+ Active stale エスカレーション（9ヶ月）
  - `execute_archive()`: 指定タイトルの pitfall を pitfalls.md から削除
  - `suggest_preflight_script()`: Root-cause カテゴリ別テンプレート解決（action/tool_use/output/generic）
  - `_compute_line_guard()`: PITFALL_MAX_LINES（100行）超過時に Cold 層から削除候補生成
  - `extract_root_cause_keywords()`: 「—」分割 → ストップワード除外のキーワード抽出
- **skill_evolve**: 5定数追加（INTEGRATION_JACCARD_THRESHOLD, GRADUATED_TTL_DAYS, STALE_ESCALATION_MONTHS, PITFALL_MAX_LINES, ERROR_FREQUENCY_THRESHOLD）
- **discover**: `run_discover()` に pitfall_candidates 統合（corrections/errors → extract_pitfall_candidates）
- **templates**: `skills/evolve/templates/preflight/` — Pre-flight スクリプトテンプレート 4種（action.sh, tool_use.sh, output.sh, generic.sh）
- **skill_origin**: `scripts/lib/skill_origin.py` — プラグイン由来スキルの origin 判定・編集保護・代替先提案モジュール
  - `classify_skill_origin()`: installed_plugins.json + パスベースのハイブリッド判定（mtime cache invalidation）
  - `is_protected_skill()`: plugin origin のスキルを編集保護対象と判定
  - `suggest_local_alternative()`: 保護スキルのプロジェクト側代替パス（references/pitfalls.md）を提案
  - `generate_protection_warning()`: 保護スキルへの編集警告メッセージ生成
  - `format_pitfall_candidate()`: pitfall_manager Candidate フォーマット生成
  - graceful degradation: 不正JSON/未知version/存在しないパスへの安全なフォールバック
- **reflect**: `suggest_claude_file()` に last-skill コンテキスト層を追加（位置6: always/never 後、frontmatter paths 前）
  - `_resolve_skill_references_path()`: last_skill のスキル references/ パス解決（保護スキルはローカル代替先にリダイレクト）
  - `LAST_SKILL_CONFIDENCE = 0.88` 定数追加
- **remediation**: `classify_issue()` に保護スキルチェック追加 — 保護スキルへの修正は proposable に降格 + `protection_warning` 付与
- **discover**: plugin_summary に `protected: True` フィールド追加

### Changed
- **pitfall_hygiene**: 返却値に `graduation_proposals`, `archive_candidates`, `codegen_proposals`, `line_count` フィールド追加
- **audit**: `_load_plugin_skill_map()`, `classify_artifact_origin()`, `classify_usage_skill()` を `skill_origin.py` に委譲（後方互換ラッパーとして残存）

## [1.4.0] - 2026-03-15

### Added
- **release-notes-review**: リリースノート分析 & 適用提案スキル — Claude Code リリースノートをPJ環境と突合し、優先度別レポート + OpenSpec change 提案
- **line_limit**: `suggest_separation()` — rule 行数超過時に references/ への分離提案を生成（SeparationProposal dataclass、衝突回避）
- **optimize**: gate 不合格（line_limit_exceeded）時に分離提案メッセージを表示、result に `suggestion` フィールド追加
- **remediation**: `fix_line_limit_violation()` が rule ファイルは分離モード（references/ に詳細移動 + 要約書き換え）、skill は従来 LLM 圧縮
- **reflect**: `route_corrections()` で反映先 rule の行数チェック、超過時 `line_limit_warning` 付与
- **openspec**: adopt-claude-code-features 仕様策定完了 — Claude Code v2.1.x 新機能（context:fork, ${CLAUDE_SKILL_DIR}, agent model, skill hooks, PostCompact, auto-memory協調, worktree isolation, effort level, mtime staleness）の適用設計 9 Decision + 8 delta spec

## [1.3.0] - 2026-03-13

### Added
- **issue_schema**: `scripts/lib/issue_schema.py` — モジュール間 issue データ受け渡しの共有スキーマ定数 + factory 関数
  - issue type 定数（TOOL_USAGE_RULE_CANDIDATE, TOOL_USAGE_HOOK_CANDIDATE, SKILL_EVOLVE_CANDIDATE）
  - detail フィールド定数（RULE_FILENAME, HOOK_SCRIPT_PATH, SE_SKILL_NAME 等）
  - `make_rule_candidate_issue()`, `make_hook_candidate_issue()`, `make_skill_evolve_issue()` factory 関数
- **evolve**: skill_evolve assessment を Phase 3.4 に統合（remediation の前に実行）
- **discover**: RECOMMENDED_ARTIFACTS に `commit-version`・`claude-md-style`・`commit-skill` エントリ追加（未導入PJへの提案）
- **verification_catalog**: `scripts/lib/verification_catalog.py` — 検証知見カタログ（detect_verification_needs + detect_data_contract_verification）
  - VERIFICATION_CATALOG 定義、閾値定数（DATA_CONTRACT_MIN_PATTERNS=3, DETECTION_TIMEOUT_SECONDS=5, MAX_CATALOG_ENTRIES=10）
  - discover に verification_needs 検出統合、evolve Phase 3.5 に issue 変換
  - remediation に verification_rule_candidate ハンドラ追加（fix/verify/rationale/proposals）
  - issue_schema に VERIFICATION_RULE_CANDIDATE + make_verification_rule_issue() factory 追加
- **verification_catalog**: `side-effect-verification` エントリ追加（DB操作/MQ/外部API の3カテゴリ副作用検出）
  - テストファイル除外フィルタ、detected_categories 別フィールド、content-aware インストール済みチェック
  - reflect_utils に corrections ベースの副作用パターン検出 + ルーティング追加（優先度3、FP抑制複合パターン）
  - remediation の rationale テンプレートを汎用化

### Fixed
- **evolve**: discover → remediation のデータフロー断絶を修正（issue 変換のフィールド名不一致）
  - rule_candidate: path/commands/alternatives/count/rule_content → filename/target_commands/alternative_tools/total_count/content
  - hook_candidate: path/content → script_path/script_content/settings_diff/target_commands/total_count
- **tool_usage_analyzer**: hook テンプレートの出力を JSON stdout から `exit 2` + stderr に変更（Claude Code Hooks Guide 準拠）

### Changed
- **remediation**: 全 issue type 比較・detail フィールド参照を issue_schema 定数に統一
- **test**: remediation / skill_evolve テストの issue dict を定数参照 + factory 関数に移行

## [1.2.0] - 2026-03-13

### Added
- **evolve**: Mitigation Trend — ツール使用分析のトレンド表示（↑↓→ 件数差・増減率%・pp差）
  - evolve-state.json に `tool_usage_snapshot` を保存、前回との差分を算出
- **evolve**: Bash 割合に目標閾値（≤40%）と達成/未達ラベルを併記
  - BUILTIN_THRESHOLD/SLEEP_THRESHOLD も閾値表示
- **remediation**: Reference Type Auto-fix — `untagged_reference_candidates` の自動修正
  - `update_frontmatter()` で YAML frontmatter に `type: reference` を追加
  - confidence 0.90 で proposable 分類
- **remediation**: line_limit_violation の auto_fixable 拡張（1行超過 → confidence 0.95）
  - LLM 1パス圧縮による自動修正 + 失敗時 proposable 降格フォールバック
- **fitness_evolution**: Bootstrap モード（5-29件: 簡易分析、0-4件: insufficient_data）

### Changed
- **prune**: Step 3 の2段階承認フロー（一括方針選択→個別選択）を廃止し、最初から個別レビューに変更
  - 各スキルの SKILL.md を読み取り、4観点（未使用の背景/今後の使用可能性/重複・統合/参照価値）の分析テキストを出力
  - 1-2件目: アーカイブ/維持/後で判断、3件目以降: アーカイブ/維持/残り全てスキップ
  - SKILL.md Read 失敗時のフォールバック動作を追加
  - Step 2 の推薦ラベル最終判定を Step 3 の個別レビュー内で実行する形に整理

## [1.1.0] - 2026-03-13

### Added
- **discover**: evolve Step 10.2 の mitigation-awareness 機能
  - `RECOMMENDED_ARTIFACTS` に `recommendation_id` + `content_patterns` フィールド拡張
  - `sleep-polling-guard` エントリ新規追加（sleep ポーリング検出）
  - `detect_installed_artifacts()` が `mitigation_metrics`（mitigated/recent_count/content_matched）を返却
- **tool_usage_analyzer**: `check_artifact_installed()` 汎用対策検出関数
  - hook/rule 存在チェック + content_patterns 正規表現マッチ
  - 閾値定数: `BUILTIN_THRESHOLD=10`, `SLEEP_THRESHOLD=20`, `BASH_RATIO_THRESHOLD=0.40`, `COMPLIANCE_GOOD_THRESHOLD=0.90`

### Changed
- **evolve**: Step 10.2 のツール使用改善セクションを対策状態に応じた表示切替に更新
  - 対策済み → 「対策済み (artifacts) — 直近 N 件検出」
  - 未対策 → 従来通り件数と改善提案
  - 全対策済みかつ検出ゼロ → 1行表示
  - 閾値をハードコードからモジュール定数参照に移行

## [1.0.7] - 2026-03-11

### Added
- **discover**: global scope の rule/hook 自動提案機能 (#26)
  - `tool_usage_analyzer` に `generate_rule_candidates()` / `generate_hook_template()` / `check_hook_installed()` 追加
  - `RECOMMENDED_ARTIFACTS` に `avoid-bash-builtin`（rule + PreToolUse hook）追加
  - `detect_installed_artifacts()` で導入済みアーティファクトのステータス表示
- **remediation**: global scope を `proposable` に昇格（`manual_required` → ユーザー承認付き提案へ）
  - `fix_global_rule()` / `fix_hook_scaffold()` を FIX_DISPATCH に追加
  - `tool_usage_rule_candidate` / `tool_usage_hook_candidate` の confidence_score・rationale・proposals 対応

## [1.0.6] - 2026-03-11

### Fixed
- **evolve**: Step 10 推奨アクションが LLM にスキップされる問題を修正
  - 各サブステップを無条件出力に変更（該当なしでも「問題なし」等を表示）
  - セクション見出しに「スキップ厳禁」を明記

## [1.0.5] - 2026-03-11

### Added
- **evolve**: dry-run レポートに「推奨アクション」セクション（Step 10）追加
  - 10.1: reflect 未処理件数の警告と実行推奨
  - 10.2: Built-in 代替可能な Bash コマンド・sleep パターン・Bash 割合の改善提案
  - 10.3: Remediation の auto_fixable / manual_required サマリ

## [1.0.4] - 2026-03-11

### Fixed
- **semantic_detector**: フォールバックを `is_learning=False`（全件除外）→ `is_learning=True`（パススルー）に修正 (#25)
  - partial success 対応: LLM が一部のみ返却時、index マッチングで成功分を適用し残りをパススルー
  - validate_corrections の例外フォールバックも同様に修正
- **discover**: `load_claude_reflect_data()` に `reflect_status == "pending"` フィルタ追加 (#25)
  - evolve の reflect_data_count と reflect の認識を一致させる
- **optimize**: `last_skill` が None の場合の AttributeError を修正 (#24)

## [1.0.3] - 2026-03-09

### Added
- **save_state**: PreCompact hook で作業コンテキスト（git branch/log/status）を checkpoint.json に保存 (#17)
  - 定数: `_MAX_UNCOMMITTED_FILES=30`, `_MAX_RECENT_COMMITS=5`, `_GIT_TIMEOUT_SECONDS=2`
  - 合計 3.5s タイムアウトガードで hook 5000ms 制限内に収束
- **restore_state**: SessionStart hook で committed/uncommitted 分離サマリーを stdout 出力 (#17)
  - work_context なし checkpoint の後方互換性維持
- **CLAUDE.md**: Compaction Instructions セクション追加（完了タスク/スキル結果/変更ファイル/最後の指示）

## [1.0.2] - 2026-03-09

### Fixed
- **diagnose**: FP 4パターン修正 (#23)
  - stale_ref: 数値パターン除外、ファイル位置基準の相対パス解決、不在トップレベルディレクトリ除外
  - orphan_rule: `.claude/rules/` auto-load のため廃止（coherence Efficiency 軸からも削除）
  - claudemd_missing_section: セクション名マッチを `.*[Ss]kills?\b` に柔軟化（prefix 付き対応）
  - line_limit: CLAUDE.md を warning only 化、project rule 5行制限、global rule 3行維持

### Changed
- **coherence**: Efficiency 軸から orphan_rules チェックを削除
- **line_limit**: `MAX_PROJECT_RULE_LINES=5`、`CLAUDEMD_WARNING_LINES=300` 追加
- **environment**: orphan_rules 廃止に伴い constitutional が有効になるケースの期待値対応

## [1.0.1] - 2026-03-09

### Fixed
- **optimize**: SKILL.md・plugin.json・marketplace.json 等の旧GA（遺伝的アルゴリズム）記述を DirectPatchOptimizer/直接パッチ最適化に統一 (#22)

## [1.0.0] - 2026-03-09

### BREAKING CHANGES
- **evolve**: 3ステージ構成の全レイヤー自律進化パイプライン完成（Diagnose→Compile→Housekeeping）
  - v0.x 系の evolve 出力フォーマットとの互換性なし（phases 構造が大幅変更）

### Added
- **environment-fitness**: coherence+telemetry+constitutional 3層ブレンド統合 Environment Fitness (#15)
  - Coherence Score: 構造的整合性4軸（Coverage/Consistency/Completeness/Efficiency）
  - Telemetry Score: テレメトリ駆動3軸（Utilization/Effectiveness/Implicit Reward）
  - Constitutional Score: 原則×4レイヤーの LLM Judge 評価 + Chaos Testing
- **all-layer-compile**: 全レイヤー（Rules/Memory/Hooks/CLAUDE.md）の自動修正・提案生成 (#16)
  - FIX_DISPATCH/VERIFY_DISPATCH による全レイヤー dispatch
  - confidence_score/impact_scope ベースの動的3カテゴリ分類
- **self-evolution**: パイプライン自己改善ループ (#21)
  - pipeline_reflector: trajectory分析・EWA calibration・adjustment proposals
  - trigger_engine: FP蓄積+承認率低下トリガー追加
  - evolve Phase 6: self-evolution フェーズ統合
  - audit `--pipeline-health`: remediation-outcomes.jsonl 集計（LLM不使用）
  - remediation: extended metadata + calibration override
- **auto-evolve-trigger**: セッション終了・corrections蓄積時の自動 evolve/audit 提案 (#21)
- **auto-compression-trigger**: bloat_check() ベースの肥大化自動検出トリガー (#21)

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
