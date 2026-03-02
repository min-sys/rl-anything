# Observe 拡張: ワークフロートレーシング

> ステータス: 要件定義（Phase B: 実装対象）
> 前提: Phase C（ワークフロー構造進化）の設計判断に必要なデータを収集する

## 背景

### 現状の問題

observe hooks は「どのツールを呼んだか」を記録するが、「どのワークフローの一部として呼んだか」が欠落している。

```
現在の記録:
  {skill_name: "Agent:Explore", session_id: "xxx", timestamp: "..."}
  {skill_name: "Agent:Explore", session_id: "xxx", timestamp: "..."}
  {skill_name: "Agent:Explore", session_id: "xxx", timestamp: "..."}

  → 3回 Explore を呼んだことはわかるが、
    「opsx:refine の中で呼ばれた」のか「手動で呼んだ」のか区別できない
```

### 実データで確認した影響

rl-anything 自身のバックフィルデータ（8セッション、43レコード）を分析した結果:

| 問題 | 具体例 |
|------|--------|
| Discover の的外れな提案 | `Agent:Explore 22回 → skill_candidate` と提案するが、うち13回は opsx:refine 経由で呼ばれた spec-review。新スキルは不要 |
| Prune の誤検出 | `openspec-refine` が使用回数0で淘汰候補になるが、実際は plan mode 経由で頻繁に使用されている |
| Discover のサブカテゴリ分析の限界 | keyword ベースで prompt を分類しても、`contextualized`（スキル内）vs `ad-hoc`（手動）が区別できない |

### 目的

1. ツール呼び出しに「どのスキルの中で呼ばれたか」を付与し、Discover/Prune の精度を向上させる
2. Phase C（ワークフロー構造進化）に必要なワークフローシーケンスデータを蓄積する

---

## 要件

### R1: PreToolUse hook でワークフロー文脈を記録する（MUST）

Skill ツールが呼ばれたとき、`PreToolUse` hook でセッション内のワークフロー文脈ファイルを書き出す。

```
トリガー: PreToolUse (matcher: tool_name: "Skill")
書き出し先: $TMPDIR/rl-anything-workflow-{session_id}.json
内容:
  {
    "skill_name": "opsx:refine",
    "session_id": "sess-001",
    "workflow_id": "wf-{uuid4_short}",
    "started_at": "2026-03-03T10:00:00Z"
  }
```

上書き方式。同一セッション内で別のスキルが呼ばれたら文脈を更新する。

### R2: PostToolUse hook で parent_skill を付与する（MUST）

Agent ツール呼び出しの usage レコードに、ワークフロー文脈ファイルから `parent_skill` と `workflow_id` を付与する。

```
文脈ファイルが存在する場合:
  {
    "skill_name": "Agent:Explore",
    "parent_skill": "opsx:refine",      ← 追加
    "workflow_id": "wf-abc123",          ← 追加
    "session_id": "sess-001",
    "timestamp": "...",
    ...
  }

文脈ファイルが存在しない場合（手動呼び出し）:
  {
    "skill_name": "Agent:Explore",
    "parent_skill": null,                ← 明示的に null
    "workflow_id": null,
    "session_id": "sess-001",
    "timestamp": "...",
    ...
  }
```

### R3: SubagentStop hook にも parent_skill を付与する（MUST）

subagents.jsonl のレコードにも同様に `parent_skill` と `workflow_id` を付与する。

### R4: ワークフローシーケンスを workflows.jsonl に記録する（MUST）

セッション終了時（Stop hook）にワークフロー単位のシーケンスレコードを書き出す。

```json
{
  "workflow_id": "wf-abc123",
  "skill_name": "opsx:refine",
  "session_id": "sess-001",
  "started_at": "2026-03-03T10:00:00Z",
  "ended_at": "2026-03-03T10:05:00Z",
  "steps": [
    {"tool": "Agent:Explore", "intent_category": "spec-review", "timestamp": "..."},
    {"tool": "Agent:Explore", "intent_category": "spec-review", "timestamp": "..."},
    {"tool": "Agent:general-purpose", "intent_category": "implementation", "timestamp": "..."}
  ],
  "step_count": 3,
  "source": "trace"
}
```

このデータが Phase C（ワークフロー構造進化）の入力になる。

### R5: Discover でcontextualized / ad-hoc を分類する（MUST）

`parent_skill` の有無で usage レコードを2層に分類し、提案の精度を上げる。

```
contextualized（parent_skill あり）:
  → 既存スキルの一部として呼ばれている
  → 新規スキル候補にしない
  → ただしワークフローの効率改善候補にはなりうる（Phase C 向け）

ad-hoc（parent_skill なし）:
  → 手動で呼ばれている
  → 繰り返しパターンがあればスキル候補
  → 既存スキルとの類似度が高ければ「このスキル使えるよ」推薦
```

### R6: Prune で parent_skill 経由の使用を認識する（MUST）

Prune の使用回数カウントに以下を含める:
- 直接の Skill tool_use（従来通り）
- `parent_skill` としての参照（新規）

これにより「plan mode 経由で使われているスキル」が淘汰候補から外れる。

### R7: ワークフロー文脈ファイルの寿命管理（MUST）

- セッション終了時（Stop hook）に文脈ファイルを削除する
- 文脈ファイルは24時間経過で自動的に無効とみなす（クラッシュ対応）
- 文脈ファイルの読み取り失敗はサイレントに無視する（セッションをブロックしない）

---

