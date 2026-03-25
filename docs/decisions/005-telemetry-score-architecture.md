# ADR-005: Telemetry Score Architecture

Date: 2026-03-08
Status: Accepted

## Context

Phase 0 の Coherence Score（構造品質）は「環境として整っているか」を静的に測定できるが、「環境が実際に役立っているか」は分からなかった。hooks が蓄積する5種の JSONL（usage / errors / corrections / sessions / workflows）は discover/audit で部分的に利用されていたが、環境の実効性を定量化する統合スコアは存在しなかった。

## Decision

- **3軸テレメトリスコア**: Utilization / Effectiveness / Implicit Reward の3軸で行動実績スコアを算出する `telemetry.py` を実装。coherence.py と同じ THRESHOLDS/WEIGHTS + score_xxx() 関数群パターンに準拠
- **重み配分**: Utilization 0.30 / Effectiveness 0.40 / Implicit Reward 0.30。Effectiveness（使用傾向の改善）を最重視
- **telemetry_query.py に時間範囲クエリ追加**: 既存の query_xxx() に `since`/`until` パラメータを追加。Effectiveness 算出には「直近30日 vs 前30日」の比較が必要
- **query_corrections() / query_workflows() の新規追加**: telemetry_query.py の共通クエリ層に追加し、DRY を維持
- **environment.py で Coherence + Telemetry をブレンド**: テレメトリ利用可能時は coherence 0.4 + telemetry 0.6 の固定重み。テレメトリデータ不足時は coherence のみにフォールバック
- **data_sufficiency 判定**: 最低30セッション + 最低7日間のデータ幅を要件とする
- **Implicit Reward は簡易実装**: Skill 単位の成功率（invoke 後60秒以内に corrections が発生しない = success）のみ。同一 session_id の一致を要件としクロスセッション誤検出を防止
- **LLM コストゼロ**: 全て既存データの集計のみ

## Alternatives Considered

- **別の query_usage_range() 関数を新設**: 重複が多く保守コスト増のため、既存関数の拡張を選択
- **等重み (0.5/0.5) のブレンド**: テレメトリの情報量を活かせない。構造が整っていても実際に使われていない環境を過大評価するリスク
- **動的重み（データ量に応じてスライド）**: 閾値設計・テストが複雑化するため Phase 1 では固定重みで十分と判断
- **corrections の高精度パース**: カウントベースの簡易集計に留め、Phase 2 で LLM による高精度分類を検討

リスクとして、特定PJでのみ hooks が活発な場合のデータ偏りはスコアをPJ内相対トレンドとして解釈することで軽減し、Shannon entropy のスキル数依存は正規化で対応する。

## Consequences

**良い影響:**
- 環境の実効性を定量的に測定可能になり、「整っているが使われていない」環境を検出可能に
- テレメトリデータ不足時も coherence のみで安全にフォールバックし、段階的なスコア向上が可能
- environment.py の統合設計が Phase 2（Constitutional）の追加を容易にする拡張点を提供
- LLM コストゼロのため、Coherence Score と同様に頻繁な実行が可能

**悪い影響:**
- 最低30セッション + 7日間の蓄積が必要で、新規プロジェクトではしばらくスコアが利用できない
- Implicit Reward の60秒ウィンドウは proxy 指標であり、精度に限界がある
- corrections.jsonl の project_path と他 JSONL の project フィールドの不整合を query_corrections() で吸収する必要がある
