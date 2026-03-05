## Why

evolve/discover が `~/.claude/rl-anything/usage.jsonl` を全レコード無差別に読み込むため、別プロジェクトのテレメトリが混入し、無関係なスキル候補（例: AWS 未使用 PJ に `aws-deploy` を推薦）が提案される。データ量は増加し続けており（現在 1915 行）、JSONL の全行パースによる分析コードの複雑さも課題。

## What Changes

- observe hook の usage/errors レコードに `project` フィールドを追加（JSONL append は維持）
- discover/audit/analyze の読み込み層に DuckDB を導入し、JSONL を直接 SQL クエリ
- discover の `detect_behavior_patterns()` に project フィルタリングを追加
- errors.jsonl の detect_error_patterns() にも同様の project フィルタリングを追加
- evolve.py から discover への `--project-dir` パススルーを修正

## Capabilities

### New Capabilities
- `project-aware-telemetry`: observe hook が project フィールドを記録し、discover/audit が project 単位でフィルタリングする機能
- `duckdb-query-layer`: JSONL ファイルを DuckDB の `read_json_auto()` で直接 SQL クエリする共通読み込み層

### Modified Capabilities

## Impact

- **hooks/observe.py**: usage/errors レコードに `project` フィールド追加（空文字列は `null` として扱う）
- **hooks/common.py**: `project_name_from_dir()` は既存（変更なし）
- **scripts/lib/telemetry_query.py**: DuckDB 共通クエリ層（新規作成）。discover/audit/analyze の `load_jsonl()` 重複を統合
- **skills/discover/scripts/discover.py**: telemetry_query.py 経由に書き換え、`project_root` フィルタ + `--include-unknown` フラグ追加
- **skills/audit/scripts/audit.py**: telemetry_query.py 経由に書き換え、`project_root` 指定時はプロジェクトスコープで集計
- **skills/evolve/scripts/evolve.py**: `--project-dir` を discover に `project_root` として伝播
- **scripts/requirements.txt**: `duckdb` パッケージ追加（read 側のみ。observe hook は依存なし）
- **既存データ互換**: project フィールドなしのレコードは `project IS NULL` として扱い、フィルタ時はデフォルト除外。`--include-unknown` で含める選択肢あり
