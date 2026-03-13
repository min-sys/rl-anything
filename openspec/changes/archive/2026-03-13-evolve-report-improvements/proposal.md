Related: #26

## Why

evolve レポートは「対策済み」と表示するが、対策の効果（トレンド推移）が見えず改善判断ができない。また remediation の auto_fixable 範囲が狭く、機械的に修正可能な問題が proposable/manual_required に留まっている。fitness evolution はコールドスタート問題で MIN_DATA_COUNT=30 に到達できず機能しない。これらを一括で改善し、evolve パイプラインの実用性を引き上げる。

## What Changes

- evolve レポートの tool usage セクションに **前回比トレンド**（件数差分・増減率）を追加
- remediation の **auto_fixable 範囲を拡張**: line_limit 違反（軽微）と untagged_reference_candidates に自動修正を実装
- fitness evolution の **bootstrap モード** 追加（MIN_DATA_COUNT 未満でも簡易分析を実行）
- evolve レポートに **BASH_RATIO_THRESHOLD 表示**（目標値 vs 実績の明示）
- untagged_reference_candidates に対する **FIX_DISPATCH エントリ追加**（frontmatter に `type: reference` を自動付与）

## Capabilities

### New Capabilities

- `mitigation-trend`: 対策効果のトレンド可視化（前回 evolve との件数比較・増減表示）
- `fitness-bootstrap`: fitness evolution のコールドスタート対策（少数データでの簡易分析モード）
- `reference-type-autofix`: untagged_reference_candidates の自動修正（frontmatter type: reference 付与）

### Modified Capabilities

- `remediation-engine`: auto_fixable 判定ロジック拡張（line_limit 軽微違反の昇格）
- `tool-usage-analysis`: BASH_RATIO_THRESHOLD の目標値表示追加

## Impact

- `skills/evolve/scripts/remediation.py` — classify_issue, FIX_DISPATCH, VERIFY_DISPATCH 拡張
- `skills/evolve-fitness/scripts/fitness_evolution.py` — bootstrap モード追加
- `scripts/lib/tool_usage_analyzer.py` — threshold 表示用データ追加
- `skills/evolve/SKILL.md` — レポートテンプレート更新（トレンド・threshold 表示）
- `skills/discover/scripts/discover.py` — mitigation_metrics にトレンドデータ追加
- Related: #26（tool_usage_patterns 自動生成の前提改善）
