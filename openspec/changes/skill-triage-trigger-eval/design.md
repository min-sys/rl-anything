## Context

rl-anything の evolve パイプラインは Diagnose → Compile → Housekeeping の3ステージで構成される。Diagnose では discover（パターン検出）、audit（問題検出）、reorganize（split検出）を実行するが、スキルの **description trigger 精度** を計測する手段がない。

skill-creator v2 は `run_eval.py`（trigger 精度計測）と `improve_description.py`（description 最適化）を提供している。rl-anything はテレメトリデータ（sessions.jsonl / usage.jsonl）を保持しており、これを eval set に変換する独自価値を持つ。

現状の判断能力:
- discover `detect_missed_skills()`: テキストマッチベースの missed skill 検出（false positive 多い）
- skill_evolve `classify_suitability()`: 5軸適性評価（description 品質は未計測）
- remediation: issue 分類 → fix dispatch（description 関連の issue type なし）

## Goals / Non-Goals

**Goals:**
- テレメトリの実プロンプトから skill-creator 互換の evals.json を自動生成する
- trigger eval 結果 + テレメトリを統合し、CREATE / UPDATE / SPLIT / MERGE / OK の5択 triage 判定を行う
- evolve Diagnose ステージに triage を統合し、description 品質問題を remediation パイプラインに流す

**Non-Goals:**
- skill-creator の `run_eval.py` / `improve_description.py` を rl-anything 内に再実装しない（フォーマット互換のみ）
- description の自動書き換えは行わない（skill-creator に委譲し、パスを提案するのみ）
- trigger eval の実機テスト（`claude -p` 実行）は rl-anything 側では行わない（コスト大。eval set 生成までが責務）

## Decisions

### D1: eval set 生成のデータソース

**決定**: sessions.jsonl の `user_prompts` + usage.jsonl のスキル使用実績を組み合わせる

- should_trigger: スキルが実際に使われたセッションの user_prompts から抽出
- should_not_trigger: 同じトリガーワードを含むが異なるスキルが使われたセッション（near-miss）+ スキル未使用セッション

**代替案1**: errors.jsonl も含める → 却下。エラーセッションは trigger の正否とは無関係

**代替案2**: LLM によるシンセティッククエリ生成 → 却下。LLM 不使用方針（D3）と矛盾する。テレメトリからの実データ（near-miss + unrelated）を優先し、信頼性の高い eval set を構築する

### D2: evals.json フォーマット

**決定**: skill-creator の evals.json フォーマットに完全準拠する

```json
[
  {"query": "...", "should_trigger": true},
  {"query": "...", "should_trigger": false}
]
```

skill-creator の `run_eval.py --eval-set` でそのまま使えるようにする。

**代替案**: rl-anything 独自フォーマット → 却下。互換性を最優先

### D3: triage 判定ロジック

**決定**: 以下の判定マトリクスを使用する

| 条件 | 判定 |
|------|------|
| missed_skill 高 + 既存スキルなし | CREATE |
| missed_skill 高 + 既存スキルあり + near-miss 多 | UPDATE（description 精度問題） |
| 1スキルに should_trigger 多カテゴリ集中 | SPLIT（description が広すぎ） |
| 複数スキルに should_trigger 重複 | MERGE（description が重複） |
| 上記いずれにも該当しない | OK |

判定は `skill_triage.py` の `triage_skill()` 関数で行い、結果を `issue_schema.py` の issue として出力する。

**代替案1**: LLM で判定 → 却下。テレメトリベースの定量判定で十分。LLM コスト不要

**代替案2**: 2段階判定（needs_attention → 人間分類） → 却下。evolve は自動パイプラインであり、人間介入を前提にすると remediation フローに乗らない。5択判定は confidence 付きで提案するため、低 confidence は実質的に人間判断を委ねている

### D4: evolve 統合ポイント

**決定**: Diagnose ステージの discover 実行後に triage を実行する

```
Diagnose:
  1. discover（パターン検出 + missed skill 検出）
  2. triage（eval set 生成 + CREATE/UPDATE/SPLIT/MERGE/OK 判定）  ← NEW
  3. audit（問題検出 + 全レイヤー診断）
  4. reorganize（split 検出）
```

