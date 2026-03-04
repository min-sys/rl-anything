## MODIFIED Requirements

### Requirement: テンプレートベースの生成

fitness-template.py をスケルトンとして使用し、LLM で穴埋め・カスタマイズして最終的な関数を生成しなければならない（MUST）。テンプレートの `evaluate()` がスタブのまま実行された場合、黙って 0.5 を返してはならない（MUST NOT）。

#### Scenario: テンプレートの構造が維持される
- **WHEN** fitness 関数を生成する
- **THEN** fitness-template.py の基本構造（docstring、evaluate 関数、main 関数）が維持されなければならない（MUST）

#### Scenario: スタブ未実装のまま実行された場合
- **WHEN** `evaluate()` 内の `scores` 辞書が空のまま実行される
- **THEN** stderr に「評価ロジック未実装」の警告を出力し、0.0 を返さなければならない（MUST）

#### Scenario: 正常に実装済みの場合
- **WHEN** `evaluate()` 内の `scores` 辞書に1つ以上の評価軸が定義されている
- **THEN** 加重平均スコア（0.0〜1.0）を返す（従来動作を維持）
