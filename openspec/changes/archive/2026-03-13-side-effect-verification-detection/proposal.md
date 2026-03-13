Related: #27

## Why

テスト検証時に「正パスのみ確認・副作用未確認」のまま完了とするパターンが繰り返し発生している（#27）。verification.md ルールに副作用チェックの1行を追加済みだが、discover/reflect でこのパターンを自動検出し、プロジェクト固有の副作用チェックリスト生成をルール提案できると再発防止が強化される。

## What Changes

- **verification_catalog.py に副作用検出エントリを追加**: DB残留・共有リソース書き込み・非同期連鎖の3パターンを検出する `side-effect-verification` カタログエントリ
- **reflect_utils.py に corrections からの副作用見落としパターン検出を追加**: 過去の corrections.jsonl から「副作用未確認→手動修正」パターンを抽出し、ルール改善を提案
- **検出関数 `detect_side_effect_verification`**: プロジェクト内の DB操作・メッセージキュー・Webhook 等の共有リソースアクセスパターンを走査し、副作用チェックルールの必要性を判定

## Capabilities

### New Capabilities
- `side-effect-detection`: verification_catalog への副作用検出エントリ追加 + 検出関数実装
- `correction-side-effect-pattern`: reflect での corrections ベース副作用見落としパターン検出

### Modified Capabilities
- `verification-catalog`: 新エントリ追加に伴うカタログ拡張（既存 spec の requirement は変更なし、エントリ追加のみ）

## Impact

- `scripts/lib/verification_catalog.py`: 新エントリ + 検出関数追加
- `scripts/lib/reflect_utils.py`: 副作用パターン検出ロジック追加
- `scripts/lib/issue_schema.py`: 変更なし（既存の `verification_rule_candidate` をそのまま利用）
- discover/evolve/remediation パイプライン: 既存の `verification_needs` フローに乗るため変更不要
