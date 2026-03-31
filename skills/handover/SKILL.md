---
name: handover
effort: low
description: |
  セッションの作業状態を構造化ノートに書き出す。次セッションや別コンテキストへの引き継ぎに使用。
  Trigger: handover, 引き継ぎ, 作業引き継ぎ, hand off, 引き渡し, セッション引き継ぎ
---

# /rl-anything:handover — セッション引き継ぎノート生成

現在のセッションで行った作業を構造化ノートに書き出す。

## Usage

```
/rl-anything:handover          # ローカルファイル出力（デフォルト）
/rl-anything:handover --issue   # GitHub Issue として作成
```

## 実行手順

### Step 1: データ収集 + 出力モード判定

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/handover/scripts/handover.py" --issue --project-dir "$(pwd)"
```

返却 JSON の `is_github` フィールドを確認する:
- `--issue` フラグ指定時 → **Issue モード**（Step 2a へ）
- `is_github: true`（フラグなし） → **Issue モード**（Step 2a へ、GitHub リポはデフォルトで Issue）
- `is_github: false` → **ファイルモード**（Step 2b へ）

### Step 2a: Issue モード — 構造化ノート生成 + Issue 作成

Step 1 の JSON 内 `body` テンプレートの `<!-- LLM: ... -->` コメントを **会話コンテキスト** から埋める。

**埋めるセクション**:
- `## Decisions` — 決定事項とその理由（箇条書き）。「なぜそうしたか」を必ず含める
- `## Discarded Alternatives` — 検討したが捨てた選択肢とその理由。なければ「なし」
- `## Deploy State` — 各環境のデプロイ状態。不明なら「不明」
- `## Next Actions` — 次にやるべきこと（優先順付き）。Deploy State を考慮

**重要ルール**（ファイルモードと共通）:
- 会話コンテキストから「なぜその決定をしたか」「何を試して何がダメだったか」を必ず含める（MUST）
- `Discarded Alternatives` は省略しない — エージェントが同じ失敗を繰り返さないための最重要セクション
- `Deploy State` は会話コンテキストから判断する（MUST）
- `Next Actions` は `Deploy State` を考慮して記述する
- `Context (auto)` セクションは JSON データのまま（LLM 要約不要）

LLM が body を埋めたら、`gh issue create` で Issue を作成する:

```bash
gh issue create --title "{title}" --body "{完成した body}" --label "handover"
```

ラベル `handover` が存在しない場合はラベルなしで作成する。

作成された Issue URL をユーザーに伝える。

### Step 2b: ファイルモード — 構造化ノート生成

Step 1 のデータ（`--issue` なしで再取得）**および会話コンテキスト** を元に、以下のセクションで Markdown ノートを生成する。

**このノートの目的**: git/checkpoint/auto-memory では復元できない「判断の理由」と「次の一手」に特化する。

```markdown
# Handover: {日付} {時刻}

## Decisions
{決定事項とその理由（箇条書き）。「なぜそうしたか」を必ず含める}

## Discarded Alternatives
{検討したが捨てた選択肢とその理由（箇条書き）。なければ「なし」}

## Deploy State
{各環境のデプロイ状態。会話コンテキストから判断する。不明なら「不明」}
- dev: {deployed / not deployed / 不明} (commit {hash})
- prod: {deployed / not deployed / 不明} (commit {hash})

## Next Actions
{次にやるべきこと（優先順付き箇条書き）。Deploy State を考慮すること。
デプロイ済みなら merge → 再デプロイ → 動作確認、未デプロイなら デプロイ → 動作確認 → merge}

## Context (auto)
branch: {work_context.git_branch}
commits: {work_context.recent_commits}
uncommitted: {work_context.uncommitted_files}
skills: {skills_used}
corrections: {corrections}
```

**重要ルール**: Step 2a と同じ。Summary / Related Files セクションは **廃止** — checkpoint.json + git で復元可能。

### Step 3: ファイル書き出し（ファイルモードのみ）

生成したノートを以下のパスに Write で書き出す:

```
{project_dir}/.claude/handovers/YYYY-MM-DD_HHmm.md
```

ディレクトリが存在しない場合は作成する（`mkdir -p`）。

### Step 4: SPEC.md 同期

プロジェクトに SPEC.md が存在する場合、`/rl-anything:spec-keeper update` を実行して仕様を最新化する。
SPEC.md が存在しない場合はスキップ。

### Step 5: 確認

- Issue モード: Issue URL をユーザーに伝える
- ファイルモード: 書き出したファイルのパスをユーザーに伝える
- SPEC.md を更新した場合はその旨も伝える

## allowed-tools

Read, Write, Bash, Glob, Grep
