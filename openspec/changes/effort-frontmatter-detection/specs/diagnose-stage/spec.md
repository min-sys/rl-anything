## MODIFIED Requirements

### Requirement: Diagnose ステージはパターン検出と問題検出を統合する
Diagnose ステージは discover（パターン検出 + enrich 統合）、skill triage（trigger eval 生成 + アクション判定）、audit 問題検出（collect_issues）、reorganize（split 検出のみ）、全レイヤー診断（Rules / Memory / Hooks / CLAUDE.md）、**effort 未設定スキル検出**を1ステージとして実行しなければならない（MUST）。出力はレイヤー別の問題リストと候補リスト、triage 結果、**および effort 検出結果**を含まなければならない（MUST）。

#### Scenario: 全サブステップが実行される
- **WHEN** evolve が Diagnose ステージを実行する
- **THEN** discover（enrich 統合済み）、skill triage、audit 問題検出（全レイヤー診断含む）、reorganize（split 検出）、**effort 未設定検出**が順に実行され、統合された診断結果が生成される

#### Scenario: effort 検出結果が issue に変換される
- **WHEN** audit の collect_issues() が effort 未設定スキルを検出する
- **THEN** `missing_effort` 型の issue として issues リストに追加され、remediation で `MISSING_EFFORT_CANDIDATE` として処理される

#### Scenario: discover がパターン未検出でも triage は実行される
- **WHEN** discover がパターンを検出しない（usage.jsonl のデータ不足等）
- **THEN** skill triage は sessions.jsonl から独立して実行され、audit と reorganize も正常に実行される

#### Scenario: triage 結果が evolve の出力に含まれる
- **WHEN** Diagnose ステージが完了する
- **THEN** evolve.py の出力 phases に `skill_triage` キーが含まれ、`CREATE`, `UPDATE`, `SPLIT`, `MERGE`, `OK` のアクション別スキルリストが格納される

#### Scenario: triage のデータ不足で graceful degradation
- **WHEN** sessions.jsonl のセッション数が不足し eval set 生成ができない
- **THEN** triage はスキップされ、`skill_triage: {"skipped": true, "reason": "insufficient_data"}` が出力に含まれる。他のサブステップは正常に実行される
