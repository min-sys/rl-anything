## ADDED Requirements

### Requirement: Skill trigger word extraction
discover は CLAUDE.md の Skills セクションからスキル名とトリガーワードを抽出する（MUST）。トリガーワードが未記載のスキルはスキル名自体をフォールバックトリガーとして使用する（SHALL）。

#### Scenario: Trigger words defined in CLAUDE.md
- **WHEN** CLAUDE.md に `- /channel-routing: ... トリガー: channel routing, チャンネルマッピング, bot追加` と記載されている
- **THEN** `{"skill": "channel-routing", "triggers": ["channel routing", "チャンネルマッピング", "bot追加"]}` が抽出される

#### Scenario: Trigger word format variations
- **WHEN** CLAUDE.md に以下のいずれかの形式でトリガーワードが記載されている:
  - `トリガー: word1, word2`
  - `トリガーワード: word1, word2`
  - `Trigger: word1, word2`
  - `triggers: word1, word2`
- **THEN** いずれの形式でもトリガーワードが正しく抽出される

#### Scenario: No trigger words defined
- **WHEN** CLAUDE.md に `/my-skill: 説明文` とだけ記載されトリガーワードがない
- **THEN** `{"skill": "my-skill", "triggers": ["my-skill"]}` がフォールバックとして生成される

#### Scenario: CLAUDE.md not found
- **WHEN** プロジェクトルートに CLAUDE.md が存在しない
- **THEN** missed skill 検出をスキップし、レポートに `"No CLAUDE.md found, skipping missed skill detection"` と表示する

### Requirement: Missed skill detection from session data
discover は sessions.jsonl の user_prompts とスキルのトリガーワードを突合し、usage.jsonl のスキル使用実績と照合して「トリガーワードにマッチしたがスキルが使われなかった」セッションを検出する（MUST）。`--project-dir` 指定時は sessions.jsonl / usage.jsonl の両方に同じ project フィルタを適用する（MUST）。

#### Scenario: Trigger matched but skill not used
- **WHEN** sessions.jsonl の user_prompts に「Slackのチャンネル設定をしたい」があり、usage.jsonl で同 session_id に `/channel-routing` の使用実績がない
- **AND** `channel-routing` のトリガーワード「チャンネル」が user_prompts に含まれる
- **THEN** missed skill opportunity として `{"skill": "channel-routing", "trigger_matched": "チャンネル", "session": "..."}` が検出される

#### Scenario: Trigger matched and skill was used
- **WHEN** sessions.jsonl の user_prompts に「チャンネル設定」があり、usage.jsonl で同 session_id に `/channel-routing` の使用実績がある
- **THEN** missed skill opportunity として検出されない

#### Scenario: Skill name normalization
- **WHEN** usage.jsonl に `/channel-routing` や `rl-anything:channel-routing` としてスキル使用が記録されている
- **THEN** 正規化後 `channel-routing` として突合され、missed として誤検出されない

#### Scenario: Frequency threshold filtering
- **WHEN** `/deploy-check` のトリガーワードが 1セッションのみでマッチした
- **AND** missed skill 検出の閾値が 2セッション以上（`MISSED_SKILL_THRESHOLD`）
- **THEN** レポートに含まれない（ノイズ除去）

#### Scenario: sessions.jsonl not found
- **WHEN** sessions.jsonl が存在しない（backfill 未実行）
- **THEN** missed skill 検出をスキップし、レポートに `"No sessions.jsonl found (run backfill first), skipping missed skill detection"` と表示する

### Requirement: Missed skill report section
discover レポートに「Missed Skill Opportunities」セクションを出力する（MUST）。スキル名、マッチしたトリガーワード、該当セッション数を表示する。

#### Scenario: Multiple missed skills detected
- **WHEN** `channel-routing` が 3セッション、`deploy-check` が 2セッションで missed と検出された
- **THEN** レポートに以下が表示される:
  ```
  === Missed Skill Opportunities ===
    /channel-routing (3 sessions): triggers ["チャンネル", "bot追加"]
    /deploy-check (2 sessions): triggers ["デプロイ確認"]
  ```

#### Scenario: No missed skills detected
- **WHEN** missed skill opportunity が 0件
- **THEN** 「Missed Skill Opportunities」セクションは表示しない
