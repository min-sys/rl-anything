## Context

現在の MPO（Modular Prompt Optimization）実装は `optimize.py` の `GeneticOptimizer` クラスでセクション単位の最適化を行う。各セクションに対して evaluate（1コール）+ update（1コール）= 2コールが必要で、セクション数に比例してコストが増大する。atlas-browser（1,180行、88セクション）では176コールとなり、1回のトライアルで数十ドル規模のコストが発生しうる。

Issue #13 のベストプラクティス調査で、SPO, OPTS, TRIPLE, FrugalGPT 等の手法を組み合わせることで 176コール → 20-30コール（高価モデル換算）に削減可能であることが示された。

prompt-optimizer-bench での検証により、ファイルサイズに応じた手法切り替えが最適であることが確認された:

| ファイルサイズ | ベスト手法 | Score Imp | Survival | Calls |
|-------------|----------|-----------|----------|-------|
| short (< 60行) | self_refine | +0.45 | 80% | 13 |
| medium (60-200行) | self_refine | +0.364 | 100% | 13 |
| long (200行超) | budget_mpo | +0.090 | 100% | 8 |

## Goals / Non-Goals

**Goals:**

- ファイルサイズに応じた最適化手法の自動切り替え（strategy-router）
- 大規模スキル（200行超 + references/）で MPO コール数を 80%以上削減する
- short/medium スキルでは self_refine で安定した品質を維持する
- `--budget N` で高価モデルのコール数上限を指定可能にする
- references/ 内の複数ファイルをファイル単位で並行最適化する

**Non-Goals:**

- SPO のペアワイズ評価の完全実装（Phase 2 以降で検討）
- GEPA のトレースベースフィードバック統合（別 change で対応）
- 新しい fitness 関数の追加

## Decisions

### 0. ファイルサイズベースの手法ルーターで最適手法を自動選択する

**選択**: ファイル行数に基づく2分岐

```python
def select_strategy(file_lines: int) -> str:
    if file_lines < 200:
        return "self_refine"   # 批評→部分修正ループ（最大3回反復）
    else:
        return "budget_mpo"    # 適応的粒度 + Thompson Sampling + カスケード
```

**理由**: bench 検証で short/medium は self_refine が最高品質（+0.36〜+0.45, survival 80-100%）、long は budget_mpo が最高効率（MPO 同等品質、コール数60%減）と判明。閾値 200行は `determine_split_level` の `h2_only` 判定と一致させる。

**代替案**: 全サイズで budget_mpo → small ファイルでは `_optimize_whole()` にフォールバックし self_refine と実質同じだが、不要なオーバーヘッド（importance scoring 等）が入る。

**注**: ユーザー向けの手法選択オプションは設けない。ファイルサイズで自動判定のみ。

### 1. 4フェーズパイプラインで段階的に処理する（budget_mpo パス）

**選択**: Phase 0（粒度制御）→ Phase 1（重要度推定）→ Phase 2（バンディット選択 + 最適化）→ Phase 3（早期停止）の4段パイプライン

```
入力: スキルファイル（SKILL.md + references/*.md）
  │
  ▼
Strategy Router: file_lines >= 200 → budget_mpo パス
  │                file_lines < 200  → self_refine パス
  ▼
Phase 0: Adaptive Granularity
  ├─ ファイルサイズ判定 → 分割レベル決定
  ├─ セクション分割
  └─ 小セクション統合（10行未満 → 親に merge）
  結果: 88セクション → ~35セクション
  │
  ▼
Phase 1: Importance Scoring (安価モデル)
  ├─ Leave-One-Out ablation: N+1 コールで各セクションの寄与度算出
  └─ importance_scores: Dict[section_id, float]
  結果: 各セクションに重要度スコア付与
  │
  ▼
Phase 2: Bandit Selection + Optimization (高価モデル)
  ├─ Thompson Sampling: Beta(α,β) から top-K セクションを選択
  ├─ 選択セクションに MPO gradient 適用
  └─ 結果に基づいて α/β を更新
  結果: 上位K件のみ最適化
  │
  ▼
Phase 3: Early Stopping + Consolidation
  ├─ セクション単位の停止判定
  ├─ De-dup consolidation（MPO 論文）
  └─ 最終結果の組み立て
  結果: 最適化済みスキル
```

**理由**: 各フェーズが独立にテスト可能で、段階的に導入できる。Phase 0 だけでも40%のコスト削減が見込める。

**代替案**: 全フェーズを一体化した単一パイプライン → テスト困難、段階導入不可、却下

### 2. Thompson Sampling で改善余地の大きいセクションを動的選択する

**選択**: OPTS（ACL 2025）の Thompson Sampling パターンを採用

