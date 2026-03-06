## Why

skill/rule ファイル内にハードコードされた環境固有の値（App ID、チャンネルID、ARN等）が混入すると、新規セットアップ時にそのまま使われて不具合の原因になる。実際に channel-routing スキルで `slack_app_id` の固定値が原因で bot が無反応になる事故が発生した（GitHub Issue #9）。現在 audit/discover にはこの種の検出機能がなく、手動レビューに頼っている。

## What Changes

- audit に**ハードコード値検出フェーズ**を追加し、skill/rule ファイル内の環境固有リテラルを警告する
- 検出対象: 環境固有 ID（App ID、チャンネル ID、ARN、URL等）がプレースホルダでなく固定値として記載されているケース
- 許容パターン（false positive 回避）: ダミーサンプル値、意図的な定数定義、プレースホルダ `${VAR}` 表記
- 検出結果を `collect_issues()` に統合し、remediation パイプラインで修正提案可能にする

## Capabilities

### New Capabilities
- `hardcoded-value-detection`: skill/rule ファイル内の環境固有ハードコード値を正規表現 + ヒューリスティクスで検出し、audit レポートおよび collect_issues() に統合する
- `inline-suppression`: `<!-- rl-allow: hardcoded -->` コメントによる行単位の検出抑制。意図的なハードコード値を false positive から除外する

### Modified Capabilities

## Impact

- `skills/audit/scripts/audit.py`: `collect_issues()` に新検出結果を追加、`generate_report()` に警告セクション追加
- `scripts/lib/`: 新モジュール `hardcoded_detector.py` を配置（検出ロジック本体）
- 既存の remediation パイプライン（`skills/evolve/scripts/remediation.py`）は変更不要 — `collect_issues()` 経由で自動連携
