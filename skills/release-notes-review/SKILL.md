---
name: release-notes-review
effort: medium
description: |
  Claude Code のリリースノートを分析し、現在のプロジェクト環境（CLAUDE.md, skills, hooks, agents）と
  比較して適用可能な新機能・改善点を優先度別に報告する。高優先度の項目は OpenSpec change 提案まで一貫して行う。
  Trigger: release-notes, リリースノート確認, CC更新確認, バージョンアップ対応, release notes review,
  新機能チェック, Claude Code アップデート確認
  Use this skill whenever the user mentions Claude Code updates, version upgrades, release notes,
  or wants to check if their project can benefit from new Claude Code features. Also trigger when
  the user asks "何か新しい機能ある？" or "CC更新で使えるものは？" in the context of Claude Code.
---

# /rl-anything:release-notes-review — リリースノート分析 & 適用提案

Claude Code のリリースノートから**未チェック分のみ**を抽出し、プロジェクト環境と突合して
適用可能な改善点を優先度付きレポートとして出力する。

## Usage

```
/rl-anything:release-notes-review              # フル分析
/rl-anything:release-notes-review --report-only # レポートのみ（OpenSpec 提案なし）
```

## 実行手順

### Step 0: バージョン範囲の決定

1. **現在の CC バージョン取得**: `claude --version` を Bash で実行
2. **チェック済みバージョン確認**: auto-memory から `release_notes_last_checked.md` を Read で探す
   - 場所: `~/.claude/projects/<encoded-project-path>/memory/release_notes_last_checked.md`
   - なければ初回実行として扱う（全バージョンが対象）
3. **差分判定**: 現在バージョン ≤ チェック済みバージョン → 「新しいバージョンはありません」で終了

### Step 1: リリースノートの取得（未チェック分のみ）

`/release-notes` はビルトインスラッシュコマンド（Skill tool では呼び出せない）。

**取得方法**（優先順位順）:
1. `/release-notes` の出力が既に会話コンテキストにある → そのまま使用
2. ない場合 → 以下のいずれかで取得:
   - `gh api repos/anthropics/claude-code/contents/CHANGELOG.md -q .content | base64 -d` (GitHub API)
   - WebFetch で `https://code.claude.com/docs/en/changelog` (公式ドキュメント)

取得後、**チェック済みバージョン以前のエントリはすべて除外**し、未チェック分のみを分析対象にする。
これによりコンテキスト消費を大幅に削減する。

### Step 2: プロジェクト環境のスナップショット

現在の環境を把握するために以下を読み取る（先頭 20-30 行の frontmatter/設定部分のみ）:

1. **CLAUDE.md** — プロジェクト構成、スキル一覧、コンポーネント情報
2. **スキル frontmatter** — 全 `skills/*/SKILL.md` の frontmatter
3. **フック定義** — `hooks/hooks.json`
4. **エージェント定義** — `.claude/agents/*.md` と `agents/*.md` の両方
5. **plugin.json** — `.claude-plugin/plugin.json`

### Step 3: 突合分析

未チェック分のリリースノートについて、環境との関連性を判定する。

**関連性の判定基準**:
- **plugin/skill 関連**: frontmatter 新フィールド、skill hooks、context:fork、${CLAUDE_SKILL_DIR} 等
- **hook 関連**: 新フックイベント（PostCompact, WorktreeCreate 等）、フック改善
- **agent 関連**: model フィールド、memory スコープ、isolation:worktree、background:true
- **API/SDK 関連**: Agent SDK 変更、構造化出力、新ツール
- **UX 改善**: コマンド改善、パフォーマンス改善、影響を受けるバグ修正

**適用範囲の制約**（誤提案防止）:
- `once: true` は **skill hooks 専用**。settings hooks（hooks.json）では使えない
- `context: fork` はステップバイステップ実行のスキルのみ。対話的スキルには不適
- `${CLAUDE_SKILL_DIR}` は SKILL.md 内のみ。Python コードは `Path(__file__)` ベース

**除外基準**: IDE/OS 固有修正、適用済み機能、プロジェクト無関係の機能

### Step 4: 優先度分類 & レポート出力

```markdown
# Release Notes Review Report

**分析日**: YYYY-MM-DD
**対象バージョン範囲**: vX.Y.Z 〜 vA.B.C（前回チェック: vX.Y.Z）
**検出項目数**: N件（即適用: X / 中期: Y / 長期: Z）

## 即適用可能 🟢
- frontmatter 1行追加、hooks.json エントリ追加等、コード変更不要 or 極めて軽微

### [項目名]
- **バージョン**: vX.Y.Z
- **内容**: 1-2行の説明
- **適用方法**: 具体的な変更手順
- **影響ファイル**: 変更が必要なファイル一覧
- **期待効果**: 何が改善されるか

## 中期検討 🟡
- コード変更あり、影響範囲限定的、テスト追加必要

### [項目名]
- **バージョン**: vX.Y.Z
- **内容**: 1-2行の説明
- **必要な作業**: 実装ステップ概要
- **影響範囲**: 変更が及ぶモジュール/スキル

## 長期 🔵
- アーキテクチャ変更、調査/PoC 必要、安定待ち

### [項目名]
- **バージョン**: vX.Y.Z
- **内容**: 1-2行の説明
- **検討理由**: なぜ今すぐ適用しないか
```

### Step 5: チェック済みバージョンの記録

レポート出力後、auto-memory に `release_notes_last_checked.md` を Write で保存する:

```markdown
---
name: release-notes-last-checked
description: release-notes-review で最後にチェックした Claude Code バージョン
type: reference
---

last_checked_version: <現在の CC バージョン>
last_checked_date: <本日の日付>
```

### Step 6: OpenSpec change 提案（`--report-only` でない場合）

ユーザーに確認し、選択された項目を `/openspec-propose` で change 化する。
change 名は `adopt-cc-features-<簡潔な説明>` 形式。

## 注意事項

- リリースノートは膨大になりうる。未チェック分に絞った後でも、
  まず plugin/skill/hook/agent 関連キーワードでフィルタし、関連エントリのみ詳細分析する。
- `openspec/changes/` に既存の adopt-cc-features change がある場合、重複提案を避ける。
- 「適用済み」の判定は実際のファイル内容に基づく（CLAUDE.md の記述だけで判断しない）。
- エージェント定義は `.claude/agents/` と `agents/` の両方を確認する。
