## strategy-router

ファイルサイズに基づく最適化手法の自動選択ルーター。

### インターフェース

```python
def select_strategy(file_lines: int) -> Literal["self_refine", "budget_mpo"]:
    """ファイル行数に基づき最適化手法を選択"""
```

## ADDED Requirements

### Requirement: 手法選択ルール

- MUST: 200行未満のファイル → `"self_refine"` を返す
- MUST: 200行以上のファイル → `"budget_mpo"` を返す
- MUST: 閾値（200行）はモジュール先頭の定数 `STRATEGY_THRESHOLD` として定義する
- SHOULD: 閾値は将来的に設定ファイルで上書き可能にする

#### Scenario: 50行ファイルは self_refine

```
Given: 50行の Markdown スキルファイル
When: select_strategy(50) を呼び出す
Then: "self_refine" が返る
And: 批評→部分修正ループ（最大3回反復）で最適化される
```

#### Scenario: 300行ファイルは budget_mpo

```
Given: 300行の Markdown スキルファイル
When: select_strategy(300) を呼び出す
Then: "budget_mpo" が返る
And: 4フェーズパイプライン（粒度制御→重要度推定→バンディット選択→早期停止）で最適化される
```

#### Scenario: 境界値200行は budget_mpo

```
Given: ちょうど200行の Markdown スキルファイル
When: select_strategy(200) を呼び出す
Then: "budget_mpo" が返る
```

### Requirement: CLI による明示指定

- MUST: `--strategy self_refine` または `--strategy budget_mpo` が指定された場合、ファイルサイズ判定をスキップし指定値を使用する
- MUST: `--strategy auto`（デフォルト）の場合、手法選択ルールに従う
- MUST: `--budget N` が指定された場合、`--strategy auto` であっても `"budget_mpo"` を強制する

#### Scenario: --strategy 明示指定でサイズ判定をスキップ

```
Given: 50行の Markdown スキルファイル（通常は self_refine）
When: --strategy budget_mpo が CLI で指定されている
Then: ファイルサイズ判定をスキップし "budget_mpo" が使用される
```

### Requirement: GeneticOptimizer 統合

- MUST: `GeneticOptimizer._select_strategy()` メソッドとして統合する
- MUST: 選択された手法に応じて `_run_self_refine()` または `_run_budget_aware()` に分岐する
- SHOULD: 選択された手法名をログに出力する

#### Scenario: GeneticOptimizer が手法を自動選択して分岐する

```
Given: 300行のスキルファイルで GeneticOptimizer を実行する
When: _select_strategy() が呼ばれる
Then: "budget_mpo" が返る
And: _run_budget_aware() が実行される
And: ログに「strategy: budget_mpo」が出力される
```

### Requirement: 失敗時挙動

- MUST: `file_lines` が負の値 → `ValueError` を送出する
- MUST: `file_lines` が 0 → `"self_refine"` を返す

#### Scenario: 負の行数で ValueError

```
Given: file_lines = -1
When: select_strategy(-1) を呼び出す
Then: ValueError が送出される
```

### 参考

- prompt-optimizer-bench: short/medium は self_refine が最高品質（+0.36〜+0.45）、long は budget_mpo が最高効率