```python
class BanditSectionSelector:
    def __init__(self, section_ids: list[str]):
        # 各セクションに Beta(1, 1) を初期化（一様事前分布）
        self.alpha = {sid: 1.0 for sid in section_ids}
        self.beta = {sid: 1.0 for sid in section_ids}

    def select_top_k(self, k: int) -> list[str]:
        """Thompson Sampling で上位k件を選択"""
        samples = {}
        for sid in self.alpha:
            samples[sid] = np.random.beta(self.alpha[sid], self.beta[sid])
        ranked = sorted(samples, key=samples.get, reverse=True)
        return ranked[:k]

    def update(self, section_id: str, improved: bool):
        """最適化結果に基づいて分布を更新"""
        if improved:
            self.alpha[section_id] += 1.0
        else:
            self.beta[section_id] += 1.0
```

- Leave-One-Out の重要度スコアを事前情報として `alpha` の初期値に反映可能
- 複数イテレーション実行時は前回の `alpha/beta` を引き継ぎ

**理由**: EvoPrompt 比 +7% accuracy（OPTS 論文）。実装がシンプルで、既存の `GeneticOptimizer` に自然に統合できる。

**代替案**: TRIPLE-SH（Successive Halving）→ 固定バジェット前提で柔軟性が低い。Thompson Sampling の方が adaptive。

### 3. FrugalGPT カスケードでモデルコストを段階化する

**選択**: 3段カスケード

| 段階 | 用途 | モデル | コール数 |
|------|------|--------|---------|
| Tier 1 | 重要度推定（LOO ablation） | 安価（Haiku相当） | N+1 |
| Tier 2 | セクション最適化（MPO gradient） | 中価（Sonnet相当） | K x 2 |
| Tier 3 | 最終評価 + De-dup consolidation | 高価（Opus相当） | 2-3 |

**実装**: `claude -p` の `--model` フラグ、または環境変数 `CLAUDE_MODEL` でモデルを切り替える。モデル名は設定ファイルで指定可能にする。

```python
class ModelCascade:
    def __init__(self, config: dict):
        self.tier1_model = config.get("tier1", "haiku")
        self.tier2_model = config.get("tier2", "sonnet")
        self.tier3_model = config.get("tier3", "opus")

    def run_with_tier(self, prompt: str, tier: int) -> str:
        model = [self.tier1_model, self.tier2_model, self.tier3_model][tier - 1]
        # claude -p --model {model} で実行
```

**理由**: FrugalGPT 論文では 60-70% のクエリが安価モデルで処理完了。重要度推定は精度要求が低いため安価モデルで十分。

**代替案**: 全て同一モデル → コスト最適化の余地がない。全て安価モデル → 最適化品質が低下。

**採用しないパターン**: RouteLLM（preference-based routing）→ preference データの事前収集が必要。本プロジェクトではセクション最適化の評価データが少なく cold start 問題がある。FrugalGPT の固定カスケードの方がデータ不要で確実。RouteLLM は将来データ蓄積後の拡張候補として記録。

### 4. 適応的粒度制御でセクション数を削減する

**選択**: ファイルサイズベースの3段階分割 + 小セクション統合

```python
def determine_split_level(file_lines: int) -> str:
    if file_lines < 60:
        return "none"        # TextGrad 一括
    elif file_lines <= 200:
        return "h2_h3"       # ## と ### で分割
    else:
        return "h2_only"     # ## のみで分割

def merge_small_sections(sections: list, min_lines: int = 10) -> list:
    """10行未満のセクションを前のセクションに統合"""
    merged = []
    for section in sections:
        if merged and len(section.lines) < min_lines:
            merged[-1].lines.extend(section.lines)
        else:
            merged.append(section)
    return merged
```

atlas-browser の場合:
- SKILL.md（319行）: `##` のみ → 32 → ~15セクション（小セクション統合後）
- pitfalls.md（294行）: `##` のみ → 16 → ~10セクション
- 他5ファイル（80-146行）: `##`/`###` 分割のまま → ~10セクション
- 合計: 88 → ~35セクション

**理由**: GAAPO の動的粒度制御に倣う。粒度制御だけで 50-60% のセクション削減が見込める。

**採用しないパターン**: Optimal Ablation（最適除去） → 除去対象の最適な組み合わせを探す追加コストが必要。LOO の相対順位付けで十分であり、実装もシンプル。TokenSHAP → N! の計算量でセクション数35では非実用的。

### 5. ファイル単位の並行最適化

**選択**: references/ 内のファイルは独立に MPO パイプライン実行。SKILL.md は最後に最適化。

```
atlas-browser/
├── SKILL.md              → 最後（references の結果を参照可能）
└── references/
    ├── pitfalls.md        ─┐
    ├── danger-zone.md     ─┤
    ├── expedition.md      ─┤ 並行実行可能
    ├── tile-click.md      ─┤
    ├── troubleshooting.md ─┤
    └── combat-debug.md    ─┘
```

**実装**: Python の `concurrent.futures.ThreadPoolExecutor` で並行実行。`--parallel N` で並行数を制御。

**理由**: references/ ファイル間に依存関係がないため、安全に並行化可能。壁時間を 1/N に短縮。

### 6. Prefix Caching 戦略

