---
name: release-notes-review
effort: medium
description: |
  Claude Code のリリースノートを分析し、プロジェクト環境（CLAUDE.md, skills, hooks, agents）と
  グローバル環境（~/.claude/rules, skills, agents, settings.json）の両方と突合して
  適用可能な新機能・改善点を優先度別に報告する。高優先度の項目は ADR + 実装タスクとして提案する。
  グローバル環境健康診断も実施し、CC 新機能で代替可能なカスタム設定や改善機会を検出する。
  Trigger: release-notes, リリースノート確認, CC更新確認, バージョンアップ対応, release notes review,
  新機能チェック, Claude Code アップデート確認, グローバル環境レビュー, 環境見直し
  Use this skill whenever the user mentions Claude Code updates, version upgrades, release notes,
  or wants to check if their project can benefit from new Claude Code features. Also trigger when
  the user asks "何か新しい機能ある？" or "CC更新で使えるものは？" in the context of Claude Code.
  Also trigger for global environment review requests like "環境の健康診断" or "rules 見直したい".
---

# /rl-anything:release-notes-review — リリースノート分析 & グローバル環境健康診断

Claude Code のリリースノートから**未チェック分のみ**を抽出し、**プロジェクト環境**と
**グローバル環境**の両方と突合して適用可能な改善点を優先度付きレポートとして出力する。
加えて、グローバル環境（rules/skills/agents/settings hooks）の健康診断を行い、
CC 新機能で代替可能なカスタム設定や改善機会を検出する。

## Usage

```
/rl-anything:release-notes-review              # フル分析（リリースノート + 環境健康診断）
/rl-anything:release-notes-review --report-only # レポートのみ（実装提案なし）
/rl-anything:release-notes-review --env-only    # 環境健康診断のみ（リリースノートスキップ）
```

## 実行手順

### Step 0: バージョン範囲の決定

`--env-only` の場合はこのステップをスキップして Step 2 へ。

1. **現在の CC バージョン取得**: `claude --version` を Bash で実行
2. **チェック済みバージョン確認**: auto-memory から `release_notes_last_checked.md` を Read で探す
   - 場所: `~/.claude/projects/<encoded-project-path>/memory/release_notes_last_checked.md`
   - なければ初回実行として扱う（全バージョンが対象）
3. **差分判定**: 現在バージョン ≤ チェック済みバージョン → リリースノート分析はスキップし Step 2.5 へ

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

#### 2.1 プラグイン/プロジェクト環境

1. **CLAUDE.md** — プロジェクト構成、スキル一覧、コンポーネント情報
2. **スキル frontmatter** — 全 `skills/*/SKILL.md` の frontmatter
3. **フック定義** — `hooks/hooks.json`
4. **エージェント定義** — `.claude/agents/*.md` と `agents/*.md` の両方
5. **plugin.json** — `.claude-plugin/plugin.json`

#### 2.2 グローバル環境

6. **グローバル rules** — Glob で `~/.claude/rules/*.md` を列挙し全ファイルを Read
7. **グローバル skills** — Glob で `~/.claude/skills/*/SKILL.md` を列挙し frontmatter を Read
8. **グローバル agents** — Glob で `~/.claude/agents/*.md` を列挙し Read
9. **settings.json** — Read で `~/.claude/settings.json` の hooks セクション

### Step 2.5: グローバル環境健康診断

プロジェクト環境に加え、グローバル環境の品質を診断する。
CC のリリースノートと突合し、新機能で代替可能になった設定も検出する。

#### 2.5.1 Global Rules (`~/.claude/rules/*.md`)

以下を検査:

- **行数チェック**: `rules-style.md` ルールに従い、frontmatter 除外で 3 行以内か
- **重複検出**: 複数ルールが同じことを異なる表現で指示していないか
- **矛盾検出**: ルール間で相反する指示がないか
- **陳腐化チェック**: 参照先ツール/ワークフロー/スキルが現在も存在するか
- **CC 代替チェック**: CC 新機能がルールの役割を吸収していないか
  （例: CC がビルトインで提供するようになった機能を手動ルールで指示している場合）

#### 2.5.2 Global Skills (`~/.claude/skills/*/SKILL.md`)

gstack 内蔵スキル（`~/.claude/skills/gstack/` 配下および `~/.claude/skills/gstack-*/`）を除外し、自作/サードパーティを対象:

- **CC 機能重複チェック**: CC 新機能が自作スキルの役割を吸収していないか
- **frontmatter 品質**: name, description が存在するか。description にトリガーワードがあるか
- **新機能活用チャンス**: CC の新機能で既存スキルを強化できないか
  （例: 新しい frontmatter フィールド、skill hooks、context:fork 等）

#### 2.5.3 Global Agents (`~/.claude/agents/*.md`)

各エージェント定義を Read で確認:

- **品質チェック**: model 指定、maxTurns、disallowedTools の有無
- **新機能活用**: CC の新エージェント機能（memory スコープ、isolation:worktree 等）の活用余地
- **参照の有効性**: 参照しているスキルやツールが現存するか

#### 2.5.4 Settings Hooks (`~/.claude/settings.json`)

hooks 定義を確認:

- **孤立検出**: 参照先スクリプトが存在するか
- **新フックイベント活用**: CC が新たに追加したフックイベント（PostCompact, WorktreeCreate 等）の活用余地
- **rl-anything hooks との整合**: プラグインの hooks.json と settings.json で重複・競合がないか

#### 2.5.5 Memory (`~/.claude/projects/*/memory/MEMORY.md`)

