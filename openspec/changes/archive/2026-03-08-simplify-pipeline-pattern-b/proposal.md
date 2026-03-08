## Why

現在の evolve パイプラインは8ステージ / 15スキル / ~8,350 LOC と複雑すぎる。業界の成功例（DSPy, Reflexion, OpenAI Cookbook）は最大3ステージで同等以上の効果を達成している。#21 の調査で、現在の8ステージのうち多くは Skill 進化の周辺機能であり、統合しても効果を落とさないことが判明した。Phase 1 として Pattern B（Observe → Diagnose → Compile）への移行を行い、後続 Phase（全層 Diagnose / 全層 Compile / 自己進化）の土台を作る。

## What Changes

- **enrich スキルを discover に統合**: 164 LOC の Jaccard 類似度マッチを discover の後処理フィルタに変更
- **discover から session-scan を削除**: ~50 LOC のテキストマイニング機能。ノイズが多く限界的
- **マージ候補検出を prune に一元化**: reorganize と prune の二重検出を解消。reorganize は split 検出のみに縮小
- **regression gate を共通ライブラリに抽出**: optimize.py 内のハードコードを `scripts/lib/regression_gate.py` に分離
- **evolve オーケストレーターを3ステージに再構成**: Observe → Diagnose → Compile の流れに整理
- **backfill をセットアップコマンドに再分類**: パイプラインから分離し、初期セットアップ専用に

## Capabilities

### New Capabilities

- `diagnose-stage`: Diagnose ステージ — discover(core) + enrich(統合) + audit 問題検出を1ステージに統合。パターン検出 + 既存スキル照合 + 構造チェックを実行し、レイヤー別の問題リストを出力する
- `compile-stage`: Compile ステージ — optimize + reflect + remediation を1ステージに統合。corrections/context/診断結果からパッチ生成 → regression gate → fitness 検証 → メモリルーティングを実行する
- `shared-regression-gate`: 共通 regression gate ライブラリ — optimize / rl-loop / 将来の全層 Compile で共有する regression gate ルールエンジン

### Modified Capabilities

- `regression-gate`: gate ルールを共通ライブラリに移動。インターフェースは維持、実装場所が変わる
- `enrich`: **BREAKING** — 独立スキルとしては廃止。discover の内部処理に統合
- `reorganize`: マージ候補検出を削除し split 検出のみに縮小。prune の optional sub-function に

## Impact

- **スキル数**: 15 → 14（enrich 廃止）。evolve は内部的に 3ステージ構成（Diagnose → Compile → Housekeeping）に再編。regression gate は `scripts/lib/regression_gate.py` に共通化
- **LOC**: ~8,350 → ~7,900（統合による ~450 LOC 削減）
- **evolve スキル**: 全面書き換え（3ステージオーケストレーターに）
- **discover スキル**: enrich の Jaccard 処理を統合、session-scan 削除
- **prune スキル**: reorganize のマージ検出ロジックを取り込み
- **optimize スキル**: regression gate を外部ライブラリ参照に変更
- **rl-loop スキル**: regression gate を外部ライブラリ参照に変更
- **テスト**: 既存テストの参照先変更 + 新しい共通 gate のテスト追加
- **関連 issue**: #21（ロードマップ簡素化）の Phase 1 に該当
