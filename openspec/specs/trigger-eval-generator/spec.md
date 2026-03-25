## ADDED Requirements

### Requirement: Generate eval set from telemetry
`trigger_eval_generator.py` の `generate_eval_set()` は sessions.jsonl + usage.jsonl からスキルごとの trigger eval set を生成する（SHALL）。出力は skill-creator 互換の JSON 配列フォーマットとする（MUST）。

#### Scenario: Skill with sufficient session data
- **WHEN** `channel-routing` スキルが5セッションで使用されており、3セッションでトリガーワード「チャンネル」を含むが未使用
- **THEN** should_trigger クエリ5件 + should_not_trigger クエリ3件の eval set が生成される

#### Scenario: Insufficient session data
- **WHEN** スキルの関連セッションが MIN_EVAL_QUERIES (3) 未満
- **THEN** eval set 生成をスキップし `{"skipped": true, "reason": "insufficient_data", "available": N}` を返す

#### Scenario: Output format is skill-creator compatible
- **WHEN** eval set が正常に生成される
- **THEN** 出力は `[{"query": "...", "should_trigger": true}, ...]` の JSON 配列で、skill-creator の `run_eval.py --eval-set` に直接渡せるフォーマットとなる

### Requirement: Should-trigger query extraction
should_trigger クエリは、対象スキルが実際に使用されたセッションの `user_prompts` から抽出する（SHALL）。複数プロンプトがあるセッションでは、スキル名/トリガーワードとの一致度が最も高いプロンプトを優先する（SHALL）。

**マルチプロンプト戦略**: sessions.jsonl は user_prompts の順序を保持するが、usage レコードとの厳密な時系列紐付けは不可。セッション内の全 user_prompts を should_trigger 候補とし、`skill_triggers.py` のトリガーワードに最もマッチするものを優先選択する。

#### Scenario: Single prompt session
- **WHEN** セッションに1つの user_prompt 「CDKでLambdaをデプロイしたい」があり、`aws-cdk-deploy` が使用された
- **THEN** `{"query": "CDKでLambdaをデプロイしたい", "should_trigger": true}` が生成される

#### Scenario: Multi-prompt session with trigger word matching
- **WHEN** セッションに user_prompts [「こんにちは」, 「CDKのデプロイでエラーが出た」, 「ログを見せて」] があり、`aws-cdk-deploy` が使用された
- **AND** `aws-cdk-deploy` のトリガーワードが「CDK」「デプロイ」「deploy」を含む
- **THEN** トリガーワードとの一致度が最も高い「CDKのデプロイでエラーが出た」が should_trigger クエリとして抽出される

#### Scenario: Multi-prompt session with no clear match
- **WHEN** セッションに user_prompts [「インフラの問題を調べて」, 「詳細を教えて」] があり、`aws-cdk-deploy` が使用された
- **AND** いずれのプロンプトもトリガーワードに明確にマッチしない
- **THEN** 最初のプロンプト「インフラの問題を調べて」が should_trigger クエリとして抽出される（フォールバック: 先頭優先）

### Requirement: Should-not-trigger query generation
should_not_trigger クエリは以下の2ソースから生成する（SHALL）。各ソースに `confidence_weight` を付与し、eval set 生成時の優先度を制御する。

1. **Near-miss** (`confidence_weight: 1.0`): 対象スキルのトリガーワードを含むが、**別のスキル**が使用されたセッション。最も信頼性の高い should_not_trigger 根拠
2. **Unrelated** (`confidence_weight: 0.6`): トリガーワードに部分一致するが、スキルが全く使用されなかったセッション。偶然の一致を含む可能性がある

eval set 生成時には near-miss を優先的に採用し、near-miss だけで `TARGET_EVAL_QUERIES` に達しない場合に unrelated で補完する（SHALL）。

#### Scenario: Near-miss query from different skill usage
- **WHEN** 「デプロイの設定を確認したい」セッションでトリガーワード「デプロイ」が `aws-cdk-deploy` にマッチするが、実際には `config-review` が使用された
- **THEN** `{"query": "デプロイの設定を確認したい", "should_trigger": false, "confidence_weight": 1.0}` が生成される

#### Scenario: Unrelated query with keyword overlap
- **WHEN** 「チャンネルの動画をダウンロードしたい」でトリガーワード「チャンネル」が `channel-routing` にマッチするが、スキル未使用
- **THEN** `{"query": "チャンネルの動画をダウンロードしたい", "should_trigger": false, "confidence_weight": 0.6}` が生成される

#### Scenario: Near-miss prioritization in eval set
- **WHEN** near-miss 候補が8件、unrelated 候補が5件あり、TARGET_EVAL_QUERIES=10
- **THEN** near-miss 8件を優先採用し、unrelated から2件を補完して合計10件の should_not_trigger eval set を構成する

### Requirement: Eval set balance and limits
eval set は should_trigger と should_not_trigger のバランスを維持する（SHALL）。各カテゴリ最低 MIN_EVAL_QUERIES (3) 件、目標 TARGET_EVAL_QUERIES (10) 件とする。合計が TARGET を超える場合は各カテゴリからランダムサンプリングする（SHALL）。

#### Scenario: Balanced eval set
- **WHEN** should_trigger 候補が15件、should_not_trigger 候補が8件ある
- **THEN** should_trigger 10件、should_not_trigger 8件にサンプリングされる（多い方を TARGET に切り詰め）

#### Scenario: Minimum threshold enforcement
- **WHEN** should_trigger 候補が5件、should_not_trigger 候補が2件（MIN未満）
- **THEN** eval set 生成をスキップし insufficient_data を返す

### Requirement: Eval set file output
生成された eval set は `~/.claude/rl-anything/eval-sets/<skill-name>.json` に保存する（SHALL）。既存ファイルがある場合は上書きする。

#### Scenario: File output path
- **WHEN** `aws-cdk-deploy` の eval set が生成される
- **THEN** `~/.claude/rl-anything/eval-sets/aws-cdk-deploy.json` に保存される

#### Scenario: Directory creation
- **WHEN** `eval-sets/` ディレクトリが存在しない
- **THEN** ディレクトリを自動作成してからファイルを保存する
