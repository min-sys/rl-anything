---
name: implement
effort: medium
description: |
  計画を構造化実装。plan artifact→タスク分解→実装(single/parallel)→検証→テレメトリ記録。
  Trigger: implement, 実装して, 実装開始, build this, 計画を実装, コーディング開始
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion
---

# 構造化実装スキル

plan → implement → ship の「implement」フェーズを構造化する。
計画の決定事項を漏らさず実装し、その軌跡をテレメトリに記録する。

## なぜこのスキルがあるか

「実装して」と言うだけでも Claude は実装できる。しかし:
- plan-eng-review で議論した 8 個の決定事項、全部覚えてる？
- 実装で何タスク・何分かかったか、後から振り返れる？
- 大きめの feature で並列化の判断を毎回手動でやりたい？

このスキルは「やりっぱなしの実装」を「学習する実装」に変える。

## 実行手順

### Step 0: 計画の収集

まず実装の元になる計画を集める。

**gstack plan artifact がある場合:**

```bash
setopt +o nomatch 2>/dev/null || true  # zsh compat
# gstack slug 解決（gstack 未インストールでもエラーにならない）
GSTACK_SLUG=""
if command -v ~/.claude/skills/gstack/bin/gstack-slug &>/dev/null; then
  eval "$(~/.claude/skills/gstack/bin/gstack-slug 2>/dev/null)" 2>/dev/null || true
  GSTACK_SLUG="$SLUG"
fi
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null | tr '/' '-' || echo 'no-branch')
PROJECT_DIR="${GSTACK_HOME:-$HOME/.gstack}/projects/${GSTACK_SLUG:-unknown}"

echo "=== Plan Artifacts ==="
# CEO plan
ls -t "$PROJECT_DIR"/*-${BRANCH}-ceo-plan-*.md 2>/dev/null | head -1 || true
# Test plan
ls -t "$PROJECT_DIR"/*-${BRANCH}-*test-plan-*.md 2>/dev/null | head -1 || true
# Design doc
ls -t "$PROJECT_DIR"/*-${BRANCH}-design-*.md 2>/dev/null | head -1 || true
# Fallback: branch なし
ls -t "$PROJECT_DIR"/*-ceo-plan-*.md 2>/dev/null | head -1 || true
ls -t "$PROJECT_DIR"/*-design-*.md 2>/dev/null | head -1 || true
```

見つかった artifact は全て読む。これが実装の仕様書になる。

**plan artifact が見つからない場合:**
会話の文脈から計画を把握する。ユーザーに「何を実装しますか？」と聞く。
plan-eng-review をこのセッションで実行済みなら、その決定事項を使う。

**会話内に plan mode の plan ファイルがある場合:**
plan ファイルの内容を計画として使う。

### Step 1: タスク分解

計画を読んで、実装タスクに分解する。

**分解ルール:**
- 1 タスク = 1 ファイル or 1 つのまとまった機能
- 各タスクにテストを含める（テスト専用タスクは作らない）
- 同じディレクトリのファイルは同じレーンに割り当て
- 依存関係を明示（Task B が Task A の出力を使うなら記載）
- 上限 15 タスク。超えたら「計画が大きすぎます。フェーズに分割してください」

**出力:**

```
タスク分解
═══════════
| # | タスク | ファイル/モジュール | 依存 | レーン |
|---|--------|-------------------|------|--------|
| 1 | ... | src/lib/ | — | A |
| 2 | ... | src/api/ | — | B |
| 3 | ... | src/lib/ | 1 | A |
```

ユーザーにタスク分解を見せ、OK をもらってから実装に入る。

### Step 2: モード選択と実行

**Standard モード**（タスク 5 未満 or レーン 1 つ）:

各タスクを順番に実行する Ralph Loop:
1. 次のタスクを宣言: 「Task N: {description}」
2. 実装
3. テスト実行（プロジェクトのテストコマンドを使用）
4. テスト通過 → コミット
5. 次のタスクへ

テストが失敗したら、次のタスクに進まず修正する。

**Parallel モード**（タスク 5 以上 AND 独立レーン 2 以上）:

Agent ツールの `isolation: "worktree"` を使い、レーンごとに並列実行する。

> **進捗モニタリング (CC v2.1.98+)**: `run_in_background: true` で起動した subagent や長時間バックグラウンド処理の stdout は、`Monitor` tool で stream として受信できる。`sleep` ポーリングの代替として採用。



各実装エージェントに渡すプロンプト:

