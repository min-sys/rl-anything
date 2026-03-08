## ADDED Requirements

### Requirement: Compile ステージはパッチ生成とメモリルーティングを統合する
Compile ステージは optimize（パッチ生成 + regression gate）、remediation（audit 違反の自動修正）、reflect（corrections → メモリルーティング）を1ステージとして実行しなければならない（MUST）。

#### Scenario: corrections がある場合
- **WHEN** corrections.jsonl に未処理の corrections が存在する
- **THEN** optimize（パッチ生成）→ remediation → reflect の順に実行される

#### Scenario: corrections がない場合
- **WHEN** corrections.jsonl に未処理の corrections が存在しない
- **THEN** optimize はスキップされ、remediation → reflect のみ実行される

#### Scenario: Diagnose の診断結果を入力として受け取る
- **WHEN** Diagnose ステージが問題リストを出力している
- **THEN** Compile ステージはその診断結果を remediation の入力として使用する

### Requirement: Compile は共通 regression gate を使用する
optimize でのパッチ検証に `scripts/lib/regression_gate.py` の `check_gates()` を使用しなければならない（MUST）。optimize.py 内にゲートロジックをハードコードしてはならない（MUST NOT）。

#### Scenario: regression gate が共通ライブラリから呼ばれる
- **WHEN** optimize がパッチ候補を生成する
- **THEN** `scripts/lib/regression_gate.py` の `check_gates()` でゲートチェックを実行する

#### Scenario: ゲート不合格時の挙動
- **WHEN** パッチ候補が禁止パターン（TODO 等）を含む
- **THEN** optimize が `score=0.0` を設定し、LLM 評価をスキップする（既存の regression-gate spec 準拠。スコア設定は optimize の責務）
