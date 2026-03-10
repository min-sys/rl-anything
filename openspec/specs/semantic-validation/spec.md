# semantic-validation Specification

## Purpose
corrections.jsonl のセマンティック検証、multi-target recommendation routing、および LLM スキップオプションを提供する analyze 拡張機能。

## Requirements
### Requirement: analyze 実行時に corrections をセマンティック検証しなければならない（MUST）
analyze コマンド実行時に、corrections.jsonl の未検証レコードを LLM に送り、「このユーザー発話は本当にスキルへの修正フィードバックか」を判定しなければならない（MUST）。

#### LLM 入力フィールド
LLM に送るフィールドは以下の 3 つとする（MUST）:
- `message`: ユーザーの発話テキスト（corrections.jsonl の `message` フィールド）
- `last_skill`: 直前に実行されたスキル名（null 許容）
- `confidence`: パターンマッチ由来の confidence 値（0.0〜1.0）

#### Prompt Template
```
以下のユーザー発話が、直前に実行されたスキルへの修正フィードバックかどうかを判定してください。

発話: {message}
直前スキル: {last_skill}
パターンマッチ confidence: {confidence}

JSON で回答してください:
{{"is_correction": bool, "confidence": float, "target_skill": string | null, "reason": string}}
```

#### Scenario: 真の修正が検証される
- **WHEN** correction レコード `{"message": "いや、そうじゃなくて optimize を使って", "last_skill": "evolve", "confidence": 0.85}` が LLM に送られる
- **THEN** LLM が `{"is_correction": true, "confidence": 0.90, "target_skill": "evolve"}` を返し、verified フラグが true に更新される

#### Scenario: 偽陽性が除外される
- **WHEN** correction レコード `{"message": "いや、いいね！完璧", "last_skill": "commit", "confidence": 0.85}` が LLM に送られる
- **THEN** LLM が `{"is_correction": false, "confidence": 0.10}` を返し、レコードが除外される

### Requirement: multi-target recommendation routing を実装しなければならない（MUST）
analyze の推奨アクションに `target` フィールドを含め、改善先を振り分けなければならない（MUST）。

#### Scenario: correction が多いスキルは改善推奨
- **WHEN** スキル X に verified correction が 3 件以上ある
- **THEN** recommendation の target が `"skill"` で、アクションが `"evolve で改善"` となる

#### Scenario: 高頻度パターンは CLAUDE.md 昇格推奨
- **WHEN** あるワークフローパターンが 10 回以上検出され、3 プロジェクト以上で使用されている
- **THEN** recommendation の target が `"claude_md"` で、アクションが `"CLAUDE.md にパターンを追加"` となる

#### Scenario: project 固有パターンは rule 推奨
- **WHEN** あるワークフローパターンが 5 回以上検出され、1 プロジェクトのみで使用されている
- **THEN** recommendation の target が `"rule"` で、アクションが `"rules/ に追加"` となる

### Requirement: --no-llm フラグでセマンティック検証をスキップできなければならない（MUST）
analyze に `--no-llm` オプションを追加し、パターンマッチのみで高速に結果を返せるようにしなければならない（MUST）。

#### Scenario: no-llm モード
- **WHEN** `analyze --no-llm` が実行される
- **THEN** corrections のパターンマッチ confidence のみで判定し、LLM 呼び出しを行わない

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
