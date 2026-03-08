## Why

MPO（Modular Prompt Optimization）は #12 で導入したセクション局所最適化により long_skill の品質改善を実現したが、大規模スキルではLLMコール数が爆発する。atlas-browser スキル（1,180行）を例にとると、`##`/`###` 分割で88セクション x 2コール（evaluate + update）= 最大176 LLMコールとなり、コスト的に実用不可能である。

| ターゲット | 行数 | セクション | コール | 結果 |
|-----------|------|-----------|--------|------|
| short_rule | 9 | - | 6 (TextGrad) | +0.476 |
| long_skill | 127 | 11 | 20 (MPO) | +0.085 |
| atlas-browser | 1,180 | 88 | 176 (MPO) | 未検証 |

prompt-optimizer-bench での検証により、ファイルサイズに応じた手法切り替えが最適であることが判明した:

| ファイルサイズ | ベスト手法 | Score Imp | Survival | Completeness | Calls |
|-------------|----------|-----------|----------|--------------|-------|
| short (< 60行) | self_refine | +0.45 | 80% | 1.00 | 13 |
| medium (60-200行) | self_refine | +0.364 | 100% | 0.98 | 13 |
| long (200行超) | **budget_mpo** | **+0.090** | **100%** | **0.96** | **8** |

2025-2026年のプロンプト最適化研究（SPO, OPTS, TRIPLE, GEPA, FrugalGPT, TEP）では、バンディットベースのセクション選択、モデルカスケード、ペアワイズ評価等の手法でコスト削減が実証されている。これらの知見を組み合わせ、176コール(高価モデル) を 20-30コール相当に削減する。

## What Changes

### 0. ファイルサイズベースの手法ルーター

ファイルサイズに応じて最適な最適化手法を自動選択する。

- `< 60行`: self_refine（批評→部分修正ループ、最大3回反復）
- `60-200行`: self_refine（同上）
- `200行超`: budget_mpo（以下の手法1-4を統合した大規模スキル向けパイプライン）

### 1. 適応的粒度制御（Adaptive Granularity）

88セクションを ~35セクションに削減する。

- ファイルサイズに応じた分割レベルの自動切替: `<60行` → 一括（TextGrad）、`60-200行` → `##`/`###` 分割、`200行超` → `##` のみ分割
- 小セクション統合: 10行未満のセクションは親セクションに merge
- GAAPO（Frontiers 2025）、MoG の適応的粒度手法を参考

### 2. Budget-Aware セクション選択（Thompson Sampling）

全セクションを最適化する代わりに、改善余地の大きい上位N件に集中する。

- OPTS（ACL 2025）パターン: 各セクションを multi-armed bandit の「腕」として扱い、`Beta(alpha, beta)` で改善実績を追跡
- 事前の重要度推定として Leave-One-Out ablation（N+1コール）を実行し、各セクションの寄与度を算出
- 上位セクションのみ gradient 適用（コール数に上限を設定）

### 3. FrugalGPT スタイルのモデルカスケード

安価モデルでスクリーニング・重要度推定を行い、高価モデルは最終段の最適化のみに使用する。

- Phase 1（重要度推定）: Haiku/GPT-4o-mini 相当の安価モデル
- Phase 2（最適化生成）: 上位候補セクションのみ Sonnet/Opus で最適化
- Phase 3（最終評価）: トップN件の結果を高価モデルで評価

### 4. 早期停止ルール

セクション単位の停止条件を導入し、改善が見込めないセクションを打ち切る。

- プラトー検出: 連続N回改善なしで停止
- 収穫逓減: marginal_gain < 0.01 で停止
- バジェット上限: セクションあたりの最大コール数を設定

## Capabilities

### New Capabilities

- `strategy-router`: ファイルサイズに基づく手法自動選択（内部ロジック、ユーザー指定不要）
- `adaptive-granularity`: ファイルサイズに応じたセクション分割レベルの自動調整、小セクション統合
- `bandit-section-selector`: Thompson Sampling ベースのセクション優先度付け、Leave-One-Out 重要度推定
- `model-cascade`: 安価モデルによるスクリーニング + 高価モデルによる最適化のカスケード実行
- `early-stopping`: セクション単位の停止ルール（プラトー検出、収穫逓減、バジェット上限）

### Modified Capabilities

- `mpo-optimizer`: 既存の MPO パイプラインに strategy-router + 上記4機能を統合

## Impact

- `skills/genetic-prompt-optimizer/scripts/optimize.py`: `GeneticOptimizer` クラスに adaptive granularity, bandit selector, model cascade を統合
- `skills/genetic-prompt-optimizer/scripts/granularity.py`: 新規 — 適応的粒度制御モジュール
- `skills/genetic-prompt-optimizer/scripts/bandit_selector.py`: 新規 — Thompson Sampling セクション選択モジュール
- `skills/genetic-prompt-optimizer/scripts/model_cascade.py`: 新規 — モデルカスケード実行モジュール
- `skills/genetic-prompt-optimizer/SKILL.md`: 新オプション（`--budget`, `--cascade`, `--granularity`）の説明追加
- `skills/genetic-prompt-optimizer/tests/`: 各モジュールのユニットテスト追加
- 関連 Issue: #12, #8
- closes #13

## 参考文献

| 論文 | 出典 | 主な貢献 |
|------|------|---------|
| SPO | [EMNLP 2025](https://arxiv.org/abs/2502.06855) | ペアワイズ評価で評価コスト95%減 |
| OPTS | [ACL 2025](https://aclanthology.org/2025.findings-acl.1070/) | Thompson Sampling によるセクション選択 |
| TRIPLE | [NeurIPS 2024](https://arxiv.org/abs/2402.09723) | Successive Halving による候補の効率的評価 |
| GEPA | [ICLR 2026](https://arxiv.org/abs/2507.19457) | トレースベースフィードバック、35x ロールアウト削減 |
| FrugalGPT | [arXiv](https://arxiv.org/abs/2305.05176) | モデルカスケードで最大98%コスト削減 |
| TEP | [arXiv](https://arxiv.org/abs/2601.21064) | 局所均衡による勾配安定化 |
| GAAPO | [Frontiers 2025](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1613007/full) | 動的戦略配分、適応的粒度 |
| MPO | [arXiv](https://arxiv.org/abs/2601.04055) | セクション局所最適化、De-dup consolidation |
