## model-cascade

FrugalGPT カスケードによるモデルコストの段階化。タスクの要求精度に応じて異なるモデルを使い分ける。

### インターフェース

```python
class ModelCascade:
    def __init__(self, config: dict | None = None):
        """カスケード設定を読み込み、3段 Tier を初期化"""

    def get_model(self, tier: int) -> str:
        """指定 Tier のモデル名を返す"""

    def run_with_tier(self, prompt: str, tier: int) -> str:
        """指定 Tier のモデルでプロンプトを実行"""

    @property
    def enabled(self) -> bool:
        """カスケードが有効かどうか"""
```

## ADDED Requirements

### Requirement: 3段 Tier 構成

- MUST: 以下の3段構成でモデルを使い分ける

| Tier | 用途 | デフォルトモデル | コール数 |
|------|------|----------------|---------|
| Tier 1 | 重要度推定（LOO ablation） | Haiku 相当 | N+1 |
| Tier 2 | セクション最適化（MPO gradient） | Sonnet 相当 | K x 2 |
| Tier 3 | 最終評価 + De-dup consolidation | Opus 相当 | 2-3 |

- MUST: 各 Tier のモデル名は設定ファイルまたは環境変数で指定可能にする（ハードコード禁止）
- MUST: デフォルト値はモジュール先頭の定数 `TIER1_MODEL`, `TIER2_MODEL`, `TIER3_MODEL` として定義する

#### Scenario: カスケード有効で各 Tier が正常動作

```
Given: --cascade フラグが有効
When: Phase 1 で LOO ablation を実行する
Then: Tier 1（Haiku 相当）で N+1 回の評価が行われる
And: Phase 2 で Tier 2（Sonnet 相当）でセクション最適化が行われる
And: Phase 3 で Tier 3（Opus 相当）で最終評価が行われる
```

### Requirement: カスケード有効化

- MUST: `--cascade` CLI フラグで有効化する
- MUST: カスケード無効時（デフォルト）は従来通り単一モデルで動作する（後方互換）
- SHOULD: カスケード無効時は `ModelCascade` インスタンスを生成せず、既存パスをそのまま使用する

#### Scenario: カスケード無効時の後方互換

```
Given: --cascade フラグが未指定（デフォルト）
When: 最適化を実行する
Then: 従来通り単一モデルで全フェーズが処理される
And: ModelCascade は使用されない
```

### Requirement: モデル指定方法

- MUST: `claude -p --model {model}` または環境変数 `CLAUDE_MODEL` でモデルを切り替える
- SHOULD: 設定ファイル（YAML）による一括設定をサポートする
- MAY: Tier ごとに異なる temperature やパラメータを設定可能にする

#### Scenario: 設定ファイルでモデル名をカスタマイズ

```
Given: 設定ファイルに tier1: "claude-haiku-4-5-20251001" が指定されている
When: ModelCascade を初期化する
Then: Tier 1 のモデルが "claude-haiku-4-5-20251001" に設定される
```

### Requirement: 失敗時挙動

- MUST: Tier N のモデル呼び出しが失敗した場合 → Tier N+1 に直接エスカレーションする
- MUST: Tier 3（最高 Tier）が失敗した場合 → エラーを伝搬し、該当セクションの最適化をスキップする
- MUST: 設定ファイルのパースエラー → デフォルト値を使用し、警告をログ出力する
- MUST: 不正な Tier 番号（1-3 以外） → `ValueError` を送出する

#### Scenario: Tier 1 失敗時のエスカレーション

```
Given: --cascade フラグが有効
When: Tier 1 モデルが API エラーを返す
Then: Tier 2 モデルで LOO ablation を再実行する
And: 警告ログ「Tier 1 failed, escalating to Tier 2」が出力される
```

### 参考

- FrugalGPT（Chen et al., 2023）: 60-70% のクエリが安価モデルで処理完了
- 採用しないパターン: RouteLLM（preference-based routing）→ preference データの事前収集が必要。本プロジェクトではセクション最適化の評価データが少なく cold start 問題がある。FrugalGPT の固定カスケードの方がデータ不要で確実。RouteLLM は将来データ蓄積後の拡張候補として記録
