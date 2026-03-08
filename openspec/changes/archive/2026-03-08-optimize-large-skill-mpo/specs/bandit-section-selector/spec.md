## bandit-section-selector

Thompson Sampling ベースのセクション優先度付けと Leave-One-Out 重要度推定。

### インターフェース

```python
class BanditSectionSelector:
    def __init__(self, section_ids: list[str]):
        """各セクションに Beta(1, 1) を初期化（一様事前分布）"""

    def initialize_from_importance(self, scores: dict[str, float], scale: float = 5.0):
        """LOO 重要度スコアを alpha の初期値に反映"""

    def select_top_k(self, k: int) -> list[str]:
        """Thompson Sampling で上位k件のセクションIDを返す"""

    def update(self, section_id: str, improved: bool):
        """最適化結果に基づいて Beta 分布を更新"""

    def get_state(self) -> dict[str, tuple[float, float]]:
        """全セクションの (alpha, beta) を返す（永続化用）"""

def estimate_importance(
    sections: list[Section],
    evaluator: Callable[[str], float],
    model: str = "haiku",
) -> dict[str, float]:
    """Leave-One-Out ablation で各セクションの重要度を推定（N+1コール）"""
```

## ADDED Requirements

### Requirement: Thompson Sampling アルゴリズム

- MUST: 各セクション `i` に `Beta(alpha_i, beta_i)` を維持する
- MUST: `select_top_k(k)` 呼び出し時、各セクションから `theta_i ~ Beta(alpha_i, beta_i)` をサンプリングし、`theta_i` の降順で上位 `k` 件を返す
- MUST: `update(section_id, improved=True)` は `alpha += 1`、`improved=False` は `beta += 1` とする
- MUST: `__init__` で全セクションを `Beta(1, 1)`（一様事前分布）に初期化する
- SHOULD: `scale` パラメータはモジュール先頭の定数 `LOO_ALPHA_SCALE` として定義する

#### Scenario: 35セクション+budget=20 での top-K 選択

```
Given: 35セクションが分割済みで budget=20
When: k = 20 // 2 = 10 を算出し select_top_k(10) を呼び出す
Then: Thompson Sampling により10セクションが選択される
And: 選択されたセクションのみが Phase 2 で最適化される
And: 最適化結果に基づき alpha/beta が更新される
```

### Requirement: LOO 重要度推定

- MUST: フルプロンプト（全セクション含む）を評価し `S_base` を取得する
- MUST: 各セクション `i` を除外したプロンプトを評価し `S_{-i}` を取得する
- MUST: 重要度を `importance_i = S_base - S_{-i}` で算出する（正の値 = 重要、負の値 = 削除候補）
- MUST: コスト = N+1 コール（N = セクション数）
- SHOULD: 安価モデル（Tier 1）で実行する

#### Scenario: LOO ablation で重要度を算出

```
Given: 5セクション（A, B, C, D, E）のスキル
When: estimate_importance(sections, evaluator) を呼び出す
Then: evaluator が 6回呼ばれる（ベースライン1回 + 各セクション除外5回）
And: 各セクションに importance スコアが付与される
And: importance が高いセクションは select_top_k で選択されやすくなる
```

### Requirement: LOO スコアから事前情報への変換

- MUST: `initialize_from_importance()` は LOO スコアを 0-1 に正規化した上で `alpha = 1.0 + normalized * scale` に設定する
- MUST: 負のスコアは `max(0.0, ...)` で 0 にクランプする
- SHOULD: `beta` はデフォルトの 1.0 を維持する

#### Scenario: LOO スコアが事前情報に反映される

```
Given: 3セクションの LOO スコア {"h2-0": 0.5, "h2-1": 0.1, "h2-2": -0.2}（scale=5.0）
When: initialize_from_importance(scores, scale=5.0) を呼び出す
Then: h2-0 の alpha = 1.0 + (0.5/0.5) * 5.0 = 6.0
And: h2-1 の alpha = 1.0 + (0.1/0.5) * 5.0 = 2.0
And: h2-2 の alpha = 1.0 + 0.0 * 5.0 = 1.0（負の値はクランプ）
```

### Requirement: --budget N の動作

- MUST: `budget` 指定時、Phase 2 の高価モデルコール数上限 = `budget` とする
- MUST: `k = budget // 2`（evaluate + update で2コール/セクション）で Thompson Sampling 選択する
- MUST: `budget` 未指定時、従来通り全セクションを最適化する（後方互換）

#### Scenario: budget 未指定時の後方互換

```
Given: budget が未指定（None）
When: BanditSectionSelector が使用される
Then: 全セクションが最適化対象として返される
And: 従来の MPO と同等の動作をする
```

### Requirement: 状態永続化

- MUST: 複数イテレーション実行時、`alpha/beta` を JSON で永続化する
- MUST: 保存先は `{output_dir}/bandit_state.json` とする
- SHOULD: 永続化ファイルが存在すれば読み込んで初期状態として使用する

#### Scenario: 前回の状態を引き継いで再開する

```
Given: bandit_state.json に {"h2-0": [3.0, 1.0], "h2-1": [1.0, 2.0]} が保存されている
When: BanditSectionSelector を初期化する
Then: h2-0 は Beta(3.0, 1.0)、h2-1 は Beta(1.0, 2.0) で開始する
And: 前回の学習結果が反映された選択が行われる
```

### Requirement: 失敗時挙動

- MUST: LOO ablation の evaluator 呼び出しが失敗した場合 → 一様事前分布 `Beta(1,1)` のまま Phase 2 に進む
- MUST: Thompson Sampling の `np.random.beta()` で例外発生時 → 一様ランダム選択にフォールバック
- MUST: `bandit_state.json` の読み込み失敗 → `Beta(1,1)` で新規開始し、警告をログ出力する
- MUST: `k` がセクション数を超える場合 → 全セクションを返す

#### Scenario: LOO 評価失敗時のフォールバック

```
Given: evaluator が TimeoutError を送出する
When: estimate_importance() が失敗する
Then: 全セクションが Beta(1,1) のまま Phase 2 に進む
And: 警告ログが出力される
```

### 参考

- OPTS（ACL 2025）: Thompson Sampling で prompt design strategy 選択、EvoPrompt 比 +7%
- TRIPLE（NeurIPS 2024）: 固定バジェット最良腕識別、Successive Halving
- POSIX（EMNLP 2024）: セクション感度分析（将来拡張候補）
