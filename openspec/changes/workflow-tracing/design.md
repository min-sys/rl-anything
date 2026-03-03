## Context

rl-anything の observe hooks（PostToolUse, SubagentStop, Stop）はツール呼び出しを JSONL に記録するが、「どのスキルのワークフロー内で呼ばれたか」の文脈情報がない。バックフィルデータ（43レコード）の分析で、Discover が Agent:Explore 22回を新スキル候補と誤提案し、Prune が opsx:refine を使用0回と誤検出する問題を確認した。

OTel GenAI Agent Spans の `invoke_agent` → `execute_tool` 階層構造と、`disler/claude-code-hooks-multi-agent-observability` の context file パターンを参考に、Claude Code hooks の制約内でワークフロー文脈を伝搬する仕組みを設計する。

## Goals / Non-Goals

**Goals:**
- Skill 呼び出し → 後続 Agent/SubagentStop に `parent_skill` を伝搬する
- ワークフロー単位のシーケンスデータを蓄積する（Phase C の入力）
- Discover/Prune の誤検出を解消する
- 既存データとの後方互換性を維持する

**Non-Goals:**
- ネストされたスキル呼び出しのトレーシング（Skill A → Skill B → Agent のような多段構造は対象外。直近の Skill のみを parent とする）
- ワークフロー構造の進化（Phase C で対応。本 change はデータ収集のみ）
- backfill データへの retroactive な parent_skill 付与（トランスクリプトに文脈情報がないため不可。ただしタスク13でワークフロー境界判定による近似解を実装済み）

## Hook イベント構造

### PreToolUse イベント

```json
{
  "tool_name": "Skill",
  "tool_input": {
    "skill": "opsx:refine",
    "args": "..."
  },
  "session_id": "sess-001"
}
```

PostToolUse と同じ `tool_input` 構造。`tool_result` は存在しない（実行前のため）。
`tool_input.skill` でスキル名を取得する（observe.py の既存パターンと同一）。

## Decisions

| # | Decision | Rationale | Alternatives Considered |
|---|----------|-----------|------------------------|
| 1 | 文脈伝搬にファイルベース（`$TMPDIR`）を使用 | Claude Code hooks 間に IPC 機構がない。env 変数は PreToolUse → PostToolUse 間で伝搬しない。ファイルは最もシンプルで hooks/common.py パターンと一貫性がある | a) env 変数: hooks 間で伝搬しない b) DB: 依存追加が重い c) stdout/stderr: hooks 間で接続されない |
| 2 | 文脈ファイルのパスを `$TMPDIR/rl-anything-workflow-{session_id}.json` とする | session_id でスコープすることで並行セッションが干渉しない。$TMPDIR は OS が管理するため明示的なクリーンアップ漏れのリスクが低い | a) `~/.claude/rl-anything/` 配下: 永続データと混在して管理が煩雑 b) `/tmp` 直指定: OS 間の差異 |
| 3 | 同一セッション内で新しい Skill が呼ばれたら文脈を上書きする | セッション内の「直近のスキル」が最も関連性が高い。ネストは Non-Goal | a) スタック構造: 実装複雑化、ネストは Non-Goal b) 全スキル履歴を保持: 分析時に「どの Skill の中か」が曖昧になる |
| 4 | workflows.jsonl のシーケンスは Stop hook で組み立てる | セッション終了時に usage.jsonl を逆引きして同一 workflow_id のレコードを収集する。リアルタイム書き込みより実装がシンプルで、incomplete なシーケンスが残らない | a) リアルタイム追記: incomplete レコード問題 b) 別プロセスで定期集計: 遅延が生じる |
| 5 | Discover は `parent_skill: null` + `source: "backfill"` を `unknown` として除外 | backfill データには文脈情報がないため、ad-hoc/contextualized の判断ができない。保守的に除外することで誤提案を防ぐ | a) 全て ad-hoc 扱い: 既知の誤検出問題を引き起こす b) prompt 分析で推定: 精度が不確実 |
| 6 | `workflow_id` は `wf-{uuid4の先頭8文字}` 形式 | 十分な一意性を持ちつつ、JSONL のレコードサイズを抑える | a) フル UUID: 36文字は JSONL で冗長 b) timestamp ベース: 同一 ms に2つの Skill が呼ばれた場合に衝突 |
| 7 | 文脈ファイル読み取りロジックを `hooks/common.py` の `read_workflow_context(session_id)` に集約 | observe.py と subagent_observe.py の両方で同一の「文脈ファイル読み取り → parent_skill/workflow_id 取得 → 24h expire → エラー時 null」ロジックが必要。`hooks/common.py` に既に `append_jsonl()` 等の共通関数がある既存パターンに合わせて DRY にする | a) 各 hook にコピペ実装: DRY 違反、修正漏れリスク b) 別の共通モジュール: common.py が既に共通関数の集約先として機能しているため不要 |
| 8 | `--force` は対象プロジェクトの session_id のみ削除する（project-scoped） | 複数プロジェクトのデータが `~/.claude/rl-anything/` に混在するため、`--force` で全データを消すと他プロジェクトのデータが失われる。トランスクリプトのファイル名（= session_id）でスコープを絞る | a) 全削除 + 確認プロンプト: スクリプト実行時に対話が必要になり自動化に不向き b) プロジェクト別ディレクトリ: データ分散で横断分析が煩雑 |
| 9 | `steps[].intent_category` は discover.py の `_PROMPT_CATEGORIES` と同じキーワード分類で計算 | usage.jsonl の prompt フィールドからキーワードマッチで分類する既存ロジックを再利用。Phase C でワークフロー構造を分析する際にステップの意図が判別できる | a) LLM で分類: コスト・レイテンシが過大 b) 分類なし: Phase C で各ステップの意図が不明になり分析精度が低下 |

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 文脈ファイルの残骸（セッションクラッシュ時） | 24時間経過で無効とみなす。$TMPDIR は OS 再起動で自動削除される |
| PreToolUse hook の追加によるレイテンシ | ファイル1つ書き出すだけで LLM 呼び出しなし。timeout 5000ms（既存 hook と統一） |
| Stop hook でのワークフロー組み立てが usage.jsonl の全スキャン | workflow_id で逆引きするため、セッション内のレコード数（通常数十行）なら問題なし |
| 並行セッション間での文脈ファイル衝突 | session_id をファイル名に含めることで回避 |
| Skill → Agent の間に人間入力や長時間の操作が挟まる場合 | 文脈ファイルは上書きされるまで有効。24時間で expire するためスタンバイ中のセッション問題も限定的 |
