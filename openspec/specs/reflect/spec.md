## ADDED Requirements

### Requirement: Reflect skill loads pending corrections
`reflect.py` は corrections.jsonl から `reflect_status: "pending"` のレコードを抽出し、分析結果を JSON で出力する（MUST）。

#### Scenario: Pending corrections exist
- **WHEN** corrections.jsonl に pending レコードが 3件ある
- **THEN** reflect.py が 3件の分析結果（ルーティング提案・重複チェック結果）を JSON で出力する

#### Scenario: No pending corrections
- **WHEN** corrections.jsonl に pending レコードがない
- **THEN** `{"status": "empty", "message": "未処理の修正はありません"}` を出力する

### Requirement: Project-aware filtering
corrections の project パスと現在のプロジェクトを比較し、3ケースに分類する（MUST）: same-project, global-looking, project-specific-other。

#### Scenario: Same project correction
- **WHEN** correction の project が現在のプロジェクトと一致する
- **THEN** 通常表示し、project/global/both のスコープ選択を提供する

#### Scenario: Global-looking correction from other project
- **WHEN** correction が別プロジェクトで記録され、"always"/"never" やモデル名を含む
- **THEN** "FROM DIFFERENT PROJECT" 警告とともに global スコープのみを提案する

#### Scenario: Project-specific correction from other project
- **WHEN** correction が別プロジェクトで記録され、DB名やファイルパスを含む
- **THEN** 自動スキップし "Skipping project-specific learning from [project]" と表示する

#### Scenario: Correction with null project_path
- **WHEN** correction の project_path が null（CLAUDE_PROJECT_DIR 未設定環境で記録）
- **THEN** global-looking 扱いとし、「プロジェクト情報なし: global として扱います」と表示する

### Requirement: 8-tier memory hierarchy routing
corrections は8層メモリ階層の適切な書込先にルーティングされる（MUST）。CLAUDE.local.md（個人用）と auto-memory（低信頼度ステージング）を含む。ルーティング判定時にプロジェクト固有シグナル検出を実施し、`always/never/prefer` キーワードによる global ルーティングよりも優先する（MUST）。**`last_skill` コンテキストが存在する場合、always/never 層の後・frontmatter paths 層の前（位置6）に挿入された last-skill 層でスキルの references/ にルーティングする（MUST）。保護スキルの場合はローカル代替先にリダイレクトする。**

#### Scenario: Guardrail routed to rules
- **WHEN** guardrail タイプの correction をルーティングする
- **THEN** `.claude/rules/guardrails.md` が提案される

#### Scenario: Last skill context routes at position 6
- **WHEN** correction の `last_skill` が "atlas-browser" であり、always/never キーワードも含まない
- **THEN** 位置6の last-skill 層で評価され、`.claude/skills/atlas-browser/references/pitfalls.md` が提案される

#### Scenario: Last skill is protected — redirect to local
- **WHEN** correction の `last_skill` が "openspec-verify-change"（plugin 由来）
- **THEN** プロジェクト側の references/ が代替先として提案される

#### Scenario: Model preference routed to global
- **WHEN** "claude-4" 等のモデル名を含む correction をルーティングする
- **THEN** `~/.claude/CLAUDE.md` または model-preferences rule が提案される

#### Scenario: Project-specific skill in correction with always keyword
- **WHEN** correction テキストが「/channel-routing は always 使うべき」を含む
- **AND** `channel-routing` が現在のプロジェクトの CLAUDE.md に記載されたスキル
- **THEN** プロジェクト固有シグナルにより `.claude/rules/` が提案される（global ではなく）

#### Scenario: Generic always keyword without project signal
- **WHEN** correction テキストが「タスクが変わったら always スキルを確認する」を含む
- **AND** プロジェクト固有シグナルが検出されない
- **THEN** 従来通り `~/.claude/CLAUDE.md`（global）が提案される

#### Scenario: Path-scoped rule match
- **WHEN** correction に "src/api" パスの言及があり、`paths: src/api/` を持つ rule がある
- **THEN** その rule ファイルが提案される

