## Why

evolve の Report フェーズ（Step 7）は行数制限違反やメモリの古い参照などの問題を検出・報告するが、修正提案やアクション提示を行わない。ユーザーが自分で対処を依頼しなければ何も起きず、detect → report で止まっている。propose → review → apply の Remediation ループを追加し、検出から修正までを一体化する。

## What Changes

- evolve の Report フェーズの後に **Remediation フェーズ**（Step 7.5）を追加
- 検出された問題を confidence_score（修正の確実性）と impact_scope（影響範囲）に基づき3カテゴリに動的分類:
  - **auto-fixable**: 高信頼度 + ファイルスコープの問題を自動修正（rationale 付き一括承認）
  - **proposable**: 中信頼度またはプロジェクトスコープの問題に具体的な修正案を提案（理由説明付き個別承認）
  - **manual-required**: 低信頼度またはグローバルスコープの問題を明示（分類理由を表示）
- 修正後に2段階検証（Fix Verification + Regression Check）を実施。副作用検出時はロールバック
- 修正結果を `remediation-outcomes.jsonl` に記録し、分類精度の改善に活用
- evolve.py に Remediation フェーズのデータ収集ロジックを追加（dry-run 時は分類レポートのみ）

## Capabilities

### New Capabilities

- `remediation-engine`: audit レポートから fixable な問題を抽出し、confidence_score / impact_scope ベースで動的分類。rationale 付き修正アクション生成と outcome 記録を行うエンジン
- `remediation-verification`: Fix Verification（元問題の解消確認）+ Regression Check（副作用検出）の2段階検証。副作用検出時のロールバック機能を含む

### Modified Capabilities

（なし）

## Impact

- `skills/evolve/SKILL.md`: Step 7.5 として Remediation フェーズのフロー追記
- `skills/evolve/scripts/evolve.py`: Remediation 用データ収集の Phase 追加
- `skills/audit/scripts/audit.py`: 問題分類メタデータの構造化出力（既存レポートとの互換性維持）
- 新規スクリプト: `skills/evolve/scripts/remediation.py`（問題分類 + 修正アクション生成）