## データストレージの拡張

```
~/.claude/rl-anything/
├── usage.jsonl          # 既存 + parent_skill, workflow_id フィールド追加
├── subagents.jsonl      # 既存 + parent_skill, workflow_id フィールド追加
├── workflows.jsonl      # 新規: ワークフローシーケンス記録
├── errors.jsonl         # 変更なし
├── sessions.jsonl       # 変更なし
└── ...
```

### 後方互換性

- `parent_skill`, `workflow_id` が null のレコードは「トレーシング導入前のデータ」として扱う
- backfill データ（`source: "backfill"`）には parent_skill を付与できない（トランスクリプトに文脈情報がないため）
- Discover/Prune は null を「不明」として保守的に扱う（ad-hoc にも contextualized にもカウントしない）

---

## hooks.json の変更

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": { "tool_name": "Skill" },
        "hooks": [{
          "type": "command",
          "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/workflow_context.py\"",
          "timeout": 5000
        }]
      }
    ],
    "PostToolUse": [
      "(既存の observe.py — parent_skill 読み取りロジックを追加)"
    ],
    "SubagentStop": [
      "(既存の subagent_observe.py — parent_skill 読み取りロジックを追加)"
    ],
    "Stop": [
      "(既存の session_summary.py — workflows.jsonl 書き出し + 文脈ファイル削除を追加)"
    ]
  }
}
```

新規ファイル: `hooks/workflow_context.py`（PreToolUse handler）
変更ファイル: `hooks/observe.py`, `hooks/subagent_observe.py`, `hooks/session_summary.py`

---

## 検証方法

### 手動検証シナリオ

1. `/opsx:refine` を実行 → 内部で Agent:Explore が呼ばれる → usage.jsonl に `parent_skill: "opsx:refine"` が記録されることを確認
2. 手動で Agent:Explore を呼ぶ → `parent_skill: null` が記録されることを確認
3. セッション終了 → workflows.jsonl にシーケンスレコードが書き出されることを確認
4. `python3 skills/discover/scripts/discover.py` → contextualized/ad-hoc が分類されていることを確認
5. Prune で opsx:refine が淘汰候補から外れることを確認

### 自動テスト

- hooks/tests/ に PreToolUse handler のテスト追加
- observe.py の parent_skill 読み取りテスト追加
- discover.py の contextualized/ad-hoc 分類テスト追加
- prune.py の parent_skill 経由カウントテスト追加

---

## Phase C（ワークフロー構造進化）への接続

このトレーシングデータが蓄積された後、以下の設計判断を行う:

### C の設計判断に必要なデータ（このフェーズで収集）

| 判断事項 | 必要なデータ | 収集元 |
|----------|-------------|--------|
| ワークフロー構造の表現形式 | 実際のワークフローにどんなステップがあるか | workflows.jsonl の steps |
| mutation の操作セット | ステップの並びにどんなバリエーションがあるか | 同一 skill_name の workflows.jsonl を比較 |
| fitness の測定方法 | ユーザーがどのワークフローで満足しているか | workflow の完了率、所要時間、ユーザー介入回数 |

### C の設計判断ポイント（データを見てから決める）

**1. ワークフロー構造の表現**

workflows.jsonl に蓄積されたシーケンスパターンを分析し、以下を判断:
- SKILL.md 内に構造化ブロック（YAML）で定義するか
- 別ファイル（workflow.yaml）に分離するか
- マークダウンの自然言語ステップから自動推定するか

判断基準: 実際の workflows.jsonl で、同じスキルの呼び出しパターンがどの程度一貫しているか。一貫性が高ければ構造化の価値がある。ばらつきが大きければ自然言語の方が適切。

**2. mutation の操作セット**

同一スキルの workflow シーケンスバリエーションを比較し、以下を判断:
- ステップ入れ替えに価値があるか（順序に意味があるか）
- ステップ統合に価値があるか（冗長な分割がないか）
- ステップ追加/削除に価値があるか（必須ステップと任意ステップの区別）

判断基準: workflows.jsonl で「ユーザーが途中でやり直したワークフロー」と「一発で完了したワークフロー」のステップ構造の差分。

**3. fitness の測定方法**

workflows.jsonl のメタデータを分析し、以下を判断:
- dry-run（LLM 評価）で十分か、実行ベースの評価が必要か
- ワークフロー完了率だけで測れるか、所要時間も必要か
- ユーザー介入（手動 Agent 呼び出し）の回数が品質指標になるか

判断基準: 「成功したワークフロー」と「ユーザーが手動介入したワークフロー」の特徴量の差。

### タイムライン

```
Phase B（このドキュメント）         Phase C（次のステップ）
┌──────────────────────┐          ┌──────────────────────────┐
│ 1. PreToolUse hook   │          │ 1. workflows.jsonl を    │
│ 2. observe.py 修正   │          │    分析して設計判断      │
│ 3. workflows.jsonl   │    →     │ 2. SKILL.md の構造拡張   │
│ 4. Discover 分類     │  データ  │ 3. optimizer の進化対象   │
│ 5. Prune 修正        │  蓄積    │    拡張                  │
│                      │          │ 4. workflow fitness      │
│ 期間: 2-3日          │          │                          │
│ データ蓄積: 1-2週間  │          │ 期間: 設計1週 + 実装1週   │
└──────────────────────┘          └──────────────────────────┘
```

Phase B 実装後、1-2週間の通常利用でデータを蓄積してから Phase C の設計に入る。
