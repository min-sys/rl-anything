## Why

Claude Code v2.1.80 で `effort` frontmatter がサポートされ、スキル呼び出し時の effort level を自動制御できるようになった。しかしユーザーのプロジェクトスキルには effort が未設定のものが多く、手動で全スキルに適切なレベルを設定するのは煩雑。audit/evolve パイプラインで未設定を検出し、スキル特性から適切なレベルを推定・提案することで、ユーザーの導入コストを下げる。

## What Changes

- `effort_detector.py` 新規モジュール: effort 未設定スキルの検出 + スキル特性に基づくレベル推定（low/medium/high）
- `issue_schema.py` に `MISSING_EFFORT_CANDIDATE` 定数 + factory 関数追加
- `audit.py` の `collect_issues()` に effort 未設定検出を統合
- `remediation.py` に `fix_missing_effort` ハンドラ + `_verify_missing_effort` 検証関数追加（FIX_DISPATCH/VERIFY_DISPATCH 登録）
- evolve パイプライン経由で自動提案フローに接続

## Capabilities

### New Capabilities
- `effort-detection`: effort frontmatter 未設定スキルの検出とレベル推定ヒューリスティクス

### Modified Capabilities
- `diagnose-stage`: evolve Diagnose ステージに effort 検出結果の issue 変換を追加

## Impact

- `scripts/lib/effort_detector.py` — 新規
- `scripts/lib/issue_schema.py` — 定数・factory 追加
- `skills/audit/scripts/audit.py` — collect_issues() に検出統合
- `skills/evolve/scripts/remediation.py` — FIX_DISPATCH/VERIFY_DISPATCH 追加
- `scripts/tests/test_effort_frontmatter.py` — 新規テスト
