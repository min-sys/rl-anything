## MODIFIED Requirements

### Requirement: Diagnose ステージはパターン検出と問題検出を統合する
Diagnose ステージは discover（パターン検出 + enrich 統合）、**skill triage（trigger eval 生成 + アクション判定）**、audit 問題検出（collect_issues）、reorganize（split 検出のみ）、全レイヤー診断（Rules / Memory / Hooks / CLAUDE.md）を1ステージとして実行しなければならない（MUST）。出力はレイヤー別の問題リストと候補リスト、**および triage 結果**を含まなければならない（MUST）。

#### Scenario: 全サブステップが実行される
- **WHEN** evolve が Diagnose ステージを実行する
- **THEN** discover（enrich 統合済み）、**skill triage**、audit 問題検出（全レイヤー診断含む）、reorganize（split 検出）が順に実行され、統合された診断結果が生成される

#### Scenario: discover がパターン未検出でも triage は実行される
- **WHEN** discover がパターンを検出しない（usage.jsonl のデータ不足等）
- **THEN** skill triage は sessions.jsonl から独立して実行され、audit と reorganize も正常に実行される

#### Scenario: triage 結果が evolve の出力に含まれる
- **WHEN** Diagnose ステージが完了する
- **THEN** evolve.py の出力 phases に `skill_triage` キーが含まれ、`CREATE`, `UPDATE`, `SPLIT`, `MERGE`, `OK` のアクション別スキルリストが格納される

#### Scenario: triage のデータ不足で graceful degradation
- **WHEN** sessions.jsonl のセッション数が不足し eval set 生成ができない
- **THEN** triage はスキップされ、`skill_triage: {"skipped": true, "reason": "insufficient_data"}` が出力に含まれる。他のサブステップは正常に実行される

#### Scenario: triage issue が collect_issues に統合される
- **WHEN** triage が UPDATE / SPLIT / MERGE 判定を出す
- **THEN** 各判定が issue_schema 準拠の issue として collect_issues() の結果に追加される

#### Scenario: レイヤー別診断結果が evolve の出力に含まれる
- **WHEN** Diagnose ステージが完了する
- **THEN** evolve.py の出力 phases に `layer_diagnose` キーが含まれ、`rules`, `memory`, `hooks`, `claudemd` の各レイヤーの issue リストが格納される

#### Scenario: 個別レイヤー診断がエラーでも他レイヤーは実行される
- **WHEN** `diagnose_hooks()` が settings.json の読み取りに失敗する
- **THEN** `diagnose_rules()`, `diagnose_memory()`, `diagnose_claudemd()` は正常に実行され、hooks のみエラーが記録される
