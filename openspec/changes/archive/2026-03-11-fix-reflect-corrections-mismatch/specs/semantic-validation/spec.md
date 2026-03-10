## ADDED Requirements

### Requirement: LLM 件数不一致時のフォールバックは is_learning=True でパススルーしなければならない（MUST）
`semantic_analyze()` の LLM 応答が入力件数と不一致の場合、全件を `is_learning=False` で除外してはならない（MUST NOT）。成功分は LLM 判定を適用し、残りは `is_learning=True` でパススルーする（MUST）。

#### Scenario: LLM 応答件数が入力件数と不一致（partial success）
- **WHEN** 7件の corrections を LLM に送り、LLM が 5件分の結果を返す
- **THEN** LLM 応答の `index` フィールドで入力とマッチングし、マッチした5件は LLM の判定結果を適用し、残り2件は `is_learning=True` でパススルーする（MUST）。stderr に件数不一致の警告を出力する

#### Scenario: LLM 応答が完全にパース不能
- **WHEN** `claude -p` のレスポンスが不正な JSON でパースに完全に失敗する
- **THEN** 全件を `is_learning=True` でパススルーし（MUST）、stderr に警告を出力する。`is_learning=False` で全件除外してはならない（MUST NOT）

#### Scenario: LLM 応答が 0 件
- **WHEN** `claude -p` のレスポンスをパースした結果、空リストが返る
- **THEN** 全件を `is_learning=True` でパススルーする（MUST）

#### Scenario: LLM 呼び出しが例外で失敗
- **WHEN** `claude -p` の呼び出しがタイムアウトまたは OSError で失敗する
- **THEN** 全件を `is_learning=True` でパススルーし（MUST）、stderr に警告を出力する
