## 1. 共通モジュールの整理

- [x] 1.1 `backfill.py` の `project_name_from_dir()` を `hooks/common.py` に移動する
- [x] 1.2 `backfill.py` を `common.project_name_from_dir()` を呼び出すように更新する

## 2. analyze.py のフィルタ実装

- [x] 2.1 analyze.py に argparse で --project CLI 引数を追加する
  （デフォルト値: common.project_name_from_dir(os.getcwd())
   = カレントディレクトリの末尾名。例: /Users/foo/rl-anything → "rl-anything"）
- [x] 2.2 `get_project_session_ids(project_name)` 関数を追加 — sessions.jsonl から該当 project_name の session_id セットを返す
- [x] 2.3 `load_jsonl()` に `session_ids: Optional[Set[str]]` フィルタパラメータを追加する
- [x] 2.4 `run_analysis()` を `project` 引数を受け取るように更新し、フィルタ済みデータで分析を実行する
- [x] 2.5 `main()` を argparse 結果で `run_analysis()` を呼び出すように更新する

## 3. SKILL.md の更新

- [x] 3.1 SKILL.md の Step 2 コマンドに `--project "$(basename $(pwd))"` を追加する

## 4. テスト

- [x] 4.1 `test_analyze.py` にプロジェクトフィルタのテストケースを追加する（フィルタ一致 / 不一致 / デフォルト動作）
- [x] 4.2 既存テストが壊れていないことを確認する（`python3 -m pytest skills/ -v`）
