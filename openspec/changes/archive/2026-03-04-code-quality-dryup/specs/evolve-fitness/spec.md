## MODIFIED Requirements

### Requirement: Adversarial テンプレート提供関数の意図明確化

`generate_adversarial_candidates()` を `get_adversarial_templates()` にリネームし、関数名・docstring が「静的テンプレート辞書の提供」という実態を正確に反映しなければならない（MUST）。

#### Scenario: リネーム後の関数呼び出し
- **WHEN** `evolve_fitness()` が adversarial テンプレートを取得する
- **THEN** `get_adversarial_templates()` を呼び出し、テンプレート辞書のリストを受け取る

#### Scenario: 戻り値の構造維持
- **WHEN** `get_adversarial_templates()` を呼び出す
- **THEN** 既存と同一の `[{"name": str, "description": str, "prompt_hint": str}, ...]` 構造を返す

#### Scenario: 旧関数名の除去
- **WHEN** コードベースを `generate_adversarial_candidates` で検索する
- **THEN** 一致する箇所が存在しない
