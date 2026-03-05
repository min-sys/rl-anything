## ADDED Requirements

### Requirement: Common query module provides SQL-based JSONL reading
`scripts/lib/telemetry_query.py` モジュールは DuckDB の `read_json_auto()` を使い、usage.jsonl および errors.jsonl を SQL でクエリする関数を提供する MUST。

戻り値は全関数共通で `List[Dict[str, Any]]` 型とする MUST。各 dict のキーは元の JSONL レコードのフィールド名に対応する。集計関数の dict キーは関数ごとに定義する。

DuckDB の `read_json_auto()` 呼び出し時は `ignore_errors=true` オプションを指定し、不正な JSON 行をスキップする MUST。

#### Scenario: Query usage by project
- **WHEN** `query_usage(project="atlas-breeaders")` が呼ばれる
- **THEN** DuckDB SQL で `WHERE project = 'atlas-breeaders'` のフィルタが適用され、該当レコードのみが `List[Dict[str, Any]]` として返される

#### Scenario: Query with aggregation
- **WHEN** `query_skill_counts(project="atlas-breeaders", min_count=5)` が呼ばれる
- **THEN** `GROUP BY skill_name HAVING COUNT(*) >= 5` 相当の集計結果が `List[Dict[str, Any]]`（各 dict は `{"skill_name": str, "count": int}` 構造）として返される

#### Scenario: Audit uses query layer
- **WHEN** audit.py が usage 集計を実行する
- **THEN** `query_usage()` または `query_skill_counts()` を使用して集計する。DuckDB 利用不可時はフォールバック経由で同等の結果を返す

### Requirement: DuckDB is read-side only dependency
DuckDB は discover/audit/analyze（読み込み側）でのみ使用し、observe hook（書き込み側）では使用しない MUST。hook の実行に duckdb パッケージは不要である MUST。

#### Scenario: observe hook without duckdb
- **WHEN** duckdb パッケージが未インストールの環境で observe hook が実行される
- **THEN** hook はエラーなく正常に動作し、JSONL への書き込みが成功する

### Requirement: Graceful fallback when DuckDB unavailable
DuckDB が利用不可の場合、読み込み層は既存の `load_jsonl()` + Python 集計にフォールバックする MUST。エラーメッセージで `pip install duckdb` を案内する SHALL。

#### Scenario: DuckDB not installed
- **WHEN** duckdb パッケージが未インストールの環境で discover が実行される
- **THEN** 既存の JSONL パース方式にフォールバックし、結果が返される。stderr に DuckDB インストールを推奨するメッセージが出力される

### Requirement: Fallback maintains project filtering
DuckDB フォールバック時も、Python 側で `project` フィールドによるフィルタリングを維持する MUST。フォールバックによりクロスプロジェクト汚染が再発してはならない。

#### Scenario: Fallback with project filter
- **WHEN** DuckDB が利用不可で `query_usage(project="atlas-breeaders")` が呼ばれる
- **THEN** フォールバックの `load_jsonl()` + Python フィルタにより、`project == "atlas-breeaders"` のレコードのみが返される。他プロジェクトのレコードは含まれない