triage の出力 issue は `collect_issues()` に統合され、Compile ステージの remediation に流れる。

### D5: eval set の最小データ要件

**決定**: should_trigger / should_not_trigger それぞれ最低3件。データ不足時は triage をスキップし warning を出す。

定数: `MIN_EVAL_QUERIES = 3`, `TARGET_EVAL_QUERIES = 10`

### D6: skill-creator 連携の提案形式

**決定**: UPDATE 判定時に以下の情報を remediation proposal に含める

- 生成した evals.json のパス
- `/skill-creator` でのコマンド例
- 現在の trigger 精度推定値（テレメトリベース）

実行は行わない。ユーザーが `/skill-creator` を手動で実行する。

### D7: SPLIT 検出の reorganize との責務分離

**決定**: triage の SPLIT は `skill_triage_split`（カテゴリ分散ベース）として、reorganize の `split_candidate`（行数ベース）と明確に区別する

- **reorganize**: 構造的肥大化（SPLIT_LINE_THRESHOLD=300 超過）による物理的分割の提案
- **triage**: 意味的多義性（1スキルの should_trigger クエリが複数カテゴリに分散）による論理的分割の提案
- `issue_schema.py` に `SKILL_TRIAGE_SPLIT` 定数を追加（既存 `SPLIT_CANDIDATE` とは別）

### D8: MERGE 検出の prune との責務分離

**決定**: triage MERGE と prune MERGE を検出根拠で区別し、出力を統合する

- **triage MERGE**: クエリ重複ベース（ユーザーが実際に混同するスキルペア。should_trigger クエリの Jaccard 類似度）
- **prune MERGE**: description 類似度ベース（テキスト的に似たスキルペア。`similarity.py` の `jaccard_coefficient()`）
- triage MERGE 結果は prune の `merge_proposals` と統合し、`source: "triage"` フィールドで区別する
- `similarity.py` の `jaccard_coefficient()` を再利用（新規実装不要）

### D9: SPLIT クラスタリング手法

**決定**: should_trigger クエリを `skill_triggers.py` のトリガーワードでグループ化し、Jaccard 距離で階層クラスタリングする

- 各クエリにマッチしたトリガーワードセットを取得
- トリガーワードセット間の Jaccard 距離で階層クラスタリング（scipy 不要、単純なアグロメレーション）
- LLM 不使用（D3「LLMコスト不要」方針と一貫）
- 定数: `CLUSTER_DISTANCE_THRESHOLD = 0.70`
- `SPLIT_CATEGORY_THRESHOLD` (3) カテゴリ以上に分散している場合に SPLIT を提案

### D10: confidence 計算式

**決定**: アクション種別ごとの base confidence に、エビデンス量に応じたボーナスを加算する

```
base = {CREATE: 0.70, UPDATE: 0.65, SPLIT: 0.60, MERGE: 0.55}
session_bonus = min(0.25, (session_count - MISSED_SKILL_THRESHOLD) * 0.05)
evidence_bonus = min(0.10, near_miss_count * 0.03)  # UPDATE のみ
confidence = min(1.0, base + session_bonus + evidence_bonus)
```

定数: `BASE_CONFIDENCE` (dict), `SESSION_BONUS_RATE = 0.05`, `EVIDENCE_BONUS_RATE = 0.03`, `MAX_SESSION_BONUS = 0.25`, `MAX_EVIDENCE_BONUS = 0.10`

## Risks / Trade-offs

- **[テレメトリ不足]** → sessions.jsonl のデータが少ないと eval set が偏る。MIN_EVAL_QUERIES (3件) を下回る場合は triage をスキップし graceful degradation
- **[テキストマッチの限界]** → should_trigger/should_not_trigger の自動判定はテキストマッチベース。精度は skill-creator の実機テストに劣る。eval set は「素材」として生成し、最終判断は skill-creator に委ねる
- **[MERGE 判定の false positive]** → description の文言類似だけではなく、usage.jsonl の実使用パターンも加味して判定する
- **[evolve 実行時間増加]** → triage は LLM 不使用（テレメトリ集計のみ）のため、数秒以内で完了する見込み
