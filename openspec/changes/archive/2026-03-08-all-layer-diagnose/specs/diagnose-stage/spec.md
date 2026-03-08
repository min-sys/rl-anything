## MODIFIED Requirements

### Requirement: Diagnose ステージはパターン検出と問題検出を統合する
Diagnose ステージは discover（パターン検出 + enrich 統合）、audit 問題検出（collect_issues）、reorganize（split 検出のみ）、**全レイヤー診断（Rules / Memory / Hooks / CLAUDE.md）** を1ステージとして実行しなければならない（MUST）。出力はレイヤー別の問題リストと候補リストを含まなければならない（MUST）。

#### Scenario: 全サブステップが実行される
- **WHEN** evolve が Diagnose ステージを実行する
- **THEN** discover（enrich 統合済み）、audit 問題検出（全レイヤー診断含む）、reorganize（split 検出）が順に実行され、統合された診断結果が生成される

#### Scenario: discover がパターン未検出でも他のサブステップは実行される
- **WHEN** discover がパターンを検出しない（usage.jsonl のデータ不足等）
- **THEN** audit 問題検出（全レイヤー診断含む）と reorganize（split 検出）は正常に実行される

#### Scenario: レイヤー別診断結果が evolve の出力に含まれる
- **WHEN** Diagnose ステージが完了する
- **THEN** evolve.py の出力 phases に `layer_diagnose` キーが含まれ、`rules`, `memory`, `hooks`, `claudemd` の各レイヤーの issue リストが格納される

#### Scenario: 個別レイヤー診断がエラーでも他レイヤーは実行される
- **WHEN** `diagnose_hooks()` が settings.json の読み取りに失敗する
- **THEN** `diagnose_rules()`, `diagnose_memory()`, `diagnose_claudemd()` は正常に実行され、hooks のみエラーが記録される

## ADDED Requirements

### Requirement: Diagnose は session-scan を実行しない
discover のテキストレベルパターンマイニング（session-scan）は実行してはならない（MUST NOT）。usage.jsonl ベースのパターン検出のみを使用しなければならない（MUST）。

#### Scenario: session-scan が呼ばれない
- **WHEN** Diagnose ステージが実行される
- **THEN** discover 内の session-scan 関連コード（テキストマイニング）は実行されない
