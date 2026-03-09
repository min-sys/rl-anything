Closes: #23

## Why

evolve 実行時の remediation で検出される issue の大半が false positive であり、毎回同じ誤検出が再発する（#23）。stale_ref 16件全て FP、orphan_rule 2件 FP、claudemd_missing_section 1件 FP、line_limit の適用範囲不適切と、4パターンの精度問題がパイプライン信頼性を低下させている。

## What Changes

- `_extract_paths_outside_codeblocks()` の FP 削減: 数値のみパターン（`429/500/503`）除外、相対パスのファイル位置基準解決、外部リポジトリ参照・スペック名の除外
- `diagnose_rules()` の orphan_rule 判定改善: `.claude/rules/` は Claude が自動読み込みするため、auto-load ディレクトリのルールを orphan 判定から除外
- `diagnose_claudemd()` のセクション名マッチング改善: `## Key Skills` 等の prefix 付きセクション名にもマッチするよう正規表現を拡張
- `line_limit` のファイル種別分離: CLAUDE.md と MEMORY.md で異なる制限値、global rule と project rule の区別

## Capabilities

### New Capabilities
- `path-context-aware-filtering`: パス抽出時にコンテキスト（数値パターン、ファイル位置基準の相対パス解決、外部リポジトリ参照）を考慮した高精度フィルタリング
- `auto-load-rule-awareness`: `.claude/rules/` は全て auto-load 対象のため、orphan_rule issue type を廃止。将来は telemetry ベースの unused_rule に移行
- `flexible-section-matching`: CLAUDE.md セクション名の prefix 許容マッチング
- `tiered-line-limits`: ファイル種別（CLAUDE.md/MEMORY.md/global rule/project rule）ごとの段階的行数制限

### Modified Capabilities
- `path-extraction-filtering`: 数値パターン除外、ファイル位置基準解決、外部リポジトリ参照除外の追加
- `rules-diagnose`: orphan_rule issue type を廃止（auto-load により事実上 dead code）
- `claudemd-diagnose`: セクション名マッチングの正規表現拡張
- `line-limit`: ファイル種別ごとの段階的制限値の導入

## Impact

- **scripts/lib/layer_diagnose.py**: `diagnose_rules()`, `diagnose_claudemd()` の判定ロジック変更
- **skills/audit/scripts/audit.py**: `_extract_paths_outside_codeblocks()` のフィルタリング強化
- **scripts/lib/line_limit.py**: ファイル種別分離の定数・ロジック追加
- **skills/audit/scripts/audit.py**: LIMITS dict の種別分離
- **テスト**: 各パターンの FP ケースを追加し regression 防止
- **既存 specs**: 4つの既存 spec（path-extraction-filtering, rules-diagnose, claudemd-diagnose, line-limit）に delta 追加
