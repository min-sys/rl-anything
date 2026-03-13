## MODIFIED Requirements

### Requirement: Line limit violation confidence mapping
remediation の `compute_confidence_score` で、line_limit 違反の confidence を絶対行数差ベースで SHALL 算出する。

#### Scenario: Rule file exceeds limit by exactly 1 line
- **WHEN** ルールファイルが行数制限を1行だけ超過している（例: 4行/3行制限）場合
- **THEN** confidence を 0.95 に設定し、scope が file であれば auto_fixable に分類する

#### Scenario: Rule file exceeds limit by 2+ lines
- **WHEN** ルールファイルが行数制限を2行以上超過している場合
- **THEN** 従来通り proposable に分類する（既存動作を維持）

### Requirement: Line limit auto-fix function
FIX_DISPATCH に line_limit_violation の fix 関数を SHALL 追加する。LLM 1パス圧縮で内容を行数制限内に収める。

#### Scenario: Condense rule content to fit limit
- **WHEN** auto_fixable な line_limit_violation に対して fix を実行する
- **THEN** LLM に「行数制限内に圧縮」を指示し、修正後のファイルが行数制限を満たすことを検証する

#### Scenario: LLM compression fails to reduce line count
- **WHEN** LLM 圧縮後もファイルが行数制限を超過している場合
- **THEN** category を `proposable` に降格し、`record_outcome()` に `error: "compression_insufficient"` を記録する

#### Scenario: LLM invocation error
- **WHEN** LLM 呼び出しがタイムアウトまたは非ゼロ終了した場合
- **THEN** fix をスキップし、`record_outcome()` に `error` フィールドとしてエラー詳細を記録する
- **THEN** issue の category を `proposable` に降格する

### Requirement: Untagged reference confidence score
`compute_confidence_score` に `untagged_reference_candidates` のエントリを SHALL 追加する。

#### Scenario: Untagged reference candidate detected
- **WHEN** issue type が `untagged_reference_candidates` の場合
- **THEN** confidence 0.90 を返却する（audit のフィルタ済み候補のため高信頼）

### Normative Statements

- The system SHALL use absolute line excess (lines − limit) for confidence mapping, NOT ratio-based.
- When excess == 1, the system SHALL assign confidence 0.95.
- When excess >= 2, the system SHALL NOT promote to auto_fixable.
- The system SHALL call LLM via `subprocess.run(["claude", "--print", "-p", prompt])` for line_limit compression.
- The system MUST NOT execute LLM fix during dry-run mode.
- On LLM failure, the system SHALL demote the issue to `proposable` and record the error.
- The system SHALL assign confidence 0.90 to `untagged_reference_candidates` issues.
