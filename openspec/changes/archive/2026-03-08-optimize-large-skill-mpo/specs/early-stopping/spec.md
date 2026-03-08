## early-stopping

セクション単位の早期停止ルール。品質収束・コスト上限に基づき不要な最適化を打ち切る。

### インターフェース

```python
@dataclass
class EarlyStopRule:
    quality_threshold: float = 0.95
    plateau_count: int = 3
    budget_limit: int | None = None
    marginal_gain_threshold: float = 0.01

def should_stop(
    section_id: str,
    history: list[float],
    rule: EarlyStopRule,
    cumulative_cost: int | None = None,
) -> tuple[bool, str]:
    """停止判定。(停止するか, 停止理由) を返す"""
```

## ADDED Requirements

### Requirement: 4つの停止条件

- MUST: 以下の4条件のいずれかを満たしたら停止する

| 条件 | 判定ルール | デフォルト値 |
|------|-----------|------------|
| 品質到達 | `history[-1] >= quality_threshold` | 0.95 |
| プラトー検出 | 直近 `plateau_count` 回の改善なし（スコア単調非増加） | 3回 |
| バジェット上限 | 高価モデルコール数が `budget_limit` に到達 | None（無制限） |
| 収穫逓減 | `history[-1] - history[-2] < marginal_gain_threshold` | 0.01 |

- MUST: 停止理由を文字列で返す（例: `"plateau"`, `"budget_reached"`, `"quality_reached"`, `"diminishing_returns"`）
- MUST: `history` が空または1件以下の場合は停止しない

#### Scenario: 連続3回改善なしでプラトー停止

```
Given: セクション "h2-3" の history = [0.60, 0.72, 0.75, 0.75, 0.75]
When: should_stop("h2-3", history, rule) を呼び出す（plateau_count=3）
Then: (True, "plateau") が返る
And: ログに「h2-3: stopped (plateau), final_score=0.75」が出力される
```

#### Scenario: marginal_gain が閾値未満で収穫逓減停止

```
Given: セクション "h2-1" の history = [0.80, 0.805]
When: should_stop("h2-1", history, rule) を呼び出す（marginal_gain_threshold=0.01）
Then: (True, "diminishing_returns") が返る（改善幅 0.005 < 0.01）
```

#### Scenario: 品質到達で停止

```
Given: セクション "h2-0" の history = [0.70, 0.85, 0.96]
When: should_stop("h2-0", history, rule) を呼び出す（quality_threshold=0.95）
Then: (True, "quality_reached") が返る
```

### Requirement: 停止閾値の設定

- MUST: 全閾値はモジュール先頭の定数として定義する（`PLATEAU_COUNT`, `MARGINAL_GAIN_THRESHOLD` 等）
- SHOULD: 設定ファイル（YAML）で上書き可能にする
- MAY: セクションごとに異なる停止条件を設定可能にする

#### Scenario: デフォルト閾値で初期化される

```
Given: EarlyStopRule をデフォルトで初期化する
When: rule = EarlyStopRule()
Then: quality_threshold=0.95, plateau_count=3, marginal_gain_threshold=0.01
```

### Requirement: 累積コスト上限による停止

- MUST: `--budget` で指定された高価モデルコール数に達したら、未完了の全セクションを停止する
- SHOULD: `cumulative_cost` は Phase 2 の Tier 2/Tier 3 コール数の合計とする
- MUST: `budget_limit` が None の場合、コストによる停止は行わない

#### Scenario: 累積コスト上限で全セクション停止

```
Given: budget_limit=20 で cumulative_cost=20 に到達
When: should_stop(section_id, history, rule, cumulative_cost=20) を呼び出す
Then: (True, "budget_reached") が返る
And: 未完了の他セクションも全て停止される
```

### Requirement: 停止理由のログ出力

- MUST: 停止時、どの条件で停止したかをログに出力する
- SHOULD: セクションID + 停止理由 + 最終スコアを含める

#### Scenario: 停止理由がログに出力される

```
Given: セクション "h2-5" が品質到達で停止する
When: should_stop() が (True, "quality_reached") を返す
Then: ログに「h2-5: stopped (quality_reached), final_score=0.96」が出力される
```

### Requirement: 失敗時挙動

- MUST: 停止判定ロジックで例外が発生した場合 → 停止せず続行する（安全側に倒す）
- SHOULD: `history` に NaN や Inf が含まれる場合 → 該当エントリを無視して判定する
- MUST: `EarlyStopRule` のパラメータが不正（負の値等）→ デフォルト値を使用し、警告をログ出力する

#### Scenario: 停止判定エラー時は続行

```
Given: history に予期しない型の値が含まれる
When: should_stop() 内で TypeError が発生する
Then: (False, "") が返る（停止せず続行）
And: エラーログが出力される
```

### 参考

- SPO（ICML 2024）: 収束判定による早期停止
- Cost-aware stopping（BO 論文, 2025）: コスト考慮の停止基準
