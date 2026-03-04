## Context

`/optimize` (genetic-prompt-optimizer) は `claude -p` 経由で LLM にスキルの突然変異・交叉・評価を依頼する。この `claude -p` 呼び出しでは、実行中のプロジェクトの CLAUDE.md やルールが自動的にコンテキストに含まれる。

global スキル（`~/.claude/skills/` 配下）を特定プロジェクトのディレクトリから `/optimize` すると、そのプロジェクト固有の CLAUDE.md が評価・変異の文脈に入り込み、汎用性が損なわれるリスクがある。

現状の optimize.py では scope の概念が存在せず、ターゲットのファイルパスをそのまま使用している。

## Goals / Non-Goals

**Goals:**

- ターゲットスキルの scope（global / project）を自動判定する
- global スキルの最適化時、評価プロンプトにプロジェクト固有コンテキストが混入しないようにする
- SKILL.md でのターゲット選択 UI で scope を表示し、ユーザーが判断できるようにする

**Non-Goals:**

- SKILL.md のターゲット選択 UI 自体の実装（現状は SKILL.md で定義、LLM が解釈）
- global スキルの最適化を禁止する（汎用評価で最適化可能にする）
- project スキルの評価ロジック変更

## Decisions

### 1. scope 判定方法: ファイルパスベース

スキルの物理パスで判定する。

- `~/.claude/skills/` 配下 → global
- それ以外（`.claude/skills/` やプロジェクト内パス） → project

**理由**: プラグインのインストール情報を読む方法もあるが、ファイルパスだけで十分判定でき、外部依存が不要。

### 2. global スキル最適化時の `claude -p` 呼び出し: `--cwd` でホームディレクトリを指定

global スキルの場合、`claude -p` の実行時に `cwd` をユーザーのホームディレクトリ（`~`）に設定する。これにより、プロジェクト固有の CLAUDE.md が読み込まれなくなる。

**代替案と比較:**
- A) `--cwd ~` でホームに移動 → シンプルで確実。**採用**
- B) 評価プロンプトに「プロジェクト固有の文脈を無視して」と指示 → LLM の従順性に依存し不確実
- C) `--no-project-context` フラグ（仮）→ claude CLI にそのようなフラグは存在しない

### 3. scope 表示: SKILL.md のターゲット選択セクションに scope ラベルを追加

SKILL.md のターゲット選択指示に `[global]` / `[project]` ラベルを表示するよう記述を追加。LLM が選択肢を提示する際に scope を併記する。

### 4. 通知メッセージ: global スキル選択時に自動表示

optimize.py の実行開始時に scope を判定し、global の場合は「汎用評価モードで最適化します（プロジェクト固有のコンテキストは使用しません）」と表示する。

## Risks / Trade-offs

- [Risk] `~` に `.claude/` の CLAUDE.md がある場合、それが読み込まれる → global な CLAUDE.md は汎用的な内容なので許容範囲。むしろ有用
- [Risk] `cwd` 変更により workflow_stats.json のパスが解決できなくなる → ワークフローヒントの読み込みパスはプラグインの `__file__` ベースなので影響なし
- [Trade-off] global スキルでもプロジェクト文脈を使いたいケースがある → `--force-project-context` のようなオプションで将来対応可能。現時点では Non-Goal
