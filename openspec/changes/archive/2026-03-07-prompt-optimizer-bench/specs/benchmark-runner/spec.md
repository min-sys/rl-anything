## ADDED Requirements

### Requirement: CLI でベンチマークを実行できる

`runner.py` は CLI から以下のオプションで実行できなければならない（SHALL）。

```
python runner.py \
  --strategies baseline_ga,self_refine,gepa_lite \
  --targets tasks/meta_prompt/targets/*.md \
  --trials 5 \
  --output results/run_001.json
```

#### Scenario: 全手法 x 全ターゲットの実行

- **WHEN** `--strategies` に複数手法、`--targets` に複数ファイルを指定して実行する
- **THEN** 全組み合わせ（手法 x ターゲット x trials）を実行し、結果を JSON に保存する

### Requirement: 設定ファイルで実行パラメータを管理できる

YAML 設定ファイルで実行パラメータを定義できなければならない（SHALL）。

```yaml
strategies:
  - name: baseline_ga
    params: { generations: 3, population: 3 }
  - name: self_refine
    params: { max_iterations: 3 }
  - name: gepa_lite
    params: { max_iterations: 3 }

targets:
  - path: tasks/meta_prompt/targets/short_rule.md
    test_tasks: tasks/meta_prompt/test_tasks/short_rule.yaml
  - path: tasks/meta_prompt/targets/medium_skill.md
    test_tasks: tasks/meta_prompt/test_tasks/medium_skill.yaml

trials: 5
output_dir: results/
```

#### Scenario: 設定ファイル指定で実行

- **WHEN** `python runner.py --config bench.yaml` を実行する
- **THEN** 設定ファイルの内容に従ってベンチマークを実行する

### Requirement: ドライランモードを提供する

`--dry-run` オプションで LLM 呼び出しなしの構造テストを実行できなければならない（SHALL）。

#### Scenario: ドライラン実行

- **WHEN** `--dry-run` を指定して実行する
- **THEN** 全 Strategy の初期化・設定検証を行うが、LLM 呼び出しは行わない

### Requirement: 進捗を表示する

実行中の進捗をリアルタイムに表示しなければならない（SHALL）。

#### Scenario: 進捗表示

- **WHEN** ベンチマークが実行中
- **THEN** `[strategy] [target] [trial N/M] score=X.XX` 形式で進捗を表示する

### Requirement: 中断・再開ができる

実行が中断された場合、完了済みの試行をスキップして再開できなければならない（SHALL）。

#### Scenario: 中断後の再開

- **WHEN** 結果ファイルに一部の試行結果が記録されている状態で再実行する
- **THEN** 既に完了した試行をスキップし、未完了の試行から再開する
