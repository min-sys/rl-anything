## 1. PreToolUse hook（ワークフロー文脈記録）

- [x] 1.1 `hooks/workflow_context.py` を作成（stdin から PreToolUse イベントを読み取り、Skill 呼び出し時に `$TMPDIR/rl-anything-workflow-{session_id}.json` を書き出す）
- [x] 1.2 `workflow_id` 生成ロジック（`wf-{uuid4先頭8文字}` 形式）
- [x] 1.3 `hooks.json` に PreToolUse エントリを追加（matcher: `tool_name: "Skill"`, command: `workflow_context.py`, timeout: 5000）

## 2. 文脈ファイル読み取りの共通化

- [x] 2.1 `hooks/common.py` に `read_workflow_context(session_id)` 関数を追加（文脈ファイル読み取り → parent_skill/workflow_id 取得 → 24h expire チェック → エラー時 `{"parent_skill": null, "workflow_id": null}` 返却）

## 3. PostToolUse hook 修正（parent_skill 付与）

- [x] 3.1 `hooks/observe.py` で `common.read_workflow_context(session_id)` を呼び出し、`parent_skill`, `workflow_id` を usage レコードに付与
- [x] 3.2 文脈ファイルが存在しない場合は `parent_skill: null`, `workflow_id: null` を明示設定（`read_workflow_context` のデフォルト動作）
- [x] 3.3 文脈ファイルの24時間 expire チェック（`read_workflow_context` に内包）
- [x] 3.4 文脈ファイルの読み取り失敗時のサイレント処理（`read_workflow_context` に内包。セッションをブロックしない）

## 4. SubagentStop hook 修正（parent_skill 付与）

- [x] 4.1 `hooks/subagent_observe.py` で `common.read_workflow_context(session_id)` を呼び出し、`parent_skill`, `workflow_id` を subagents.jsonl レコードに付与
- [x] 4.2 subagents.jsonl レコードに `parent_skill`, `workflow_id` を付与（PostToolUse と同一パターン）

## 5. Stop hook 修正（ワークフローシーケンス記録 + クリーンアップ）

- [x] 5.1 `hooks/session_summary.py` にワークフローシーケンス組み立てロジックを追加（usage.jsonl から同一 `workflow_id` のレコードを収集し `workflows.jsonl` に書き出す）
- [x] 5.2 文脈ファイルの削除処理を追加（存在しない場合はサイレントスキップ）

## 6. Discover 改修（contextualized / ad-hoc 分類）

- [x] 6.1 `skills/discover/scripts/discover.py` の `detect_behavior_patterns` を修正（`parent_skill` の有無で contextualized / ad-hoc / unknown を分類）
- [x] 6.2 ad-hoc パターンのみを新規スキル候補として提案するように変更
- [x] 6.3 backfill データ（`source: "backfill"`, `parent_skill: null`）を unknown として除外

## 7. Prune 改修（parent_skill 経由カウント）

- [x] 7.1 `skills/prune/scripts/prune.py` の使用回数カウントに `parent_skill` 参照回数を加算（usage.jsonl の `parent_skill` フィールドを参照。subagents.jsonl は対象外）
- [x] 7.2 parent_skill 経由で使用されているスキルが淘汰候補にならないことを確認

## 8. テスト

- [x] 8.1 `hooks/tests/test_hooks.py` に PreToolUse handler（workflow_context.py）のテスト追加
- [x] 8.2 `common.read_workflow_context()` のユニットテスト追加（文脈あり、なし、破損、expire）
- [x] 8.3 observe.py の parent_skill 読み取りテスト追加
- [x] 8.4 subagent_observe.py の parent_skill 付与テスト追加
- [x] 8.5 session_summary.py のワークフローシーケンス組み立てテスト追加
- [x] 8.6 discover.py の contextualized/ad-hoc 分類テスト追加
- [x] 8.7 prune.py の parent_skill 経由カウントテスト追加
- [x] 8.8 既存テスト全パス確認

## 9. バージョンアップ

- [x] 9.1 plugin.json を 0.3.0 にバンプ（observe 層のデータモデル拡張のためマイナーバージョンアップ）
- [x] 9.2 CHANGELOG.md に 0.3.0 エントリ追加

## 10. 動作確認（E2E）

### 10a. データ記録の確認

- [x] 10.1 `/opsx:refine` 等のスキルを実行し、内部で Agent が呼ばれた際に usage.jsonl に `parent_skill`, `workflow_id` が記録されることを確認
- [x] 10.2 手動で Agent:Explore を呼び、`parent_skill: null`, `workflow_id: null` が記録されることを確認
- [x] 10.3 セッション終了後に workflows.jsonl にシーケンスレコードが書き出されることを確認（`steps`, `step_count`, `intent_category` の内容が妥当か目視）
- [x] 10.4 subagents.jsonl にも `parent_skill`, `workflow_id` が付与されていることを確認
- [x] 10.5 文脈ファイル（`$TMPDIR/rl-anything-workflow-*.json`）がセッション終了後に削除されていることを確認

### 10b. Discover / Prune 精度の確認

