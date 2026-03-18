## ADDED Requirements

### Requirement: rl-scorer に maxTurns を設定する
`agents/rl-scorer.md` の frontmatter に `maxTurns: 15` を設定し、採点の暴走を防止する（SHALL）。

#### Scenario: rl-scorer が 15 ターン以内で完了する
- **WHEN** rl-scorer エージェントが採点を実行する
- **THEN** 最大 15 ターンで処理が終了する

### Requirement: rl-scorer に disallowedTools を設定する
`agents/rl-scorer.md` の frontmatter に `disallowedTools: [Edit, Write, Bash]` を設定し、採点エージェントがコードを変更しないことを保証する（SHALL）。
Agent tool は含めない（SHALL NOT）。rl-scorer は 3 サブエージェントを Agent tool で起動するため。

#### Scenario: rl-scorer が Edit/Write/Bash を使用できない
- **WHEN** rl-scorer エージェントが採点中にファイル変更を試みる
- **THEN** Edit, Write, Bash ツールは利用不可でブロックされる

#### Scenario: rl-scorer が Agent tool でサブエージェントを起動できる
- **WHEN** rl-scorer が 3 サブエージェント（tech/struct/domain）を起動する
- **THEN** Agent tool は利用可能で正常に動作する
