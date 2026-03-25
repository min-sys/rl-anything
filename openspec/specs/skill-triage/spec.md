## ADDED Requirements

### Requirement: Triage action determination
`skill_triage.py` の `triage_skill()` は、テレメトリデータと trigger eval 結果を統合し、各スキルに対して CREATE / UPDATE / SPLIT / MERGE / OK の5択アクション判定を行う（SHALL）。

#### Scenario: CREATE judgment
- **WHEN** `detect_missed_skills()` が `deploy-check` を 4セッションで検出し、同名スキルが存在しない
- **THEN** `{"action": "CREATE", "skill": "deploy-check", "confidence": 0.85, "evidence": {"missed_sessions": 4}}` が返される

#### Scenario: UPDATE judgment
- **WHEN** `aws-cdk-deploy` スキルが存在し、missed_skill として3セッションで検出され、near-miss クエリが2件以上ある
- **THEN** `{"action": "UPDATE", "skill": "aws-cdk-deploy", "confidence": 0.80, "evidence": {"missed_sessions": 3, "near_miss_count": 2}, "suggestion": "description の trigger 精度を改善"}` が返される

#### Scenario: SPLIT judgment (skill_triage_split — カテゴリ分散ベース)
- **WHEN** `infra-deploy` スキルの should_trigger クエリを `skill_triggers.py` のトリガーワードでグループ化し、Jaccard 距離で階層クラスタリングした結果、`SPLIT_CATEGORY_THRESHOLD` (3) 以上のクラスタに分散している（CDK / Docker / Terraform）
- **THEN** `{"action": "SPLIT", "skill": "infra-deploy", "confidence": 0.75, "evidence": {"categories": ["cdk", "docker", "terraform"], "source": "triage"}}` が返される
- **NOTE** reorganize の `split_candidate`（行数ベース SPLIT_LINE_THRESHOLD=300）とは責務が異なる。triage SPLIT は意味的多義性、reorganize SPLIT は構造的肥大化を検出する（D7）

#### Scenario: MERGE judgment (クエリ重複ベース)
- **WHEN** `cdk-deploy` と `cdk-setup` の should_trigger クエリの Jaccard 類似度が `MERGE_OVERLAP_THRESHOLD` (0.40) 以上（例: 0.55）
- **THEN** `{"action": "MERGE", "skills": ["cdk-deploy", "cdk-setup"], "confidence": 0.70, "evidence": {"overlap_ratio": 0.55, "source": "triage"}}` が返される
- **NOTE** prune の MERGE（description テキスト類似度ベース）とは検出根拠が異なる。triage MERGE はユーザーが実際に混同するスキルペアを検出する（D8）。結果は prune の `merge_proposals` と統合し `source: "triage"` で区別する

#### Scenario: OK judgment
- **WHEN** スキルの missed_skill 検出が閾値未満で、near-miss が少なく、カテゴリ分散もない
- **THEN** `{"action": "OK", "skill": "commit", "confidence": 0.90}` が返される

### Requirement: Triage runs without LLM
triage_skill() は LLM を使用せず、テレメトリの集計とルールベース判定のみで動作する（MUST）。

#### Scenario: No API calls during triage
- **WHEN** triage_skill() が実行される
- **THEN** anthropic SDK の呼び出しが0回で完了する

### Requirement: Triage confidence scoring
各判定に confidence スコア（0.0-1.0）を付与する（SHALL）。confidence は D10 の計算式に基づく。

計算式:
```
base = {CREATE: 0.70, UPDATE: 0.65, SPLIT: 0.60, MERGE: 0.55}
session_bonus = min(MAX_SESSION_BONUS, (session_count - MISSED_SKILL_THRESHOLD) * SESSION_BONUS_RATE)
evidence_bonus = min(MAX_EVIDENCE_BONUS, near_miss_count * EVIDENCE_BONUS_RATE)  # UPDATE のみ
confidence = min(1.0, base + session_bonus + evidence_bonus)
```

定数: `BASE_CONFIDENCE`, `SESSION_BONUS_RATE = 0.05`, `EVIDENCE_BONUS_RATE = 0.03`, `MAX_SESSION_BONUS = 0.25`, `MAX_EVIDENCE_BONUS = 0.10`

#### Scenario: High confidence with strong evidence
- **WHEN** missed_skill が5セッション以上で検出され、スキルが存在しない
- **THEN** CREATE 判定: base(0.70) + session_bonus(min(0.25, (5-2)*0.05)=0.15) = 0.85

