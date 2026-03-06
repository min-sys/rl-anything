## 1. 共通モジュール: tool_usage_analyzer.py

- [x] 1.1 `scripts/lib/tool_usage_analyzer.py` を作成。セッション JSONL からツール呼び出し（tool_use）を抽出する `extract_tool_calls(project_root)` 関数を実装。`project_root` から `CLAUDE_PROJECTS_DIR` 配下のセッションディレクトリを解決する（discover.py の既存パターンに準拠）
- [x] 1.2 Bash コマンド分類関数 `classify_bash_commands(commands)` を実装。3カテゴリ（builtin_replaceable / repeating_pattern / cli_legitimate）に分類。対象コマンドと代替ツールのマッピングは `BUILTIN_REPLACEABLE_MAP` 辞書としてモジュールレベルに定義（例: `{"cat": "Read", "grep": "Grep", "sed": "Edit"}` ）
- [x] 1.3 繰り返しパターン検出関数 `detect_repeating_commands(commands, threshold=5)` を実装。先頭語+サブコマンドでグルーピングし、閾値以上のパターンを返す。閾値は `REPEATING_THRESHOLD = 5` としてモジュールレベル定数に定義（discover.py の `BEHAVIOR_THRESHOLD` パターンに準拠）
- [x] 1.4 統合関数 `analyze_tool_usage(project_slug, threshold=5)` を実装。抽出→分類→検出を一括実行し、discover 向けの結果辞書を返す

## 2. テスト

- [x] 2.1 `scripts/lib/tests/test_tool_usage_analyzer.py` を作成。extract_tool_calls のパース・graceful スキップをテスト
- [x] 2.2 classify_bash_commands のテスト: builtin_replaceable（cat/grep/find 等）、cli_legitimate（git/gh 等）、cat+heredoc は除外
- [x] 2.3 detect_repeating_commands のテスト: 閾値以上/未満のパターン検出、サブカテゴリ分類
- [x] 2.4 テスト実行確認: `python3 -m pytest scripts/lib/tests/test_tool_usage_analyzer.py -v`

## 3. discover 統合

- [x] 3.1 `discover.py` に `--tool-usage` CLI 引数を追加
- [x] 3.2 `run_discover()` に `tool_usage` パラメータを追加し、True 時に `analyze_tool_usage()` を呼び出して結果に `tool_usage_patterns` キーを含める
- [x] 3.3 既存テストが壊れないことを確認: `python3 -m pytest skills/discover/scripts/tests/ -v`

## 4. evolve 統合

- [x] 4.1 `evolve.py` の discover フェーズで `tool_usage=True` を渡すように変更
- [x] 4.2 `evolve/SKILL.md` の Step 3 にツール利用分析セクションの表示ガイドを追加
- [x] 4.3 既存テストが壊れないことを確認: `python3 -m pytest skills/evolve/scripts/tests/ -v`

## 5. 結合テスト

- [x] 5.1 実際のセッション JSONL で `discover.py --tool-usage --project-dir $(pwd)` を実行し、出力を確認
- [x] 5.2 `evolve.py --project-dir $(pwd) --dry-run` でツール利用分析が evolve レポートに含まれることを確認
