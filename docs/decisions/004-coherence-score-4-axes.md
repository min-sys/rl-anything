# ADR-004: Coherence Score 4 Axes

Date: 2026-03-08
Status: Accepted

## Context

既存の fitness 評価は `scripts/rl/fitness/plugin.py`（Skill テキストのキーワードマッチ）のみで、環境全体の構造的整合性を測る仕組みがなかった。ロードマップ Gap 1 Phase 0 として、LLM コストゼロの Coherence Score を実装し、全ての進化メカニズムの基盤となる「環境品質のベースライン」を確立する必要があった。

## Decision

- **単一ファイル `coherence.py` に4軸を集約**: Coverage / Consistency / Completeness / Efficiency の4軸スコア関数を `scripts/rl/fitness/coherence.py` に実装。各軸は 20-40 行程度の小さな関数で、ファイル分割するほどの複雑さがない
- **重み付き平均でスコア算出**: Coverage 0.25 / Consistency 0.30 / Completeness 0.25 / Efficiency 0.20。Consistency（レイヤー間の矛盾）が最も環境品質に影響するため最重。Efficiency（冗長さ）は他3軸が整っていれば軽微
- **audit に `--coherence-score` フラグで統合**: デフォルトでは既存レポートに影響を与えず、明示的にフラグ指定で Coherence Score セクションを追加
- **既存モジュールを最大限再利用**: audit.collect_issues() / hardcoded_detector.py / skill_triggers.py / reflect_utils.py を再利用し、新規ロジックを最小化
- **閾値の一括管理**: モジュール先頭に `THRESHOLDS` dict を定義し、全閾値を一括管理。ハードコード散在を防止
- **LLM コストゼロ**: 全て静的分析のみで算出

## Alternatives Considered

- **軸ごとにファイル分割**: 過剰分割。各軸は小さな関数で1ファイルに収まる
- **audit.py に直接追加**: audit の責務が膨らみすぎる
- **常時表示**: 情報過多になるため、フラグでオプトインとした
- **別コマンドとして実装**: 発見性が低いため audit のオプションとした

チェック項目の過不足リスクは運用後にチューニングで対応し、既存モジュールの import 依存の深さは coherence.py を薄いラッパーに徹することで軽減する。重み配分は v1 では固定値とし、テレメトリで校正する余地を残す。

## Consequences

**良い影響:**
- 環境全体の構造的整合性を定量的に測定可能になった
- LLM コストゼロのため、頻繁に実行しても追加コストなし
- THRESHOLDS dict パターンが後続の telemetry.py / constitutional.py で踏襲される標準パターンとなった
- evolve パイプラインが構造品質の数値根拠に基づいて判断できるようになった

**悪い影響:**
- 重み配分が固定のため、プロジェクト特性によっては最適でない場合がある
- 静的分析のみのため「実際に役立っているか」は測定できない（Phase 1 Telemetry Score で補完）