#### Scenario: Low confidence with weak evidence
- **WHEN** missed_skill が2セッション（閾値ギリギリ）で検出される
- **THEN** session_bonus = 0（session_count - MISSED_SKILL_THRESHOLD = 0）、base のみで confidence = 0.70 以下

#### Scenario: UPDATE with near-miss evidence bonus
- **WHEN** missed_skill が3セッションで検出され、near-miss クエリが3件ある
- **THEN** UPDATE 判定: base(0.65) + session_bonus(0.05) + evidence_bonus(min(0.10, 3*0.03)=0.09) = 0.79

### Requirement: Batch triage for all skills
`triage_all_skills()` は CLAUDE.md に登録された全スキルに対して triage を実行し、アクション別にグループ化した結果を返す（SHALL）。

#### Scenario: Mixed results across skills
- **WHEN** プロジェクトに10スキルが登録されている
- **THEN** `{"CREATE": [...], "UPDATE": [...], "SPLIT": [...], "MERGE": [...], "OK": [...]}` の形式で全スキルの判定結果が返される

#### Scenario: Empty skill list
- **WHEN** CLAUDE.md にスキルが登録されていない
- **THEN** 空の結果 `{"CREATE": [], "UPDATE": [], "SPLIT": [], "MERGE": [], "OK": []}` が返される

### Requirement: Issue schema integration
triage 結果は `issue_schema.py` の issue フォーマットに変換可能とする（SHALL）。CREATE/UPDATE/SPLIT/MERGE の各判定は対応する issue type にマッピングする。

#### Scenario: UPDATE to issue conversion
- **WHEN** triage が `{"action": "UPDATE", "skill": "aws-cdk-deploy", "confidence": 0.80}` を返す
- **THEN** `make_skill_triage_issue(action="UPDATE", skill="aws-cdk-deploy", confidence=0.80)` で issue_schema 準拠の issue に変換できる

### Requirement: Skill-creator integration suggestion
UPDATE 判定時に、skill-creator での description 最適化コマンド例と生成済み eval set パスを proposal に含める（SHALL）。

#### Scenario: UPDATE proposal with skill-creator command
- **WHEN** `aws-cdk-deploy` が UPDATE 判定される
- **THEN** proposal に以下が含まれる:
  - eval set パス: `~/.claude/rl-anything/eval-sets/aws-cdk-deploy.json`
  - コマンド例: `/skill-creator` で description 最適化を実行
  - 現在の推定 trigger 精度（テレメトリベース）

### Requirement: SPLIT category detection
SPLIT 判定のカテゴリ分散は、`skill_triggers.py` のトリガーワードによるグループ化 + Jaccard 距離の階層クラスタリングで検出する（SHALL）。`SPLIT_CATEGORY_THRESHOLD` (3) カテゴリ以上に分散している場合に SPLIT を提案する。issue type は `SKILL_TRIAGE_SPLIT`（reorganize の `SPLIT_CANDIDATE` とは別。D7）。

#### Scenario: Keyword clustering with Jaccard distance
- **WHEN** `infra-deploy` の should_trigger クエリが「CDK deploy Lambda」「Docker compose up」「Terraform apply」を含む
- **AND** 各クエリにマッチするトリガーワードセットの Jaccard 距離が `CLUSTER_DISTANCE_THRESHOLD` (0.70) 以上
- **THEN** 3クラスタ（cdk/docker/terraform）に分散と判定され、`SKILL_TRIAGE_SPLIT` issue が生成される

#### Scenario: Similar queries stay in same cluster
- **WHEN** should_trigger クエリ「CDK deploy Lambda」「CDK synth」のトリガーワードセットの Jaccard 距離が 0.30
- **THEN** 同一クラスタに属し、SPLIT の根拠カテゴリとしてカウントされない

### Requirement: MERGE overlap detection
MERGE 判定は、2スキルの should_trigger クエリの Jaccard 類似度が `MERGE_OVERLAP_THRESHOLD` (0.40) 以上の場合に提案する（SHALL）。

#### Scenario: High overlap between skills
- **WHEN** `cdk-deploy` と `cdk-setup` の should_trigger クエリの Jaccard 類似度が 0.55
- **THEN** MERGE が提案される

#### Scenario: Low overlap
- **WHEN** 2スキルの Jaccard 類似度が 0.20
- **THEN** MERGE は提案されない
