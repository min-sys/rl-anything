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

Step 1 の JSON データ **および会話コンテキスト** を元に、以下のセクションで Markdown ノートを生成する:

```markdown
# Handover: {日付} {時刻}

## Summary
{今回のセッションで何をしたか 1-3 行}

## Decisions
{決定事項とその理由（箇条書き）}

## Discarded Alternatives
{検討したが捨てた選択肢とその理由（箇条書き）。なければ「なし」}

## Next Steps
{次にやるべきこと（優先順付き箇条書き）}

## Related Files
{変更・参照した主要ファイル一覧}

## Corrections
{セッション中の修正・方針転換（あれば）}
```

**重要ルール**:
- 会話コンテキストから「なぜその決定をしたか」「何を試して何がダメだったか」を必ず含める（MUST）
- JSON データの `skills_used` から使用したスキル/ワークフローを Summary に反映する
- JSON データの `corrections` があれば Corrections セクションに反映する
- `Discarded Alternatives` は省略しない — エージェントが同じ失敗を繰り返さないための最重要セクション

### Step 3: ファイル書き出し

生成したノートを以下のパスに Write で書き出す:

```
{CLAUDE_PROJECT_DIR}/.claude/handovers/YYYY-MM-DD_HHmm.md
```

ディレクトリが存在しない場合は作成する（`mkdir -p`）。

### Step 4: 確認

書き出したファイルのパスをユーザーに伝える。

## allowed-tools

Read, Write, Bash, Glob, Grep
