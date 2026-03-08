## Why

Phase 0（Coherence Score）と Phase 1（Telemetry Score）は LLM コストゼロで環境の構造品質と行動実績を測定するが、「PJ の価値観・原則に沿っているか」という質的評価ができない。例えば rl-anything で「LLM コール最小化」「べき等性保証」といった PJ 固有の原則を全レイヤーが遵守しているかは、静的分析やテレメトリでは判定できない。Phase 2 として Constitutional AI + Chaos Engineering の手法を導入し、LLM Judge による原則ベース評価と障害注入による堅牢性テストを実現する。

## What Changes

- CLAUDE.md から PJ 固有の「原則（principles）」を半自動抽出する仕組みを追加
- LLM Judge が全レイヤー（Rules/Skills/Memory/CLAUDE.md）を原則に照らして採点する Constitutional Evaluation を実装
- 構成要素の除去（Rule 無効化・Memory 空化等）で環境の堅牢性を測る Chaos Testing を実装
- `audit --constitutional-score` で Constitutional Score を表示
- `scripts/rl/fitness/environment.py` に Constitutional Score を統合し、3層ブレンド（Coherence + Telemetry + Constitutional）を実現

## Capabilities

### New Capabilities
- `constitutional-eval`: CLAUDE.md から原則を抽出し、LLM Judge が全レイヤーを原則に照らして評価する Constitutional Score（0.0〜1.0）の算出
- `chaos-testing`: 構成要素の除去・矛盾注入により環境の堅牢性を測定する Chaos Score（0.0〜1.0）の算出
- `principle-extraction`: CLAUDE.md/Rules から PJ 固有の原則を半自動で抽出・構造化する仕組み

### Modified Capabilities
- `environment-fitness`: Constitutional Score を3層目として統合（Coherence + Telemetry + Constitutional の動的ブレンド）
- `audit-report`: `--constitutional-score` オプション追加、Constitutional Score の表示

## Impact

- **新規ファイル**: `scripts/rl/fitness/constitutional.py`, `scripts/rl/fitness/chaos.py`, `scripts/rl/fitness/principles.py`
- **既存変更**: `scripts/rl/fitness/environment.py`（3層ブレンド）, audit スキル（`--constitutional-score` オプション）
- **LLM コスト**: Constitutional 評価 1回あたり原則数 × レイヤー数の LLM コール発生（Phase 0-1 と異なりコストゼロではない）
- **依存**: Phase 0（coherence.py）+ Phase 1（telemetry.py）が実装・運用済みであること
- **関連 Issue**: [#15](https://github.com/min-sys/rl-anything/issues/15)
- **Related**: #21
