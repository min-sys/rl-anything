"""DuckDB ベースのテレメトリクエリ層。

JSONL ファイルを DuckDB の read_json_auto() で直接 SQL クエリする。
DuckDB 未インストール時は load_jsonl() + Python フィルタにフォールバック。
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path.home() / ".claude" / "rl-anything"

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


def _warn_no_duckdb() -> None:
    print(
        "[rl-anything] duckdb not installed. Falling back to Python JSONL parser. "
        "Install with: pip install duckdb",
        file=sys.stderr,
    )


def _load_jsonl(filepath: Path) -> List[Dict[str, Any]]:
    """JSONL ファイルを Python で読み込む（フォールバック用）。"""
    if not filepath.exists():
        return []
    records = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _filter_by_project(
    records: List[Dict[str, Any]],
    project: Optional[str],
    include_unknown: bool = False,
) -> List[Dict[str, Any]]:
    """Python でプロジェクトフィルタリングを適用する（フォールバック用）。"""
    if project is None:
        return records
    result = []
    for rec in records:
        rec_project = rec.get("project")
        if rec_project == project:
            result.append(rec)
        elif include_unknown and rec_project is None:
            result.append(rec)
    return result


def query_usage(
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    usage_file: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """usage.jsonl をクエリして結果を返す。

    Args:
        project: フィルタするプロジェクト名。None の場合は全レコード。
        include_unknown: True の場合、project が null のレコードも含める。
        usage_file: usage.jsonl のパス（テスト用）。
    """
    filepath = usage_file or (DATA_DIR / "usage.jsonl")
    if not filepath.exists():
        return []

    if HAS_DUCKDB:
        return _duckdb_query_file(filepath, project=project, include_unknown=include_unknown)

    _warn_no_duckdb()
    records = _load_jsonl(filepath)
    return _filter_by_project(records, project, include_unknown)


def query_errors(
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    errors_file: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """errors.jsonl をクエリして結果を返す。"""
    filepath = errors_file or (DATA_DIR / "errors.jsonl")
    if not filepath.exists():
        return []

    if HAS_DUCKDB:
        return _duckdb_query_file(filepath, project=project, include_unknown=include_unknown)

    _warn_no_duckdb()
    records = _load_jsonl(filepath)
    return _filter_by_project(records, project, include_unknown)


def query_skill_counts(
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    min_count: int = 1,
    usage_file: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """スキル別の使用回数を集計して返す。

    Returns:
        [{"skill_name": str, "count": int}, ...]
    """
    filepath = usage_file or (DATA_DIR / "usage.jsonl")
    if not filepath.exists():
        return []

    if HAS_DUCKDB:
        return _duckdb_skill_counts(filepath, project=project, include_unknown=include_unknown, min_count=min_count)

    _warn_no_duckdb()
    records = _load_jsonl(filepath)
    filtered = _filter_by_project(records, project, include_unknown)
    counts: Dict[str, int] = {}
    for rec in filtered:
        skill = rec.get("skill_name", "")
        if skill:
            counts[skill] = counts.get(skill, 0) + 1
    return [
        {"skill_name": skill, "count": count}
        for skill, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if count >= min_count
    ]


def query_sessions(
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    sessions_file: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """sessions.jsonl をクエリして結果を返す。

    Args:
        project: フィルタするプロジェクト名。None の場合は全レコード。
        include_unknown: True の場合、project が null のレコードも含める。
        sessions_file: sessions.jsonl のパス（テスト用）。
    """
    filepath = sessions_file or (DATA_DIR / "sessions.jsonl")
    if not filepath.exists():
        return []

    if HAS_DUCKDB:
        return _duckdb_query_file(filepath, project=project, include_unknown=include_unknown)

    _warn_no_duckdb()
    records = _load_jsonl(filepath)
    return _filter_by_project(records, project, include_unknown)


def _duckdb_query_file(
    filepath: Path,
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
) -> List[Dict[str, Any]]:
    """DuckDB で JSONL ファイルをクエリする。

    project カラムが存在しない既存データとの後方互換性を保つため、
    project フィルタ指定時はカラム存在チェックを行う。
    """
    conn = duckdb.connect()
    try:
        read_expr = f"read_json_auto('{filepath}', ignore_errors=true)"

        # project フィルタが不要な場合はそのままクエリ
        if project is None:
            cursor = conn.execute(f"SELECT * FROM {read_expr}")
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

        # project カラムの存在チェック
        cols_cursor = conn.execute(f"SELECT column_name FROM (DESCRIBE SELECT * FROM {read_expr})")
        col_names = {row[0] for row in cols_cursor.fetchall()}

        if "project" not in col_names:
            # project カラムがない → フィルタ時は空リスト（全てが unknown 扱い）
            if include_unknown:
                cursor = conn.execute(f"SELECT * FROM {read_expr}")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            return []

        # project カラムありの場合は通常のフィルタ
        params: Dict[str, Any] = {"project": project}
        if include_unknown:
            where_sql = " WHERE (project = $project OR project IS NULL)"
        else:
            where_sql = " WHERE project = $project"

        cursor = conn.execute(f"SELECT * FROM {read_expr}{where_sql}", params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def _duckdb_skill_counts(
    filepath: Path,
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    min_count: int = 1,
) -> List[Dict[str, Any]]:
    """DuckDB でスキル別カウントを集計する。"""
    conn = duckdb.connect()
    try:
        read_expr = f"read_json_auto('{filepath}', ignore_errors=true)"
        where_sql = ""
        params: Dict[str, Any] = {}

        if project is not None:
            # project カラム存在チェック
            cols_cursor = conn.execute(f"SELECT column_name FROM (DESCRIBE SELECT * FROM {read_expr})")
            col_names = {row[0] for row in cols_cursor.fetchall()}

            if "project" not in col_names:
                if not include_unknown:
                    return []
                # include_unknown の場合は全レコード対象
            else:
                params["project"] = project
                if include_unknown:
                    where_sql = " WHERE (project = $project OR project IS NULL)"
                else:
                    where_sql = " WHERE project = $project"

        sql = (
            f"SELECT skill_name, COUNT(*) as count "
            f"FROM {read_expr}{where_sql} "
            f"GROUP BY skill_name HAVING COUNT(*) >= {min_count} "
            f"ORDER BY count DESC"
        )

        result = conn.execute(sql, params).fetchall()
        return [{"skill_name": row[0], "count": row[1]} for row in result]
    finally:
        conn.close()
