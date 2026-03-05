## 1. observe hook に project フィールド追加

- [x] 1.1 hooks/observe.py: Skill ツール usage レコードに `project` フィールドを追加（`CLAUDE_PROJECT_DIR` 末尾ディレクトリ名、未設定時または空文字列時は `null`）
- [x] 1.2 hooks/observe.py: Agent ツール usage レコードに同様の `project` フィールドを追加
- [x] 1.3 hooks/observe.py: errors レコードに `project` フィールドを追加
- [x] 1.4 hooks/ のテストを追加・更新（project フィールドの記録を検証。空文字列 → `null` のケースを含む）

## 2. DuckDB 共通クエリ層

- [x] 2.1 scripts/lib/telemetry_query.py を作成: DuckDB で JSONL を読む基本関数（`query_usage()`, `query_errors()`, `query_skill_counts()`）。戻り値型は全関数共通で `List[Dict[str, Any]]`。`query_skill_counts()` の dict は `{"skill_name": str, "count": int}` 構造。`read_json_auto()` は `ignore_errors=true` を指定
- [x] 2.2 DuckDB 未インストール時の graceful fallback（既存 `load_jsonl()` + Python フィルタへのフォールバック + stderr 警告）。フォールバック時も `project` フィールドによるフィルタリングを維持する MUST
- [x] 2.3 telemetry_query.py のユニットテスト（DuckDB あり/なし両方。フォールバック時の project フィルタ検証を含む）

## 3. discover の project フィルタリング

- [x] 3.1 discover.py: `detect_behavior_patterns()` を telemetry_query.py 経由に書き換え（既存の `load_jsonl()` を置換）、`project_root` フィルタを追加
- [x] 3.2 discover.py: `detect_error_patterns()` に `project_root` フィルタを追加
- [x] 3.3 discover.py: `run_discover()` と `main()` に `--project-dir` CLI 引数を追加（Python API 側のパラメータ名は `project_root` で統一）
- [x] 3.4 discover.py: `--include-unknown` フラグを追加。指定時は `project` が `null` のレコードも集計に含める
- [x] 3.5 discover のテストを更新（project フィルタリング + `--include-unknown` の検証）

## 4. evolve の project 伝播

- [x] 4.1 evolve.py: `--project-dir` を discover の `run_discover()` に `project_root` として伝播
- [x] 4.2 evolve のスキルプロンプトで `--project-dir` を discover 呼び出しに渡していることを確認

## 5. audit の DuckDB 対応

- [x] 5.1 audit.py: usage 集計を telemetry_query.py 経由に書き換え。`project_root` 指定時はプロジェクトスコープで集計
- [x] 5.2 audit のテストを更新（DuckDB 経由 + project フィルタリングの検証）

## 6. 依存管理・ドキュメント

- [x] 6.1 `scripts/requirements.txt` を作成し `duckdb` を追加（read 側のみ。hook の requirements には追加しない）
- [x] 6.2 全テスト実行で既存テストが壊れていないことを確認
