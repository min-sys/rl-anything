---
name: discover
description: |
  Detect repeating patterns from observation data (usage, errors, history) and generate
  skill/rule candidates. Outputs structured artifacts meeting quality constraints.
  Trigger: discover, パターン発見, pattern detection, skill generation, スキル生成
---

# /rl-anything:discover — パターン発見

観測データ（usage.jsonl, errors.jsonl, history.jsonl）から繰り返しパターンを検出し、
スキル/ルール候補を生成する。生成されるアーティファクトは構造的制約を満たさなければならない（MUST）。

## Usage

```
/rl-anything:discover [--scope global|project] [--session-scan]
```

### オプション

- `--session-scan`: セッション JSONL のユーザーメッセージテキストを直接分析し、繰り返しパターン（5回以上）をスキル候補として検出する。usage.jsonl ベースの行動パターン検出と補完的に機能し、ツール呼び出しに表れないテキストレベルの繰り返しを発見できる。

## 実行手順

### Step 1: パターン検出

```bash
python3 <PLUGIN_DIR>/skills/discover/scripts/discover.py [--session-scan]
```

### Step 2: 検出結果の表示

- **行動パターン** (5+回): スキル候補として提案（usage.jsonl ベース）
- **セッションテキストパターン** (5+回): スキル候補として提案（`--session-scan` 時のみ、セッション JSONL ベース）
- **エラーパターン** (3+回): ルール候補（予防策）として提案
- **却下理由パターン** (3+回): ルール候補（品質基準）として提案

### Step 3: スキル/ルール候補の生成

検出されたパターンごとに、Claude CLI を使って候補を生成する。

**スキル候補の生成**: SKILL.md 形式で500行以下（MUST）
**ルール候補の生成**: 3行以内（MUST）

### Step 4: スコープ配置の判断

各候補について配置先を決定する（MUST）:
- **global**: git/commit/PR/テスト/lint/Claude Code 自体に関連するパターン
- **project**: 特定フレームワーク依存・ドメイン固有・ファイルパス依存パターン
- **global + Usage Registry**: 特定ツール依存（figma 等）で複数PJで使われうるパターン

### Step 5: 候補の提示

生成された候補をユーザーに提示し、承認/却下を確認する。
同一パターンが2回 reject された場合、抑制リストに追加し3回目以降は提案しない。

### Step 6: corrections.jsonl 連携（オプション）

corrections.jsonl（`~/.claude/rl-anything/corrections.jsonl`）が存在する場合、修正フィードバックデータも入力ソースとして利用する。
未生成時は他の入力ソースのみで正常に動作する（MUST）。
旧 claude-reflect の learnings-queue.json からのデータは `scripts/migrate_reflect_queue.py` で corrections.jsonl に移行できる。

## allowed-tools

Read, Bash, AskUserQuestion, Write, Glob, Grep

## Tags

discover, pattern-detection, skill-generation