#### Scenario: Low confidence routed to auto-memory
- **WHEN** confidence 0.65 の correction をルーティングする
- **THEN** auto-memory のトピック別ファイル（例: `workflow.md`）に仮置きが提案される

#### Scenario: Machine-specific routed to CLAUDE.local.md
- **WHEN** correction にローカルパスや個人設定が含まれ、ユーザーが CLAUDE.local.md を選択する
- **THEN** `./CLAUDE.local.md` に書き込まれる

### Requirement: Duplicate detection across memory tiers
reflect.py は全メモリ層のエントリと corrections を照合し、既存の類似エントリを検出する（MUST）。

#### Scenario: Duplicate found in CLAUDE.md
- **WHEN** "Use bun not npm" が corrections にあり、CLAUDE.md に "Use bun for package management" がある
- **THEN** 重複として検出し、merge/replace/add-anyway/skip の選択肢を提供する

### Requirement: Semantic validation (default enabled, batch)
セマンティック検証はデフォルト有効。全 pending corrections を1回の `claude -p` 呼び出しでバッチ検証し、偽陽性を除去する（MUST）。`--skip-semantic` で無効化可能。フォールバック時は `is_learning=True` でパススルーし、全件除外してはならない（MUST NOT）。

#### Scenario: Semantic validation filters false positive
- **WHEN** "いや、今日は天気がいい" が regex で検出され、semantic 検証を実行する
- **THEN** `is_learning: false` と判定されフィルタされる

#### Scenario: Batch validation of multiple corrections
- **WHEN** pending corrections が 5件あり、semantic 検証を実行する
- **THEN** 5件を1回の `claude -p` 呼び出しでまとめて検証し、各 correction に `is_learning` 判定を返す

#### Scenario: Semantic validation skipped
- **WHEN** `/reflect --skip-semantic` を実行する
- **THEN** LLM 検証をスキップし、regex 検出結果のみで処理する

#### Scenario: Batch size exceeds limit
- **WHEN** pending corrections が 30件あり、semantic 検証を実行する
- **THEN** 20件ずつ2バッチに分割して `claude -p` を呼び出す

#### Scenario: Semantic validation JSON parse failure
- **WHEN** `claude -p` のレスポンスが不正な JSON（パース失敗、件数不一致等）である
- **THEN** 全件を `is_learning=True` としてパススルーし（MUST）、stderr に警告を出力する。全件を `is_learning=False` として除外してはならない（MUST NOT）

#### Scenario: Semantic validation unavailable
- **WHEN** `claude -p` の呼び出しがタイムアウトする
- **THEN** 全件を `is_learning=True` としてパススルーし（MUST）、警告を表示する

### Requirement: Interactive review via SKILL.md
SKILL.md の指示により Claude が corrections を対話的にレビューする（MUST）。AskUserQuestion で approve/edit/skip を選択させる。

#### Scenario: User approves a correction
- **WHEN** ユーザーが correction を "Apply" する
- **THEN** 提案先ファイルに Edit ツールで書込み、corrections.jsonl の reflect_status を "applied" に更新する

#### Scenario: User skips a correction
- **WHEN** ユーザーが correction を "Skip" する
- **THEN** corrections.jsonl の reflect_status を "skipped" に更新し、ファイル変更なし

#### Scenario: User skips remaining corrections
- **WHEN** 対話レビュー中にユーザーが "Skip remaining" を選択する
- **THEN** 未レビューの全 corrections の reflect_status を "skipped" に更新し、レビューを終了する

### Requirement: Reflect status tracking
corrections.jsonl の `reflect_status` フィールドで処理状態を追跡する（MUST）。`/reflect` は pending のみを対象とする。

#### Scenario: Already processed correction
- **WHEN** reflect_status が "applied" の correction がある
- **THEN** `/reflect` の対象に含まれない

### Requirement: Dry-run mode
`--dry-run` フラグで変更をプレビューのみ行い、ファイル書込と reflect_status 更新を行わない（MUST）。

