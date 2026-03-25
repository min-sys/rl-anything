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
/rl-anything:handover
```

## 実行手順

### Step 1: データ収集

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/handover/scripts/handover.py" --project-dir "${CLAUDE_PROJECT_DIR:-.}"
```

返却された JSON を変数として保持する。

### Step 2: 構造化ノート生成

Step 1 の JSON データ **および会話コンテキスト** を元に、以下のセクションで Markdown ノートを生成する。

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

**重要ルール**:
- 会話コンテキストから「なぜその決定をしたか」「何を試して何がダメだったか」を必ず含める（MUST）
- `Discarded Alternatives` は省略しない — エージェントが同じ失敗を繰り返さないための最重要セクション
- `Deploy State` は会話コンテキストから判断する（MUST）— デプロイ済み/未デプロイが後続の `/ship` 等の次アクション提案に影響する
- `Next Actions` は `Deploy State` を考慮して記述する — デプロイ済みなら merge-first フロー、未デプロイなら deploy-first フローを推奨
- `Context (auto)` セクションは JSON データをそのまま展開する（LLM による要約不要）
- Summary / Related Files セクションは **廃止** — checkpoint.json + git で復元可能

### Step 3: ファイル書き出し

生成したノートを以下のパスに Write で書き出す:

```
{CLAUDE_PROJECT_DIR}/.claude/handovers/YYYY-MM-DD_HHmm.md
```

ディレクトリが存在しない場合は作成する（`mkdir -p`）。

### Step 4: SPEC.md 同期

プロジェクトに SPEC.md が存在する場合、`/spec-keeper update` を実行して仕様を最新化する。
SPEC.md が存在しない場合はスキップ。

### Step 5: 確認

書き出したファイルのパスをユーザーに伝える。SPEC.md を更新した場合はその旨も伝える。

## allowed-tools

Read, Write, Bash, Glob, Grep
