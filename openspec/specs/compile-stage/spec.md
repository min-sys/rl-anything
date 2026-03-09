## ADDED Requirements

### Requirement: Compile ステージはパッチ生成とメモリルーティングを統合する
Compile ステージは optimize（パッチ生成 + regression gate）、remediation（audit 違反の自動修正）、reflect（corrections → メモリルーティング）を1ステージとして実行しなければならない（MUST）。remediation は collect_issues() の結果を受け取る（MUST）。collect_issues() は内部で diagnose_all_layers() を統合済みのため、別途マージする必要はない。

#### Scenario: corrections がある場合
- **WHEN** corrections.jsonl に未処理の corrections が存在する
- **THEN** optimize（パッチ生成）→ remediation → reflect の順に実行される

#### Scenario: corrections がない場合
- **WHEN** corrections.jsonl に未処理の corrections が存在しない
- **THEN** optimize はスキップされ、remediation → reflect のみ実行される

#### Scenario: Diagnose の診断結果を入力として受け取る
- **WHEN** Diagnose ステージが全レイヤー（Skill + Rules + Memory + Hooks + CLAUDE.md）の問題リストを出力している
- **THEN** Compile ステージはその診断結果を remediation の入力として使用する

#### Scenario: collect_issues() が diagnose_all_layers() を内部統合済み
- **WHEN** Diagnose ステージが collect_issues() を実行した
- **THEN** collect_issues() は内部で diagnose_all_layers() を呼び出し統合済みのため、Compile ステージは collect_issues() の結果のみを remediation に渡す（別途マージ不要）

### Requirement: Compile は共通 regression gate を使用する
optimize でのパッチ検証に `scripts/lib/regression_gate.py` の `check_gates()` を使用しなければならない（MUST）。optimize.py 内にゲートロジックをハードコードしてはならない（MUST NOT）。remediation の修正後検証にも verify_fix() と check_regression() を使用しなければならない（MUST）。

#### Scenario: regression gate が共通ライブラリから呼ばれる
- **WHEN** optimize がパッチ候補を生成する
- **THEN** `scripts/lib/regression_gate.py` の `check_gates()` でゲートチェックを実行する

#### Scenario: ゲート不合格時の挙動
- **WHEN** パッチ候補が禁止パターン（TODO 等）を含む
- **THEN** optimize が `score=0.0` を設定し、LLM 評価をスキップする

#### Scenario: remediation 修正後の検証
- **WHEN** remediation が auto_fixable issue を修正した
- **THEN** verify_fix() で問題解消を確認し、check_regression() で副作用を検証する

#### Scenario: regression 検出時のロールバック
- **WHEN** check_regression() が issues を検出した
- **THEN** rollback_fix() で修正前の内容に復元し、修正結果を "rollback" として記録する

## MODIFIED Requirements (self-evolution)

### Requirement: Self-evolution phase in Compile stage
Compile ステージは既存の Phase 5（Fitness Evolution）の後に Phase 6（Self-Evolution）を実行しなければならない（MUST）。Phase 6 は pipeline-trajectory-analysis → confidence-calibration → adaptive-pipeline-config の順に実行する。

#### Scenario: Data sufficient for self-evolution
- **WHEN** remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件以上の outcome が存在する
- **THEN** Phase 6 が trajectory analysis → calibration 提案 → ユーザー確認の順に実行される

#### Scenario: Data insufficient — skip self-evolution
- **WHEN** remediation-outcomes.jsonl に `MIN_OUTCOMES_FOR_ANALYSIS`（デフォルト: 20）件未満のレコードしかない
- **THEN** Phase 6 をスキップし、「Self-evolution: データ不足（N/`MIN_OUTCOMES_FOR_ANALYSIS` 件）、スキップ」と表示する

#### Scenario: Dry-run mode
- **WHEN** `dry_run=True` で実行される
- **THEN** Phase 6 の分析・表示は通常通り行うが、状態ファイル（evolve-state.json, confidence-calibration.json, pipeline-proposals.jsonl）への書き込みは行わない

### Requirement: State management for self-evolution
Self-evolution の実行状態を `evolve-state.json` に記録しなければならない（SHALL）。

#### Scenario: Calibration timestamp recorded
- **WHEN** self-evolution Phase 6 が正常に完了した
- **THEN** `evolve-state.json` の `last_calibration_timestamp` が現在時刻で更新される

#### Scenario: Calibration history preserved
- **WHEN** 新しいキャリブレーション結果が生成された
- **THEN** `evolve-state.json` の `calibration_history` に結果が追記され、既存の履歴は保持される
