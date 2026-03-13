Related: #26

## Context

現在の evolve パイプラインは tool_usage_analyzer で Bash の Built-in 代替パターン（grep→Grep, cat→Read 等）を検出するが、検出結果は discover レポートにテキスト表示されるだけで、自動的な remediation アクションに繋がらない。これらのパターンはプロジェクト固有ではなく **Claude の振る舞い矯正** であり、成果物は `~/.claude/rules/` や `~/.claude/settings.json` hooks といった global スコープに配置すべきもの。

現状の remediation.py は `scope == "global"` の issue を一律 `manual_required` に分類し、global ファイルへの書き込みパスを持たない。

## Goals / Non-Goals

**Goals:**
- discover が tool_usage_patterns から global rule 候補と hook テンプレート候補を構造化データで出力する
- remediation が global scope の issue を `proposable` として扱い、ユーザー承認後に `~/.claude/rules/` へ rule ファイルを書き込む
- PreToolUse hook のシェルスクリプトテンプレートを scaffold し、`~/.claude/settings.json` への登録案を提示する

**Non-Goals:**
- global scope の issue を `auto_fixable` にすること（常に proposable 止まり、ユーザー承認必須）
- settings.json の自動書き換え（hook 登録はスクリプト生成 + 手順提示まで）
- sleep ポーリングパターンの hook 自動生成（Phase 2 で対応）
- 既存の project scope remediation の動作変更

## Decisions

### D1: global rule 候補の生成場所
**決定**: `tool_usage_analyzer.py` に `generate_rule_candidates()` 関数を追加。discover は既存の `tool_usage_patterns` に `rule_candidates` キーを追加出力する。

**理由**: tool_usage_analyzer が既にパターン分類ロジックを持っており、rule 候補生成はその延長線上にある。別モジュールにすると責務が分散する。

**代替案**: 新モジュール `global_artifact_generator.py` を作る → パターン分類と候補生成が分離し、依存関係が増える。不採用。

### D2: hook テンプレートの生成方式
**決定**: `tool_usage_analyzer.py` に `generate_hook_template()` 関数を追加。builtin_replaceable パターンから PreToolUse hook のシェルスクリプトを生成する。スクリプトは `~/.claude/hooks/` に出力。block 時は reason を stderr に出力し `exit 2` で終了する。

