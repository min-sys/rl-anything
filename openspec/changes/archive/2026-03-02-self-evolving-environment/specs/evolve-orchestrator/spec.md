## ADDED Requirements

### Requirement: /rl-anything:evolve スキルで全フェーズをワンコマンド実行しなければならない（MUST）
Observe データ確認 → Discover → Optimize → Prune → Report の全フェーズを1つのコマンドで実行しなければならない（MUST）。

#### Scenario: 通常実行
- **WHEN** ユーザーが `/rl-anything:evolve` を実行する
- **THEN** 各フェーズが順次実行され、最終レポートが表示される

#### Scenario: 観測データ不足時の自動スキップ
- **WHEN** 前回 evolve 実行以降のセッション数が3未満、または10観測未満のデータしかない
- **THEN** 「データ不足のためスキップ推奨」メッセージを表示し、ユーザーに実行/スキップの選択を提示しなければならない（MUST）

### Requirement: --dry-run モードを提供しなければならない（MUST）
レポートのみ出力し、変更は一切行わないモードを提供しなければならない（MUST）。

#### Scenario: dry-run 実行
- **WHEN** ユーザーが `/rl-anything:evolve --dry-run` を実行する
- **THEN** 各フェーズの結果がレポートとして表示されるが、ファイルへの変更は行われない

### Requirement: 日次実行を想定した設計にしなければならない（MUST）
使用頻度が高い場合は日次で実行することを想定しなければならない（MUST）。

#### Scenario: 連続実行時のべき等性
- **WHEN** evolve が前日にも実行されている
- **THEN** 前回以降の新規データのみを対象に処理し（MUST）、重複した提案を行ってはならない（MUST NOT）
