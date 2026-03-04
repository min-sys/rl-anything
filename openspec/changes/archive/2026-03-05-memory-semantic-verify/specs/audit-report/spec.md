## MODIFIED Requirements

### Requirement: /audit レポートに Memory Health セクションを含めなければならない（MUST）

audit.py の generate_report() は Memory Health セクションを含めなければならない（MUST）。Memory Health セクションは既存のルールベース検証（パス存在チェック + 肥大化警告）に加え、LLM セマンティック検証の結果サマリーを Semantic Verification サブセクションとして含めなければならない（MUST）。

Semantic Verification サブセクションは audit SKILL.md のステップで Claude Code が検証した結果を表示する。audit.py 自体は LLM を呼ばず、セマンティック検証用のコンテキスト収集のみを行う。

#### Scenario: Memory Health セクションにセマンティック検証結果が含まれる

- **WHEN** `/rl-anything:audit` を実行し、MEMORY に3セクションあり LLM 検証で1件が MISLEADING、1件が STALE と判定される
- **THEN** レポートの Memory Health セクション内に "### Semantic Verification" サブセクションが含まれ、MISLEADING 1件と STALE 1件の判定結果と修正提案が表示される

#### Scenario: 全セクションが CONSISTENT の場合

- **WHEN** MEMORY の全セクションが LLM 検証で CONSISTENT と判定される
- **THEN** "### Semantic Verification" サブセクションに「全セクション整合」と表示する

#### Scenario: auto-memory が存在しない場合

- **WHEN** auto-memory ディレクトリが存在せず global memory にも PJ 固有セクションがない
- **THEN** Semantic Verification サブセクションは表示しない
