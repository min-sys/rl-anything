Related: #21

## Why

Phase 0 の Coherence Score（構造品質）は「環境として整っているか」を静的に測定できるが、「環境が実際に役立っているか」は分からない。hooks が蓄積した usage/errors/corrections/sessions/workflows データを活用し、LLM コストゼロのテレメトリ駆動スコアを実装することで、進化メカニズムに行動実績ベースの判断根拠を与える。

## What Changes

- `scripts/rl/fitness/telemetry.py` を新規作成: Utilization / Effectiveness / Implicit Reward の3軸で行動実績スコア（0.0〜1.0）を算出
- `telemetry_query.py` に時間範囲比較クエリを追加: 直近 N 日 vs 前 N 日の差分算出
- `audit` スキルに `--telemetry-score` オプションを追加: Coherence Score に並ぶ2軸目として表示
- `scripts/rl/fitness/environment.py` を新規作成: Coherence + Telemetry をブレンドした統合 environment fitness
- 既存の `telemetry_query.py` / `usage.jsonl` / `errors.jsonl` / `corrections.jsonl` / `sessions.jsonl` / `workflows.jsonl` を最大限活用し、新規データ収集は行わない

## Capabilities

### New Capabilities
- `telemetry-score`: テレメトリデータから環境の実効性を3軸（Utilization/Effectiveness/Implicit Reward）で測定する fitness 関数
- `environment-fitness`: Coherence Score + Telemetry Score をブレンドした統合 environment fitness スコア

### Modified Capabilities
- `audit-report`: Telemetry Score セクションの追加（3軸スコア + データ充足度 + トレンド表示）

## Impact

- 新規ファイル: `scripts/rl/fitness/telemetry.py`, `scripts/rl/fitness/environment.py`, テスト
- 変更ファイル: `skills/audit/SKILL.md`（`--telemetry-score` オプション追加）, `scripts/lib/telemetry_query.py`（時間範囲クエリ追加）
- 依存: 既存の `telemetry_query.py`, `scripts/rl/fitness/coherence.py`, hooks が蓄積する JSONL ファイル群
- データ要件: 最低 30 セッション蓄積で信頼性のあるスコアを算出（不足時は data_sufficiency: false で警告）
- Issue: [#21](https://github.com/min-sys/rl-anything/issues/21)
