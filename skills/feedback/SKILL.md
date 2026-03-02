# /rl-anything:feedback — フィードバック収集

rl-anything プラグインへのフィードバックを GitHub Issue として送信する。

## Usage

```
/rl-anything:feedback
```

## 対話フロー

1. **カテゴリ選択**: バグ報告 / 機能提案 / 改善要望 / その他
2. **ドメイン選択**: optimize / rl-loop / discover / prune / audit / evolve / その他
3. **スコア入力**: 1-5（1=不満, 5=大変満足）
4. **自由記述**: 詳細な説明

## 実行手順

### Step 1: gh 認証チェック

```bash
gh auth status 2>&1
```

認証されていない場合:
- フィードバックを `~/.claude/rl-anything/feedback-drafts/` にローカル保存する（MUST）
- 「gh auth login で認証後、再度 /rl-anything:feedback を実行してください」と案内

### Step 2: 対話フロー

AskUserQuestion ツールで以下を順に質問:

1. カテゴリ（header: "Category", options: バグ報告/機能提案/改善要望/その他）
2. 対象コンポーネント（header: "Component", options: optimize/rl-loop/discover/prune/audit/evolve/その他）
3. 満足度スコア（header: "Score", options: 1/2/3/4/5）
4. 自由記述の入力を促す

### Step 3: Issue 本文生成 + プレビュー

以下の形式で Issue 本文を生成:

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

生成した本文を **必ずプレビュー表示** し、ユーザーの承認を得る（MUST）。

### Step 4: Issue 送信

```bash
gh issue create --repo shohu/rl-anything --title "[Feedback] {category}: {summary}" --body "{body}" --label "feedback"
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
