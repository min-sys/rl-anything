## ADDED Requirements

### Requirement: Detect hardcoded environment-specific values in skill/rule files

`scripts/lib/hardcoded_detector.py` の `detect_hardcoded_values(file_path)` 関数は、skill/rule の Markdown ファイルを走査し、環境固有のハードコード値を検出して結果リストを返さなければならない (MUST)。検出対象は以下のパターンとする:

1. AWS ARN (`arn:aws:...`)
2. Slack ID (`[ABCUW][A-Z0-9]{10,}` — App ID, Bot ID, Channel ID)
3. サービス固有 URL (slack.com, amazonaws.com 等の具体パス付き)
4. API キー風文字列 (`xoxb-`, `xapp-`, `sk-`, `AKIA` プレフィックス)
5. 長い数値 ID (12桁以上の数値リテラル)

各検出結果は `{"line": int, "matched": str, "pattern_type": str, "context": str, "confidence_score": float}` 形式でなければならない (MUST)。

#### Scenario: Detect Slack App ID in SKILL.md
- **WHEN** SKILL.md に `slack_app_id: A04K8RZLM3Q` と記載されている
- **THEN** `pattern_type: "slack_id"`, `matched: "A04K8RZLM3Q"` を含む検出結果を返す

#### Scenario: Detect AWS ARN
- **WHEN** ファイルに `arn:aws:lambda:ap-northeast-1:123456789012:function:my-func` と記載されている
- **THEN** `pattern_type: "aws_arn"` を含む検出結果を返す

#### Scenario: Detect API key prefix
- **WHEN** ファイルに `xoxb-1234567890-abcdefghij` と記載されている
- **THEN** `pattern_type: "api_key"` を含む検出結果を返す

#### Scenario: File read error is skipped gracefully
- **WHEN** 対象ファイルが読み込めない（パーミッション不足、バイナリファイル等）
- **THEN** そのファイルをスキップし、空の検出結果リストを返さなければならない (MUST)。例外を上位に伝播させてはならない (MUST NOT)

#### Scenario: Encoding error is skipped gracefully
- **WHEN** 対象ファイルが UTF-8 以外のエンコーディングで記述されている
- **THEN** そのファイルをスキップし、空の検出結果リストを返さなければならない (MUST)

### Requirement: Exclude known safe patterns from detection

以下のパターンはハードコード値として検出してはならない (MUST NOT):

1. プレースホルダ表記: `${VAR}`, `<YOUR_APP_ID>`, `YOUR_*`, `xxx`, `EXAMPLE`
2. 明示的ダミー値: `A0123456789`（連番）、`000000000000`（ゼロ埋め）
3. 既知の定数名・設定キー: frontmatter のキー名自体、フォーマット定義文字列
4. `example.com` / `localhost` を含む URL
5. バージョン番号パターン: `v1.2.3`, `1.0.0-beta.1`, セマンティックバージョニング形式
6. 算術式・数式: 演算子 (`+`, `-`, `*`, `/`, `**`) を含む数値式
7. タイムスタンプ形式: Unix epoch 風の10桁数値、ISO 8601 日付の一部

#### Scenario: Skip placeholder values
- **WHEN** ファイルに `export SLACK_APP_ID=${SLACK_APP_ID}` と記載されている
- **THEN** 検出結果を返さない

#### Scenario: Skip dummy sequential ID
- **WHEN** ファイルに `例: A0123456789` と記載されている
- **THEN** 検出結果を返さない

#### Scenario: Skip localhost URL
- **WHEN** ファイルに `http://localhost:3000/api/test` と記載されている
- **THEN** 検出結果を返さない

#### Scenario: Skip version numbers
- **WHEN** ファイルに `version: 202401011234` と記載されている
- **THEN** 長数値 ID として検出してはならない (MUST NOT)

#### Scenario: Skip arithmetic expressions
- **WHEN** ファイルに `timeout = 1000 * 60 * 24` と記載されている
- **THEN** 検出結果を返さない

### Requirement: Inline suppression comment

ファイル内に `<!-- rl-allow: hardcoded -->` コメントが含まれる行は、検出対象から除外しなければならない (MUST)。抑制コメントは同一行にのみ適用される (MUST)。

#### Scenario: Suppressed line is not detected
- **WHEN** ファイルに `slack_app_id: A04K8RZLM3Q <!-- rl-allow: hardcoded -->` と記載されている
- **THEN** 検出結果を返さない

#### Scenario: Suppression does not affect other lines
- **WHEN** 1行目に `<!-- rl-allow: hardcoded -->` があり、2行目に `slack_app_id: A04K8RZLM3Q` がある
- **THEN** 2行目は検出結果を返さなければならない (MUST)

### Requirement: Integrate with audit collect_issues

`audit.py` の `collect_issues()` は `detect_hardcoded_values()` を全 skill/rule ファイルに対して実行し (MUST)、検出結果を `type: "hardcoded_value"` の issue として統一リストに追加しなければならない (MUST)。

#### Scenario: Hardcoded values appear in collect_issues output
- **WHEN** プロジェクト内の SKILL.md にハードコード Slack ID が存在する
- **THEN** `collect_issues()` の返却リストに `{"type": "hardcoded_value", "file": "...", "detail": {...}, "source": "detect_hardcoded_values"}` が含まれる

#### Scenario: No hardcoded values found
- **WHEN** プロジェクト内の全ファイルにハードコード値が存在しない
- **THEN** `collect_issues()` の返却リストに `type: "hardcoded_value"` の issue が含まれない

### Requirement: Show hardcoded value warnings in audit report

`generate_report()` の出力に「Hardcoded Values」警告セクションを追加しなければならない (MUST)。検出がない場合はセクション自体を省略しなければならない (MUST)。

#### Scenario: Report includes hardcoded value warnings
- **WHEN** `detect_hardcoded_values()` が1件以上の結果を返す
- **THEN** audit レポートに「Hardcoded Values」セクションが表示され、ファイル名・行番号・マッチ内容が列挙される

#### Scenario: Report omits section when no issues
- **WHEN** `detect_hardcoded_values()` が0件の結果を返す
- **THEN** audit レポートに「Hardcoded Values」セクションが表示されない