**選択**: 評価プロンプトの固定部分（ルーブリック）を先頭に配置し、API の Prefix Cache を活用する。

```
[固定部分: 評価ルーブリック + 基準定義]  ← キャッシュ対象
[可変部分: セクション内容]                ← 毎回変わる
```

**理由**: 評価の度にルーブリック部分が重複する。先頭固定で KV キャッシュ再利用率が最大 90%（Prefix Caching 論文）。

### 7. 既存 optimize.py との統合

**選択**: `GeneticOptimizer` に strategy-router を組み込み、ファイルサイズに応じて自動分岐する。`--budget` オプションで明示的に budget_mpo を強制することも可能。

```python
# optimize.py の main() に追加
parser.add_argument("--budget", type=int, default=None,
                    help="高価モデルのコール数上限（指定時は budget_mpo を強制）")
parser.add_argument("--strategy", choices=["auto", "self_refine", "budget_mpo"],
                    default="auto", help="最適化手法（auto=ファイルサイズで自動選択）")
parser.add_argument("--cascade", action="store_true",
                    help="モデルカスケードを有効化")
parser.add_argument("--parallel", type=int, default=1,
                    help="references/ の並行最適化数")

# GeneticOptimizer 内
def _select_strategy(self) -> str:
    if self.strategy != "auto":
        return self.strategy
    if self.budget is not None:
        return "budget_mpo"
    return select_strategy(self.file_lines)  # ファイルサイズで自動判定

# 分岐
strategy = self._select_strategy()
if strategy == "budget_mpo":
    return self._run_budget_aware()
else:
    return self._run_self_refine()
```

**理由**: ファイルサイズで自動判定するだけなのでユーザーが意識する必要がない。

## Risks / Trade-offs

**[粒度制御の精度]** 小セクション統合で文脈が失われる可能性がある。
→ 統合時に見出し情報は保持し、分割復元可能にする。統合前後でスコア比較するテストを追加。

**[Thompson Sampling の cold start]** 初期状態では全セクションが等確率で選択される。
→ Leave-One-Out の重要度スコアを事前情報として `alpha` の初期値に反映。初回から情報に基づいた選択が可能。

**[モデルカスケードの品質]** 安価モデルの重要度推定が不正確な場合、重要なセクションを見逃す。
→ Leave-One-Out は相対的な順位付けなので、絶対精度は不要。また、Thompson Sampling が exploration を担保するため、見逃しリスクは低い。

**[並行実行の整合性]** references/ ファイル間に暗黙の依存がある場合（例: pitfalls.md が他ファイルを参照）、並行最適化で不整合が生じる。
→ De-dup consolidation パス（Phase 3）で統合時に矛盾を検出・解消。

**[claude CLI のモデル指定]** `claude -p --model` でのモデル指定が将来変更される可能性。
→ モデル指定をコンフィグファイルに外出しし、CLI フラグに依存しない抽象層を設ける。

**[project-specific-fitness との並行変更]** evaluate フェーズが LLM CoT スコアリング前提だが、project-specific-fitness は execution-based evaluation を導入予定。evaluate() の設計が衝突する可能性がある。
→ budget_mpo の evaluate は `Callable[[str], float]` を受け取る設計にし、CoT/execution どちらでも差し替え可能にする。evaluate() のインターフェースを共通化し、両 change が独立に進められるようにする。

## 設定値の外出し方針

全ての閾値・モデル名はモジュール先頭の定数として定義し、将来的に設定ファイル（YAML）で上書き可能にする。

| 値 | デフォルト | 定義場所 | 上書き手段 |
|----|-----------|---------|-----------|
| STRATEGY_THRESHOLD | 200 | strategy_router.py | --strategy で迂回 |
| MIN_SECTION_LINES | 10 | granularity.py | 設定ファイル |
| LOO_ALPHA_SCALE | 5.0 | bandit_selector.py | 設定ファイル |
| PLATEAU_COUNT | 3 | early_stopping.py | 設定ファイル |
| MARGINAL_GAIN_THRESHOLD | 0.01 | early_stopping.py | 設定ファイル |
| TIER1_MODEL | "haiku" | model_cascade.py | 設定ファイル / 環境変数 |
| TIER2_MODEL | "sonnet" | model_cascade.py | 設定ファイル / 環境変数 |
| TIER3_MODEL | "opus" | model_cascade.py | 設定ファイル / 環境変数 |

## 共通化分析

| 対象 | 判断 | 説明 |
|------|------|------|
| Section データクラス | 新規（共通） | granularity.py に定義、bandit_selector/early_stopping から参照 |
| _extract_markdown() | 拡張 | セクション単位の抽出に対応（既存の code block 抽出と共存） |
| Individual.section_id | 拡張 | Optional[str] フィールド追加。budget_mpo パスでセクション追跡 |
| select_strategy() | 新規（専用） | strategy_router.py。optimize.py 以外から呼ぶ想定なし |
| ModelCascade | 新規（共通候補） | 将来 rl-loop-orchestrator からも利用可能だが、まず専用で実装 |
