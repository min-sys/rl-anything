---
name: feedback
effort: low
description: |
  Collect feedback about the rl-anything plugin and submit as a GitHub Issue.
  Supports bug reports, feature requests, and improvement suggestions.
  Trigger: feedback, フィードバック, バグ報告, bug report, 機能提案, feature request
---

# /rl-anything:feedback — フィードバック収集

rl-anything プラグインへのフィードバックを GitHub Issue として送信する。

## Usage

```
/rl-anything:feedback
```

## 自動判定フロー

LLM が会話コンテキストから以下を自動判定する（ユーザーへの質問は不要）:

- **カテゴリ**: バグ報告 / 機能提案 / 改善要望 / その他
- **コンポーネント**: optimize / rl-loop / discover / prune / audit / evolve / reflect / その他
- **満足度スコア**: 1-5（1=不満, 5=大変満足）
- **詳細**: 会話内容から要約

ユーザーが `/rl-anything:feedback` で明示的に起動した場合のみ、AskUserQuestion で補足情報を聞いてよい。
それ以外（会話中に自動検出した場合）は LLM 判断で即起票する。

## 実行手順

### Step 1: gh 認証チェック

```bash
gh auth status 2>&1
```

認証されていない場合:
- フィードバックを `~/.claude/rl-anything/feedback-drafts/` にローカル保存する（MUST）
- 「gh auth login で認証後、再度 /rl-anything:feedback を実行してください」と案内

### Step 2: Issue 本文生成

会話コンテキストから自動判定した内容で Issue 本文を生成:

```markdown
## フィードバック

**カテゴリ**: {category}
**コンポーネント**: {component}
**満足度**: {score}/5

## 詳細

{description}

---
*Submitted via /rl-anything:feedback*
```

**プライバシー保護（MUST NOT 違反を防止）**:
- SKILL.md の内容を含めてはならない（MUST NOT）
- ローカルファイルパスを含めてはならない（MUST NOT）
- プロジェクト固有の情報を含めてはならない（MUST NOT）

### Step 3: プレビュー確認

生成した Issue 本文をユーザーに表示し、AskUserQuestion で送信の承認を得る（MUST）。

### Step 4: Issue 送信

```bash
gh issue create --repo min-sys/rl-anything --title "[Feedback] {category}: {summary}" --body "{body}" --label "feedback"
```

送信失敗時のフォールバック:
```bash
mkdir -p ~/.claude/rl-anything/feedback-drafts/
# タイムスタンプ付きで保存
```

## allowed-tools

Read, Bash, AskUserQuestion, Write

## Tags

feedback, issue, github