**理由**: hook スクリプトはテンプレートベースで生成可能（パターン → コマンド先頭語検査 → 警告メッセージ）。settings.json への登録は diff 表示 + 手順案内に留める。`exit 2` + stderr は [Claude Code Hooks Guide](https://code.claude.com/docs/en/hooks-guide) の PreToolUse hook 公式パターン。

**代替案**:
- `exit 2` + stderr（採用）: 公式ドキュメントのパターン。シンプルで標準的
- `hookSpecificOutput.permissionDecision: "deny"` を JSON stdout で返す: 構造化レスポンスが必要な場合の選択肢。現時点では不要

### D3: remediation の global scope 分類変更
**決定**: `classify_issue()` で `scope == "global"` かつ `confidence >= PROPOSABLE_CONFIDENCE` の場合は `proposable` に昇格する。`auto_fixable` にはしない。

**理由**: global ファイルへの書き込みは影響範囲が広い（全プロジェクト・全セッションに影響）ため、必ずユーザー承認を経る。

### D4: rule ファイルのフォーマット
**決定**: `.claude/rules/` のルールは 3 行以内（既存ルール `rules-style.md` 準拠）。ファイル名は `avoid-bash-{command}.md` 形式。

**理由**: 既存のプロジェクトルールと同一のスタイルに統一。

### D5: 新しい issue type の追加
**決定**: `tool_usage_rule_candidate` と `tool_usage_hook_candidate` の 2 つの issue type を追加。discover → remediation の橋渡しに使う。

**理由**: 既存の issue type パターン（`stale_rule`, `claudemd_phantom_ref` 等）に倣い、remediation の FIX_DISPATCH/VERIFY_DISPATCH テーブルで統一的に扱える。

### D6: Bootstrap スキルのアーキテクチャ

**決定**: SKILL.md プロンプトで LLM にフローを指示し、Python スクリプト（`bootstrap.py`）はカタログ読み込み・衝突検出・テンプレート生成のヘルパーに留める。適用は LLM が Write/Edit ツールで実行。

**理由**: ユーザーとの対話（選択、確認）は LLM が適切。Python で TUI を作るのはオーバーエンジニアリング。Write/Edit ツール経由なら Claude Code の permission mode で承認フローが自然に入り、スクリプトが直接書き込むリスクを回避。

**代替案**: `/hooks` CLI メニューへの誘導 — Claude Code の `/hooks` コマンドで対話的に hook を設定する方法。不採用理由: プログラマティックな一括適用ができないため。

### D7: カタログのカテゴリ分類

**決定**: `essential`（rl-anything の動作に直接影響）/ `recommended`（品質向上）/ `optional`（便利だがなくてもよい）の 3 段階。essential はデフォルト選択済み。

### D8: Candidate Tracking の仕組み

**決定**: evolve の Diagnose ステージで `~/.claude/rules/` と `~/.claude/settings.json` hooks を走査し、`recommended-globals.json` に未登録の設定を検出 → `evolve-state.json` の `global_candidates` に記録 → テレメトリで corrections/usage との相関を測定 → 効果が確認できたら「カタログ昇格」を提案。閾値定数: `PROVEN_THRESHOLD = 3`（corrections.jsonl 参照回数で proven 判定）、`TESTING_MINIMUM = 2`（テレメトリ件数の最低ライン）。配置先: `candidate_tracker.py` のモジュール定数。

**理由**: ユーザーが個人環境で試行中の設定を忘れずに追跡し、知見が溜まった時点で自動的にリマインドする。evolve の既存パイプラインに乗せることで追加のトリガー機構が不要。

### D9: 推奨設定の初期カタログ

| 名前 | 種別 | カテゴリ | 説明 |
|------|------|----------|------|
| `avoid-bash-builtin` | rule | essential | grep/cat/find の代わりに専用ツールを使う |
| `check-bash-builtin` | hook (PreToolUse) | essential | Bash ツール呼び出し時に builtin 使用を検出して block |
| `no-defer-use-subagent` | rule | recommended | 先送りせず subagent で並行処理 |
| `detect-deferred-task` | hook (Stop) | recommended | 先送り表現を検出して block |
| `monitor-background-agents` | rule | recommended | background subagent の進捗を定期監視 |
| `verification` | rule | recommended | テスト不合格を「仕方ない」で済ませない |
| `suggest-subagent-delegation` | hook (PostToolUse) | recommended | メインコンテキスト5分超過で subagent 移譲を提案 |
| `analyze-before-act` | rule | optional | 構造変更前に既存パターンを確認 |
| `skill-awareness` | rule | optional | タスク変更時にスキル一覧を再確認 |

## Risks / Trade-offs

- **[Risk] rule の重複生成** — 既に `~/.claude/rules/` に類似ルールが存在する場合に重複する → **Mitigation**: 生成前に既存 rules をスキャンし、同じコマンドを対象とするルールが既存なら候補から除外
- **[Risk] hook スクリプトの互換性** — settings.json のフォーマットが Claude Code バージョンによって変わる可能性 → **Mitigation**: スクリプト生成 + 手順案内に留め、settings.json の自動書き換えはしない
- **[Risk] builtin_replaceable の false positive** — パイプ内の grep 等は正当な使用だが rule で警告される → **Mitigation**: rule テキストに「パイプ内での使用は除外」の注記を含める。hook スクリプトでは jq でコマンド先頭語のみを検査
- **[Risk] candidate tracking の FP** — ユーザー固有の設定（aws-auth 等）をカタログ昇格候補として誤検出 → **Mitigation**: プロジェクト固有キーワード（AWS, git org 名等）を含むルールは候補から除外するフィルタ
- **[Trade-off] bootstrap 適用は LLM 経由で遅いが安全** — Python 直接書き込みは速いが承認をバイパスするリスク。安全性を優先
