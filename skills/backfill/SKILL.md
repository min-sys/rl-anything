# /rl-anything:backfill — セッション履歴のバックフィル

既存の Claude Code セッショントランスクリプトから Skill/Agent ツール呼び出しを抽出し、
observe hooks と同形式の usage.jsonl にバックフィルする。

## Usage

```
/rl-anything:backfill                        # カレントプロジェクトをバックフィル
/rl-anything:backfill --project-dir /path    # 指定プロジェクトをバックフィル
/rl-anything:backfill --force                # 既存バックフィルを削除して再実行
```

## 実行手順

### Step 1: バックフィル実行

```bash
python3 <PLUGIN_DIR>/skills/backfill/scripts/backfill.py --project-dir "$(pwd)"
```

結果の JSON サマリを表示する（MUST）。

### Step 2: --force による再実行（オプション）

バックフィルが中断された場合、`--force` で既存バックフィルレコードを削除して再処理する。

```bash
python3 <PLUGIN_DIR>/skills/backfill/scripts/backfill.py --project-dir "$(pwd)" --force
```

## 出力形式

バックフィルレコードには `source: "backfill"` が付与され、リアルタイム hooks データと区別可能。

## allowed-tools

Read, Bash, Glob, Grep

## Tags

backfill, observe, usage, history
