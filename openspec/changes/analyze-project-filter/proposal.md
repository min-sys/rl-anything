## Why

`analyze.py` が JSONL データを全件読み込むため、複数プロジェクトの backfill データが混在した分析結果になる。`backfill.py` は `--project-dir` でプロジェクトスコープされるのに対し、`analyze.py` にはフィルタ機構がなく、プロジェクト横断の不正確なレポートが出力される（GitHub Issue #1）。

## What Changes

- `analyze.py` に `--project` CLI 引数を追加（デフォルト: カレントディレクトリ名）
- `load_jsonl()` または各分析関数で `project_name` フィールドによるフィルタを実装
- `run_analysis()` がプロジェクト名を受け取りフィルタ済みデータで分析を実行
- SKILL.md の Step 2 コマンドを `--project-dir` パラメータ付きに更新

## Capabilities

### New Capabilities

- `analyze-project-filter`: analyze.py にプロジェクト単位のデータフィルタリング機能を追加

### Modified Capabilities

（なし）

## Impact

- **コード**: `skills/backfill/scripts/analyze.py` — CLI 引数追加、フィルタロジック追加
- **コード**: `skills/backfill/scripts/tests/test_analyze.py` — フィルタ機能のテスト追加
- **ドキュメント**: `skills/backfill/SKILL.md` — Step 2 コマンド更新
- **データ**: 既存の JSONL ファイルへの変更なし（読み取り時フィルタのみ）