#### Scenario: Dry-run preview
- **WHEN** `/reflect --dry-run` を実行する
- **THEN** 分析結果とルーティング提案を表示するが、CLAUDE.md への書込と reflect_status の更新は行わない

### Requirement: View pending corrections
`--view` フラグで pending corrections の一覧を表示して終了する（MUST）。

#### Scenario: View pending list
- **WHEN** `/reflect --view` を実行し、pending が 3件ある
- **THEN** 各 correction の confidence・タイプ・経過日数を一覧表示し、他の処理は行わない

### Requirement: Skip all pending corrections
`--skip-all` フラグで全 pending corrections を一括スキップする（MUST）。

#### Scenario: Skip all corrections
- **WHEN** `/reflect --skip-all` を実行し、pending が 5件ある
- **THEN** 確認後、5件の reflect_status を全て "skipped" に更新する

### Requirement: Apply-all mode
`--apply-all` フラグで高信頼度の corrections を確認なしで一括適用する（SHALL）。

#### Scenario: Apply all high confidence corrections
- **WHEN** `/reflect --apply-all` を実行し、confidence >= 0.85 の correction が 3件、confidence < 0.85 の correction が 2件ある
- **THEN** 高信頼度 3件を確認なしで apply し、低信頼度 2件は対話レビュー（approve/edit/skip）に進む

#### Scenario: Custom confidence threshold
- **WHEN** `/reflect --apply-all --min-confidence 0.70` を実行する
- **THEN** confidence >= 0.70 の corrections を一括適用する

### Requirement: Auto-memory promotion
auto-memory に仮置きされた低信頼度 corrections を、条件を満たした場合に昇格候補として表示する（SHALL）。

#### Scenario: Promotion by recurrence
- **WHEN** auto-memory に仮置きされた correction と同じ correction_type が 2回以上再出現している
- **THEN** `/reflect` 実行時に昇格候補として表示し、正式な CLAUDE.md/rules への書込を提案する

#### Scenario: Promotion by aging
- **WHEN** auto-memory のエントリが 14日以上滞留し、矛盾する correction が記録されていない
- **THEN** `/reflect` 実行時に昇格候補として表示する

### Requirement: Evolve pipeline Reflect Step
evolve パイプラインの Fitness Evolution の後、Report の前に Reflect Step を配置する（MUST）。

#### Scenario: Many pending corrections during evolve
- **WHEN** evolve 実行時に pending corrections が 5件以上ある
- **THEN** 「5件の未処理修正があります。/reflect を実行しますか？」と AskUserQuestion で表示する

#### Scenario: Few pending corrections during evolve (within cooldown)
- **WHEN** evolve 実行時に pending corrections が 3件あり、前回 /reflect 実行から 5日しか経っていない
- **THEN** Report に「未処理修正 3件あり」と表示するのみで、/reflect の実行提案はしない

#### Scenario: Few pending corrections during evolve (cooldown expired)
- **WHEN** evolve 実行時に pending corrections が 3件あり、前回 /reflect 実行から 10日経過している
- **THEN** 「3件の未処理修正があります。/reflect を実行しますか？」と AskUserQuestion で表示する

#### Scenario: No pending corrections during evolve
- **WHEN** evolve 実行時に pending corrections が 0件
- **THEN** Reflect Step をスキップし Report に進む

### Requirement: Corrections cleanup via prune
prune.py の実行時に corrections.jsonl の `applied`/`skipped` レコードのうち `decay_days` を超過したものを削除する（MUST）。`pending` レコードは削除しない。

#### Scenario: Cleanup expired applied corrections
- **WHEN** prune 実行時に `reflect_status: "applied"`、`decay_days: 90` で 100日経過のレコードがある
- **THEN** そのレコードを corrections.jsonl から削除する

#### Scenario: Pending corrections preserved
- **WHEN** prune 実行時に `reflect_status: "pending"` で `decay_days` を超過したレコードがある
- **THEN** そのレコードは削除せず保持する
