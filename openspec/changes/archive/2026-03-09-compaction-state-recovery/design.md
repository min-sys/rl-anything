Related: #17

## Context

Claude Code の auto-compact 後にタスク完了状態が失われる問題。現在の hook 実装（`save_state.py`/`restore_state.py`）は evolve パイプラインの checkpoint のみを保存しており、ユーザーの作業コンテキストは対象外。

Issue #17 で対策が調査済み:
- Layer 1: CLAUDE.md Compaction Instructions（コストゼロ）
- Layer 3: Hook ベースの状態保存（最も堅牢）

Roadmap の Gap 1-6 と直交する standalone レジリエンス修正。

upstream issue `anthropics/claude-code#14160`（auto-compact 時 custom_instructions が空になる）の制約あり。

## Goals / Non-Goals

**Goals:**
- コンパクション後に完了済みタスク・変更ファイルが保持される
- 既存の save_state/restore_state hook を拡張し、作業コンテキストを保存・復元する
- CLAUDE.md に Compaction Instructions を追加し、コンパクション時のサマリー品質を向上させる

**Non-Goals:**
- upstream issue の修正（`#14160` 等）
- LLM を使った高度なコンテキスト要約（hook は 5000ms timeout、LLM 呼び出しなし）
- コンパクション自体の頻度制御やタイミング最適化

## Decisions

### D1: 既存 hook の拡張 vs 新規 hook 作成

**決定**: 既存の `save_state.py` / `restore_state.py` を拡張する

**理由**: hooks.json に既に PreCompact / SessionStart が登録済み。新規ファイルを追加すると hooks.json の管理が複雑化する。既存の checkpoint.json に作業コンテキストフィールドを追加する形が最もシンプル。

### D2: 作業コンテキストの取得方法

**決定**: git コマンド 2 つで取得する

**代替アプローチの検討:**
- **telemetry reuse**: 既存の usage.jsonl / sessions.jsonl から作業状態を推定する案。しかしテレメトリは「何を使ったか」であり「何が完了したか」の精度が不十分
- **TodoWrite**: Claude Code の TodoWrite ツールで管理する案。しかし compaction 後に TodoWrite の状態自体が失われるため fragile
- **event stdin**: PreCompact イベントの stdin に conversation が含まれる将来に期待する案。現時点でスキーマ未確定のため依存不可

**→ git primary**: 確実に取得できる git の状態を primary source とする

取得コマンド:
1. `git log --oneline -5` — 直近5コミット（完了タスクの代理指標）
2. `git status --short` — 未コミット変更ファイル一覧

### D3: checkpoint.json のスキーマ拡張

**決定**: 既存スキーマにフィールドを追加（後方互換）。committed（コミット済み）と uncommitted（未コミット）を分離する。

```json
{
  "session_id": "...",
  "timestamp": "...",
  "evolve_state": {},
  "corrections_snapshot": [],
  "work_context": {
    "recent_commits": ["abc1234 fix: something"],
    "uncommitted_files": ["path/to/file1"],
    "git_branch": "feature/x"
  }
}
```

### D4: restore_state の出力形式

**決定**: 復元時に人間可読なサマリーを stdout に出力し、Claude が作業状態を把握できるようにする。committed（完了）と uncommitted（作業中）を分離表示する。

**理由**: JSON のみだと Claude が解釈しにくい。`[rl-anything:restore_state]` プレフィックス付きの自然言語サマリーを追加出力する。

出力例:
```
[rl-anything:restore_state] 作業コンテキスト復元:
  ブランチ: feature/x
  完了: abc1234 fix: something, def5678 feat: another
  作業中: path/to/file1, path/to/file2
```

### D5: Layer 1 — Compaction Instructions の配置

**決定**: CLAUDE.md に `## Compaction Instructions` セクションを追加

**理由**: Claude Code は CLAUDE.md を常にコンテキストに含める。upstream issue #14160 の影響でauto-compact時に custom_instructions が空になる問題があるが、CLAUDE.md 自体はコンテキストに残るため、圧縮プロンプトの品質向上に寄与する。

### D7: 定数化方針

**決定**: `save_state.py` モジュール先頭に以下の定数を定義する（`common.py` パターン準拠）

```python
_MAX_UNCOMMITTED_FILES = 30
_MAX_RECENT_COMMITS = 5
_GIT_TIMEOUT_SECONDS = 2
```

### D8: 合計 timeout ガード

**決定**: `_collect_work_context()` 内で elapsed tracking を行い、合計 3.5s 超過時に残りの git コマンドを skip する

**理由**: hook の 5000ms timeout 内に確実に収めるため。git コマンド個別 timeout（2s）× 2 = 4s が最悪ケースだが、合計ガードにより 3.5s で打ち切ることで checkpoint 保存自体の時間を確保する。

## Risks / Trade-offs

- **[R1] PreCompact hook の timeout 超過** → `git log` / `git status` は通常 100ms 以内。5000ms timeout に十分収まる。subprocess 呼び出しにも個別 timeout + 合計 timeout ガードを設定する
- **[R2] upstream #14160 により Layer 1 が無効化される可能性** → Layer 3 の hook ベース復元があるため、Layer 1 が機能しなくても致命的ではない
- **[R3] checkpoint.json の肥大化** → uncommitted_files は最大30件に制限。recent_commits は5件固定
