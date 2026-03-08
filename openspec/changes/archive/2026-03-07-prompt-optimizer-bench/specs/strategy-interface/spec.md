## ADDED Requirements

### Requirement: BaseStrategy ABC を定義する

各最適化手法は `BaseStrategy` を継承し、統一インターフェースで動作しなければならない（SHALL）。

```python
class BaseStrategy(ABC):
    name: str                              # 手法名（例: "self_refine"）
    requires_pip: list[str]                # 追加 pip 依存（空リストなら Phase 1）

    @abstractmethod
    def mutate(self, content: str, context: MutationContext) -> MutationResult: ...

    @abstractmethod
    def evaluate(self, original: str, mutated: str) -> EvaluationResult: ...

    def should_stop(self, history: list[EvaluationResult]) -> bool: ...
```

#### Scenario: Strategy の登録と列挙

- **WHEN** `runner.py` が実行される
- **THEN** `strategies/` ディレクトリの全 Strategy が自動検出され、`--strategy` オプションで名前指定できる

### Requirement: MutationContext で改善方向を指示できる

`mutate()` に渡す `MutationContext` は、テレメトリデータや診断結果を含むことができなければならない（SHALL）。

```python
@dataclass
class MutationContext:
    target_path: str
    diagnosis: str | None = None       # 弱点診断（GEPA用）
    pitfalls: list[str] | None = None  # 過去の失敗パターン
    usage_stats: dict | None = None    # 使用統計
```

#### Scenario: コンテキストなしでも動作する

- **WHEN** `MutationContext` のオプションフィールドが全て None
- **THEN** Strategy はフォールバック動作（コンテキストなしの変異）を実行する

### Requirement: Phase 1 の3手法を実装する

以下の3手法を `BaseStrategy` 実装として提供しなければならない（SHALL）。

| Strategy | クラス名 | pip依存 |
|----------|---------|---------|
| 現行 GA | `BaselineGAStrategy` | なし |
| Self-Refine | `SelfRefineStrategy` | なし |
| GEPA-lite | `GEPALiteStrategy` | なし |

#### Scenario: Phase 1 は pip 依存なしで動作する

- **WHEN** Phase 1 の3手法のみを使用する
- **THEN** `claude` CLI のみで動作し、追加の pip install は不要

### Requirement: Phase 2 の手法を追加できる

Phase 2 で以下の手法を追加できる拡張ポイントを設けなければならない（SHALL）。

| Strategy | クラス名 | pip依存 |
|----------|---------|---------|
| TextGrad | `TextGradStrategy` | `textgrad` |
| DSPy MIPROv2 | `DSPyStrategy` | `dspy` |

#### Scenario: 未インストールの Strategy を指定した場合

- **WHEN** `--strategy textgrad` を指定したが `textgrad` パッケージが未インストール
- **THEN** 「pip install textgrad が必要です」と明確なエラーメッセージを表示する

### Requirement: Self-Refine Strategy は批評→修正ループで変異する

`SelfRefineStrategy.mutate()` は全文書き直しではなく、批評→部分修正の反復ループで変異を生成しなければならない（SHALL）。

#### Scenario: 批評→修正ループ

- **WHEN** `SelfRefineStrategy.mutate()` が呼ばれる
- **THEN** (1) 元のスキルを批評させる → (2) 批評に基づく部分修正を生成させる → (3) 修正結果を再批評 → (4) 収束 or 最大N回で終了

#### Scenario: 出力の完全性

- **WHEN** Self-Refine が修正を生成する
- **THEN** 出力は元のスキルの全セクションを含み、途中で途切れない

### Requirement: GEPA-lite Strategy は診断に基づいて変異する

`GEPALiteStrategy.mutate()` は `MutationContext` の診断データを読み、弱点を特定してから変異を生成しなければならない（SHALL）。

#### Scenario: 診断データありの変異

- **WHEN** `MutationContext.diagnosis` が提供される
- **THEN** 変異プロンプトに診断結果を含め、特定された弱点を修正する方向で変異を生成する

#### Scenario: 診断データなしのフォールバック

- **WHEN** `MutationContext.diagnosis` が None
- **THEN** LLM に自己診断させてから変異を生成する
