## Context

rl-anything プラグインのスキルは `installed_plugins.json` 経由でダウンロードされ、`.claude/skills/` に配置される。現在これらのスキルとユーザー作成スキルの区別はパスベース判定（`audit.py:classify_artifact_origin()`）で行われているが、編集保護の仕組みは存在しない。

reflect の知見ルーティング（`suggest_claude_file()`）は8層メモリ階層で動作するが、corrections の `last_skill` フィールドは現在ルーティング判定に使用されておらず、キーワードマッチのみで宛先を決定している。

## Goals / Non-Goals

**Goals:**
- プラグイン由来スキルの origin を判定し、discover/reflect/remediation で編集保護を適用する
- reflect の知見ルーティングで `last_skill` コンテキストを優先し、キーワードバイアスを軽減する
- 既存インフラ（`classify_artifact_origin()`, `installed_plugins.json`, frontmatter）を最大限活用する

**Non-Goals:**
- SKILL.md への `source` frontmatter 自動付与（plugin install の仕組みは Claude Code 側の責務）
- スキル編集の物理的ブロック（hook で write を拒否する等）— 警告+代替提案に留める
- reflect 以外のスキル（discover, evolve 等）のルーティング変更

## Decisions

### D1: origin 判定は `installed_plugins.json` + パスベースのハイブリッド

**選択**: `audit.py` の既存 `_load_plugin_skill_map()` を `scripts/lib/skill_origin.py` に共通モジュールとして抽出。`installed_plugins.json` で plugin 由来と判定できない場合は `.claude-plugin/` ディレクトリの存在でフォールバック。mtime ベースの cache invalidation を適用し、`installed_plugins.json` の変更時のみ再パースする（`is_reference_skill()` の cache パターン準拠）。`installed_plugins.json` の `version` フィールドが未知の形式の場合は空 map を返却する graceful degradation を実装。

**代替案**: SKILL.md frontmatter に `source: plugin` を必須化 → plugin install 時の自動付与が必要で、Claude Code 側の変更が必要なため却下。

**理由**: 既存の `installed_plugins.json` パース実装を再利用でき、追加の外部依存なし。

### D2: 編集保護は「検出 + 警告生成」の2段構成

**選択**: `skill_origin.py` に `is_protected_skill(path)` → bool と `suggest_local_alternative(skill_name, project_root)` → str を実装。reflect/discover/remediation が保護対象への書込を検出した場合に警告テキストとローカル代替先パスを返す。

**代替案**: hook で Edit ツールの呼び出しを intercept → 全ファイル編集に影響し、パフォーマンスと false positive のリスクが高いため却下。

**理由**: 各コンポーネントが自身の責務内で保護チェックを行う方が影響範囲が限定的。

### D3: reflect の知見ルーティングに `last_skill` コンテキスト優先層を追加

**選択**: `suggest_claude_file()` の always/never 層の後、frontmatter paths 層の前（位置6）に `last_skill` コンテキスト層を挿入。corrections の `last_skill` フィールドが non-null の場合、そのスキルの references/ ディレクトリを confidence `LAST_SKILL_CONFIDENCE`（0.88）で優先提案する。保護スキルの場合はローカル代替先にリダイレクト。`last_skill` が None の場合はこの層をスキップし、後続の層に委譲する。

**代替案**: 全層を再設計して LLM ベースのルーティングに移行 → オーバーエンジニアリング。既存の優先順位チェーンに1層追加する方がシンプル。

**理由**: `last_skill` は corrections.jsonl に既に記録されており（observe hooks が記録済み）、追加のデータ収集が不要。always/never 層の後に配置することで、ユーザーの明示的な global ルーティング指示を尊重しつつ、コンテキスト情報を活用できる。

### D4: ローカル代替先のパス戦略

**選択**: 保護スキルの知見は `.claude/skills/<skill-name>/references/pitfalls.md`（プロジェクト側）に保存を提案。プラグインスキルと同名のディレクトリがプロジェクト側に存在しない場合は作成を提案。知見は pitfall_manager の Candidate フォーマット（`## Candidate: <title>` + context/pattern/solution）で追加する。

**代替案A**: `references/knowledge.md`（pitfall 以外の知見分離）→ 不採用理由: 知見タイプの判定が追加で必要になり複雑化。

**代替案B**: namespace 付与（`<plugin>--<skill>/`）→ 不採用理由: 既存の references/ パターンと非整合。

**代替案C**: auto-memory 経由 → 不採用理由: 2段階になり即時性が低下。

**理由**: 既存の references/ パターン（atlas-browser 等）と整合。プロジェクト側の references/ はプラグイン更新で上書きされない。pitfall_manager の Candidate フォーマットを採用することで、既存の品質ゲート（Candidate→New 昇格）が自動適用される。

## Risks / Trade-offs

- **[Risk] `installed_plugins.json` の形式変更** → Claude Code のバージョンアップで形式が変わる可能性。フォールバック（パスベース判定）で緩和。
- **[Risk] 知見の分散** → プラグインスキルの知見がプロジェクト側 references/ に分散する。audit でプロジェクト固有 references の存在を表示して可視化で緩和。
- **[Trade-off] 警告のみで物理ブロックなし** → エージェントが警告を無視する可能性があるが、rl-anything の責務として rules/CLAUDE.md への記載で対応可能（reflect が自動的にルールを生成）。

## Constants

| 定数名 | 値 | 説明 |
|--------|-----|------|
| `LAST_SKILL_CONFIDENCE` | 0.88 | last_skill コンテキスト層の confidence 値 |