現在プロジェクトの MEMORY.md を Read で確認:

- **エントリ数**: 200 行の上限に対する使用率
- **陳腐化チェック**: 古いバージョン番号、完了済みタスク、存在しないファイルへの参照

### Step 3: 突合分析

未チェック分のリリースノートについて、**プラグイン環境**と**グローバル環境**の両方との関連性を判定する。

**関連性の判定基準**:
- **plugin/skill 関連**: frontmatter 新フィールド、skill hooks、context:fork、${CLAUDE_SKILL_DIR} 等
- **hook 関連**: 新フックイベント（PostCompact, WorktreeCreate 等）、フック改善
- **agent 関連**: model フィールド、memory スコープ、isolation:worktree、background:true
- **API/SDK 関連**: Agent SDK 変更、構造化出力、新ツール
- **UX 改善**: コマンド改善、パフォーマンス改善、影響を受けるバグ修正
- **グローバル環境影響**: 新機能がグローバル rules/skills/agents/settings hooks に影響するか
- **環境代替**: Step 2.5 で検出した CC 代替可能項目との紐づけ

**適用先の分類**: 各項目について以下のいずれかを明記する:
- **プラグイン適用**: rl-anything プラグイン内のファイル変更
- **グローバル適用**: `~/.claude/` 配下のファイル変更
- **両方**: 両環境に影響

**適用範囲の制約**（誤提案防止）:
- `once: true` は **skill hooks 専用**。settings hooks（hooks.json）では使えない
- `context: fork` はステップバイステップ実行のスキルのみ。対話的スキルには不適
- `${CLAUDE_SKILL_DIR}` は SKILL.md 内のみ。Python コードは `Path(__file__)` ベース

**除外基準**: IDE/OS 固有修正、適用済み機能、プロジェクト無関係の機能

### Step 4: 優先度分類 & レポート出力

2 セクション構成のレポートを出力する。`--env-only` の場合は Part 1 を省略し Part 2 のみ。

```markdown
# CC Release Notes & Environment Health Report

**分析日**: YYYY-MM-DD
**CC バージョン**: vX.Y.Z → vA.B.C（前回チェック: vX.Y.Z）

---

## Part 1: Release Notes Review

**検出項目数**: N件（即適用: X / 中期: Y / 長期: Z）

### 即適用可能 🟢
- frontmatter 1行追加、hooks.json エントリ追加等、コード変更不要 or 極めて軽微

#### [項目名]
- **バージョン**: vX.Y.Z
- **適用先**: プラグイン / グローバル / 両方
- **内容**: 1-2行の説明
- **適用方法**: 具体的な変更手順
- **影響ファイル**: 変更が必要なファイル一覧
- **期待効果**: 何が改善されるか

### 中期検討 🟡

#### [項目名]
- **バージョン**: vX.Y.Z
- **適用先**: プラグイン / グローバル / 両方
- **内容**: 1-2行の説明
- **必要な作業**: 実装ステップ概要
- **影響範囲**: 変更が及ぶモジュール/スキル

### 長期 🔵

#### [項目名]
- **バージョン**: vX.Y.Z
- **適用先**: プラグイン / グローバル / 両方
- **内容**: 1-2行の説明
- **検討理由**: なぜ今すぐ適用しないか

---

## Part 2: Global Environment Health

### Rules (N total)
問題なし:
- [rule] — OK

要確認:
- [rule] — [issue: 行数超過 / 重複 / 矛盾 / 陳腐化]

CC 代替候補:
- [rule] — CC [vX.Y.Z] の [feature] で代替可能

### Custom Skills (N total, gstack 内蔵除外)
問題なし:
- [skill] — OK

CC 機能重複:
- [skill] — CC の [built-in feature] と重複

強化チャンス:
- [skill] — CC [vX.Y.Z] の [feature] で改善可能

### Agents (N total)
- [agent] — OK / [issue]

### Settings Hooks
- [hook event] — OK / [issue: 孤立 / 新イベント未活用]

### Memory
- エントリ数: N行 / 200行上限
- 陳腐化候補: [entry] — [reason]
```

### Step 5: チェック済みバージョンの記録

`--env-only` の場合はこのステップをスキップする（リリースノートを確認していないため）。

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

### Step 6: 実装提案（`--report-only` でない場合）

ユーザーに確認し、選択された項目について:
1. **プラグイン適用項目**: rl-anything 内のファイル変更手順を提示
2. **グローバル適用項目**: `~/.claude/` 配下の変更手順を提示
3. 環境の問題（ルール行数超過、孤立 hook 等）の修正を提案
4. CC 代替候補について、移行手順を提示
5. 設計判断がある場合は `/spec-keeper adr` で ADR を作成する

## 注意事項

- リリースノートは膨大になりうる。未チェック分に絞った後でも、
  まず plugin/skill/hook/agent 関連キーワードでフィルタし、関連エントリのみ詳細分析する。
- 既存の ADR や CHANGELOG に同等の変更がある場合、重複提案を避ける。
- 「適用済み」の判定は実際のファイル内容に基づく（CLAUDE.md の記述だけで判断しない）。
- エージェント定義は `.claude/agents/` と `agents/` の両方を確認する。
- rl-anything プラグインの `/audit` とは役割が異なる: audit はテレメトリ駆動の環境品質スコアリング、
  こちらは CC 更新との突合に特化した定性レビュー + グローバル環境健康診断。
- 環境診断はファイルの Read のみで行う。LLM による高コスト分析は避け、構造的チェックに徹する。