```
あなたは大きな計画の一部を実装します。割り当てられたタスクを完了し、
テストを書き、コミットしてください。

タスク:
{このレーンのタスクリスト}

コード品質基準:
- 全ての行・ファイル・抽象化・依存は「必要だから存在する」状態にする
- 明示的 > 巧妙。一見して正しいとわかるコードを書く
- テスタビリティのためだけの抽象化を作らない
- 実装が1つしかないインターフェースを作らない
- 内部データに対する防御的コードを書かない
- 隣接ファイルを読んで既存スタイルに合わせる

{CLAUDE.md のコンベンションがあれば含める}

各タスクの手順:
1. 実装
2. テスト作成
3. テスト実行: {テストコマンド}
4. パス → コミット
5. 次のタスクへ
```

別途、検証エージェント（read-only）を立てて各レーンの成果物をレビューする:

```
あなたはコードレビュアーです。各 diff について確認:
1. 計画の要件を満たしているか？
2. テストは存在し、意味があるか（スモークテストだけでないか）？
3. セキュリティ問題、N+1 クエリ、エラーハンドリング漏れはないか？
簡潔に。本当の問題だけ指摘する。
```

全レーン完了後、worktree ブランチをマージ。コンフリクトがあれば解決を試み、
無理ならユーザーに提示する。マージ後にフルテスト実行。

### Step 3: 計画準拠チェック

全タスク完了後、計画と実装を突き合わせる:

- 計画の各要件を列挙
- 実装で対応するコード/テストを特定
- 未実装の要件があればリストアップ

```
計画準拠チェック
═══════════════
| 要件 | 実装状態 | 対応ファイル |
|------|---------|------------|
| ユーザー認証 API | ✓ | src/auth.ts |
| JWT トークン検証 | ✓ | src/auth.ts:42 |
| レート制限 | ✗ 未実装 | — |

準拠率: 2/3 (67%)
```

未実装の要件がある場合、ユーザーに確認:
- 今すぐ実装する
- NOT in scope として記録
- 次のセッションに持ち越す

### Step 4: テレメトリ記録

実装完了時に rl-anything のテレメトリに記録する。

```python
import json, os, datetime

data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", os.path.expanduser("~/.claude/rl-anything"))
os.makedirs(data_dir, exist_ok=True)

# usage.jsonl に実装スキル使用を記録
record = {
    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "skill": "implement",
    "project": os.path.basename(os.getcwd()),
    "tasks_total": TASKS_TOTAL,       # タスク総数
    "tasks_completed": TASKS_COMPLETED, # 完了タスク数
    "mode": MODE,                      # "standard" or "parallel"
    "conformance_rate": CONFORMANCE,   # 計画準拠率 (0.0-1.0)
    "lanes": LANES,                    # 並列レーン数
    "outcome": OUTCOME,                # "success" / "partial" / "blocked"
}
with open(os.path.join(data_dir, "usage.jsonl"), "a") as f:
    f.write(json.dumps(record, ensure_ascii=False) + "\n")

# growth-journal.jsonl に結晶化イベントを記録（タスク完了時）
if OUTCOME in ("success", "partial"):
    journal = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "type": "implementation",
        "source": "implement-skill",
        "tasks_completed": TASKS_COMPLETED,
        "conformance_rate": CONFORMANCE,
        "mode": MODE,
        "phase": "unknown",  # audit が次回更新
    }
    with open(os.path.join(data_dir, "growth-journal.jsonl"), "a") as f:
        f.write(json.dumps(journal, ensure_ascii=False) + "\n")
```

**上の Python は直接実行するのではなく、変数を実際の値に置き換えて実行する。**

### Step 5: 完了報告と次のステップ

```
実装完了
═══════
モード: Standard / Parallel ({N} レーン)
タスク: {completed}/{total}
コミット: {N} 件
テスト: 全パス / {N} 件失敗
計画準拠率: {N}%

変更ファイル:
  {ファイルリスト}

次のステップ:
  /review — コードレビュー（推奨）
  /qa — QA テスト（UI 変更がある場合）
  /ship — 出荷準備
```

gstack の reviews.jsonl がある環境なら、ビルドログも書く:

```bash
if command -v ~/.claude/skills/gstack/bin/gstack-review-log &>/dev/null; then
  ~/.claude/skills/gstack/bin/gstack-review-log '{"skill":"implement","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","status":"STATUS","tasks_completed":N,"tasks_total":N,"mode":"MODE","conformance_rate":RATE,"commit":"'"$(git rev-parse --short HEAD)"'"}'
fi
```

## エッジケース

- **テストコマンドが不明**: ユーザーに聞く。テストなしの場合は警告して続行
- **未コミットの変更がある**: 「先にコミット or stash しますか？」と確認
- **計画が 7 日以上古い**: 「計画が {N} 日前のものです。コードベースが変わっている可能性があります」と警告
- **単一ファイルの変更**: タスク数に関係なく Standard モード（並列化のメリットなし）
