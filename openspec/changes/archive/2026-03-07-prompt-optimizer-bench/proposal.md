## Why

rl-anything の `/optimize` は遺伝的アルゴリズム（GA）でスキルを最適化するが、10回の実行で一度もオリジナルを超えられていない。変異が途中で切れる（自壊問題）、評価が見た目品質のみ、探索空間が狭いという3つの根本問題がある。2025-2026年のプロンプト最適化研究（GEPA, TextGrad, DSPy, Self-Refine等）は大きく進歩しており、最適な手法を実データで検証する必要がある。

## What Changes

- 別リポジトリ `prompt-optimizer-bench` を新規作成し、プロンプト最適化手法の包括的ベンチマークを構築する
- 6手法（現行GA, Self-Refine, GEPA-lite, TextGrad, DSPy MIPROv2, PromptAgent）を統一インターフェースで比較
- 2層評価: Layer A（汎用プロンプト最適化）+ Layer B（スキル/メタプロンプト最適化）
- ベンチマーク結果をもとに、rl-anything の optimize v2 に最適な手法を還元

## Capabilities

### New Capabilities

- `strategy-interface`: 各最適化手法の統一インターフェース（mutate/evaluate/select）と strategy 実装
- `benchmark-runner`: 複数手法 x 複数タスク x N回試行のベンチマーク実行エンジン
- `meta-prompt-evaluation`: スキル/メタプロンプト特有の評価フレームワーク（変異生存率・完全性・スコア改善幅・LLMコスト）
- `result-analysis`: ベンチマーク結果の統計分析・可視化

### Modified Capabilities

（なし — 別リポのため既存機能への変更なし）

## Impact

- **新規リポジトリ**: `prompt-optimizer-bench` を min-sys org に作成
- **依存関係**: Phase 1 は pip 依存なし（`claude -p` のみ）。Phase 2 で `dspy`, `textgrad`, `gepa` を追加（別リポに閉じる）
- **rl-anything への影響**: 直接的な変更なし。ベンチマーク結果をもとに後続の optimize v2 change で反映
- **関連 issue**: min-sys/rl-anything#12
