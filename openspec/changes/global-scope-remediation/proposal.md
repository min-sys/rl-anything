Related: #26

## Why

evolve の tool_usage_patterns 検出は Bash での grep/cat/find 使用や sleep ポーリングなど **Claude の振る舞い矯正パターン** を検出するが、remediation が「レポート表示 → 人間が手動対応」で止まっている。これらのパターンはプロジェクト固有ではなく **global スコープ**（`~/.claude/rules/` や `~/.claude/settings.json` hooks）への成果物生成が必要だが、現状の discover/remediation はプロジェクトスコープ前提で設計されており global artifacts を生成・適用するパスがない。

加えて、新規ユーザーが rl-anything をインストールしただけでは推奨 global 設定の存在を知る手段がなく cold start 問題が発生する。また、ユーザーが個人環境で試行中の global 設定を「知見が溜まったらカタログに昇格」したいケースで、忘れずに追跡する仕組みも必要。

## What Changes

- **discover が rule/hook 候補を出力** — 現状は skill 候補のみだが、tool_usage_patterns の builtin_replaceable/repeating_pattern から global rule 候補と PreToolUse hook スクリプト候補を生成
- **global スコープの remediation パス追加** — `~/.claude/rules/` への rule ファイル書き込みと `~/.claude/settings.json` への hook 登録を remediation の FIX_DISPATCH に追加
- **hook テンプレート scaffold** — PreToolUse hook のシェルスクリプトテンプレートを生成する機能（例: Bash 呼び出し時に grep/cat/find を検出して警告）
- **`/rl-anything:bootstrap` スキルの新設** — 推奨 global 設定カタログ（`recommended-globals.json`）から opt-in で選択・適用するオンボーディングフロー。既存設定との衝突検出を含む
- **候補追跡（candidate tracking）** — ユーザーの `~/.claude/rules/` や hooks にあるがカタログ未登録の設定を evolve が検出し、テレメトリで効果を測定、昇格（カタログ追加）を提案する仕組み

## Capabilities

### New Capabilities
- `global-rule-generation`: discover が tool_usage_patterns から global rule 候補（`~/.claude/rules/` 向け）を生成する機能
- `hook-template-scaffold`: PreToolUse hook のシェルスクリプトテンプレートを scaffold する機能
- `global-remediation-dispatch`: remediation が global スコープの成果物（rules, hooks）を適用するパス
- `bootstrap-onboarding`: `/rl-anything:bootstrap` スキル。推奨設定カタログ表示 → ユーザー選択 → 衝突検出 → 適用 → 検証のフロー
- `candidate-tracking`: ユーザーの個人 global 設定のうちカタログ未登録のものを evolve が追跡し、効果測定・昇格提案を行う機能

### Modified Capabilities
- `tool-usage-analysis`: builtin_replaceable 検出結果から rule/hook 候補への変換ロジック追加
- `remediation-engine`: global scope の issue に対する FIX_DISPATCH/VERIFY_DISPATCH 追加

## Impact

- **scripts/lib/tool_usage_analyzer.py** — rule/hook 候補生成関数の追加
- **skills/discover/scripts/discover.py** — tool_usage_patterns に rule_candidates/hook_candidates を追加出力
- **skills/evolve/scripts/remediation.py** — global scope の classify_issue を `manual_required` から `proposable` に昇格、FIX_DISPATCH に global rule/hook 適用アクション追加
- **skills/bootstrap/** — 新規スキル（SKILL.md + scripts/bootstrap.py）
- **skills/bootstrap/recommended-globals.json** — 推奨設定カタログ（essential/recommended/optional のカテゴリ分類）
- **skills/evolve/scripts/candidate_tracker.py** — カタログ未登録の個人 global 設定を追跡・効果測定
- **~/.claude/rules/** — 生成される global rule ファイル（ユーザー承認後）
- **~/.claude/settings.json** — hook 登録（ユーザー承認後）
- **安全性**: global スコープへの書き込みは全て proposable（ユーザー承認必須）、auto_fixable にはしない