- [x] 10.6 `discover.py` を実行し、contextualized（スキル内）レコードがスキル候補から除外されていることを確認
- [x] 10.7 backfill データ（`source: "backfill"`）が unknown として除外されていることを確認
- [x] 10.8 `prune.py` を実行し、`parent_skill` 経由で使用されているスキルが淘汰候補から外れることを確認
- [x] 10.9 直接呼び出し0回 + parent_skill 参照0回のスキルが淘汰候補として報告されることを確認

## 11. データ蓄積・分析（Phase C 設計入力の収集）

> 1-2週間の通常利用でデータを蓄積してから着手する。
> 分析結果は Phase C proposal の `## Context` セクションに定量データとして記載する。

### 11a. ワークフロー構造の一貫性分析

- [ ] 11.1 同一 `skill_name` の workflows.jsonl レコードを比較し、ステップ構成の一貫性を評価する（例: `opsx:refine` は毎回「Explore → Explore → general-purpose」なのか、ばらつくのか）
- [ ] 11.2 一貫性が高いスキル / 低いスキルのリストを作成（→ Phase C: 構造化表現の要否判断に使用）

### 11b. ステップバリエーション分析

- [ ] 11.3 同一スキルの workflow シーケンスで、ステップの順序・種類・回数にどんなバリエーションがあるか集計（→ Phase C: mutation 操作セットの設計に使用）
- [ ] 11.4 「途中でユーザーが手動介入したワークフロー」と「一発で完了したワークフロー」のステップ構造の差分を分析（→ Phase C: fitness 測定の特徴量候補）

### 11c. Discover / Prune 精度の定量評価

- [ ] 11.5 トレーシング導入前後で Discover の提案内容を比較（的外れな提案が減ったか定量的に確認）
- [ ] 11.6 トレーシング導入前後で Prune の誤検出を比較（`opsx:refine` 等の false positive が解消したか確認）

## 12. Phase C proposal 作成

- [ ] 12.1 11章の分析結果を踏まえ、Phase C（ワークフロー構造進化）の change を `opsx:propose` で作成する。proposal に含めるべき定量データ:
  - workflows.jsonl のレコード数・スキル別内訳
  - ステップ構成の一貫性スコア（11.1-11.2 の結果）
  - mutation 候補の具体例（11.3-11.4 の結果）
  - Discover/Prune 精度改善の before/after（11.5-11.6 の結果）

Phase C proposal に含めるべき設計入力（アイデア記録）:
  - **初期設定スキル** (`/rl-anything:setup`): 対話形式で per-project / global の rules, skills, memory を自動生成
  - **Observe → Reflect → Adapt → Repeat** ループの実装（2026年の self-improving agent ベストプラクティス）
  - example-based bootstrap パターン（Turborepo の `--example` 方式）

## 13. Backfill ワークフロー構造抽出

### 13a. classify_prompt 共通化

- [x] 13.1 `hooks/common.py` に `PROMPT_CATEGORIES` と `classify_prompt()` を追加
- [x] 13.2 `hooks/session_summary.py` の `_PROMPT_CATEGORIES`/`_classify_prompt` を削除 → `common.classify_prompt()` に置換
- [x] 13.3 `skills/discover/scripts/discover.py` の `_PROMPT_CATEGORIES` を削除 → `common.classify_prompt()` を利用

### 13b. parse_transcript() 拡張

- [x] 13.4 `ParseResult` dataclass を追加（usage_records, workflow_records, errors）
- [x] 13.5 ワークフロー境界判定ロジック実装（Skill → Agent シーケンス検出）
- [x] 13.6 Agent レコードに parent_skill/workflow_id を付与（Skill ワークフロー内の場合）
- [x] 13.7 workflows.jsonl レコード生成（session_summary.py と同一スキーマ）

### 13c. backfill() 拡張

- [x] 13.8 `remove_backfill_workflows()` 追加（--force 用）
- [x] 13.9 backfill() ループ内で workflow_records を workflows.jsonl に追記
- [x] 13.10 サマリに `workflows` カウント追加

### 13d. テスト

- [x] 13.11 classify_prompt テスト追加（hooks/tests/test_hooks.py）
- [x] 13.12 ワークフロー追跡テスト追加（test_backfill.py - TestWorkflowTracking）
- [x] 13.13 既存 parse_transcript テストを ParseResult 対応に修正
- [x] 13.14 backfill 統合テスト（workflows.jsonl 出力、--force ワークフロー削除）
- [x] 13.15 全テスト通過確認

### 13e. ドキュメント

- [x] 13.16 SKILL.md に workflows.jsonl 生成の説明追加
- [x] 13.17 CHANGELOG.md にエントリ追加

## 14. 分析スクリプト

- [x] 14.1 `skills/backfill/scripts/analyze.py` 作成（一貫性・バリエーション・介入・Discover/Prune 分析）
- [x] 14.2 `skills/backfill/scripts/tests/test_analyze.py` 作成（13テスト）
- [ ] 14.3 分析実行 → 結果を Phase C proposal の `## Context` に反映
