"""DuckDB ベースのテレメトリクエリ層。

JSONL ファイルを DuckDB の read_json_auto() で直接 SQL クエリする。
DuckDB 未インストール時は load_jsonl() + Python フィルタにフォールバック。
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
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


def _filter_by_time(
    records: List[Dict[str, Any]],
    since: Optional[str],
    until: Optional[str],
    timestamp_field: str = "timestamp",
) -> List[Dict[str, Any]]:
    """Python で時間範囲フィルタリングを適用する（フォールバック用）。"""
    if since is None and until is None:
        return records
    result = []
    for rec in records:
        ts = rec.get(timestamp_field, "")
        if not ts:
            continue
        if since and ts < since:
            continue
        if until and ts >= until:
            continue
        result.append(rec)
    return result


def query_usage(
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    usage_file: Optional[Path] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """usage.jsonl をクエリして結果を返す。

    Args:
        project: フィルタするプロジェクト名。None の場合は全レコード。
        include_unknown: True の場合、project が null のレコードも含める。
        usage_file: usage.jsonl のパス（テスト用）。
        since: ISO 8601 文字列。この時刻以降のレコードのみ返す。
        until: ISO 8601 文字列。この時刻より前のレコードのみ返す。
    """
    filepath = usage_file or (DATA_DIR / "usage.jsonl")
    if not filepath.exists():
        return []

    if HAS_DUCKDB:
        return _duckdb_query_file(filepath, project=project, include_unknown=include_unknown, since=since, until=until)

    _warn_no_duckdb()
    records = _load_jsonl(filepath)
    records = _filter_by_project(records, project, include_unknown)
    return _filter_by_time(records, since, until)


def query_errors(
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    errors_file: Optional[Path] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """errors.jsonl をクエリして結果を返す。"""
    filepath = errors_file or (DATA_DIR / "errors.jsonl")
    if not filepath.exists():
        return []

    if HAS_DUCKDB:
        return _duckdb_query_file(filepath, project=project, include_unknown=include_unknown, since=since, until=until)

    _warn_no_duckdb()
    records = _load_jsonl(filepath)
    records = _filter_by_project(records, project, include_unknown)
    return _filter_by_time(records, since, until)


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
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """sessions.jsonl をクエリして結果を返す。

    Args:
        project: フィルタするプロジェクト名。None の場合は全レコード。
        include_unknown: True の場合、project が null のレコードも含める。
        sessions_file: sessions.jsonl のパス（テスト用）。
        since: ISO 8601 文字列。この時刻以降のレコードのみ返す。
        until: ISO 8601 文字列。この時刻より前のレコードのみ返す。
    """
    filepath = sessions_file or (DATA_DIR / "sessions.jsonl")
    if not filepath.exists():
        return []

    if HAS_DUCKDB:
        return _duckdb_query_file(filepath, project=project, include_unknown=include_unknown, since=since, until=until)

    _warn_no_duckdb()
    records = _load_jsonl(filepath)
    records = _filter_by_project(records, project, include_unknown)
    return _filter_by_time(records, since, until)


def _build_time_where(
    since: Optional[str], until: Optional[str], params: Dict[str, Any],
) -> str:
    """since/until の WHERE 句断片を生成する。"""
    clauses = []
    if since:
        params["since"] = since
        clauses.append("timestamp >= $since")
    if until:
        params["until"] = until
        clauses.append("timestamp < $until")
    return " AND ".join(clauses)


def _duckdb_query_file(
    filepath: Path,
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """DuckDB で JSONL ファイルをクエリする。

    project カラムが存在しない既存データとの後方互換性を保つため、
    project フィルタ指定時はカラム存在チェックを行う。
    """
    conn = duckdb.connect()
    try:
        read_expr = f"read_json_auto('{filepath}', ignore_errors=true)"
        params: Dict[str, Any] = {}
        where_parts: List[str] = []

        # project フィルタ
        if project is not None:
            cols_cursor = conn.execute(f"SELECT column_name FROM (DESCRIBE SELECT * FROM {read_expr})")
            col_names = {row[0] for row in cols_cursor.fetchall()}

            if "project" not in col_names:
                if not include_unknown:
                    return []
                # include_unknown の場合は全レコード対象（project フィルタなし）
            else:
                params["project"] = project
                if include_unknown:
                    where_parts.append("(project = $project OR project IS NULL)")
                else:
                    where_parts.append("project = $project")

        # 時間範囲フィルタ
        time_clause = _build_time_where(since, until, params)
        if time_clause:
            where_parts.append(time_clause)

        where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

        cursor = conn.execute(f"SELECT * FROM {read_expr}{where_sql}", params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def query_corrections(
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    corrections_file: Optional[Path] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """corrections.jsonl をクエリして結果を返す。

    corrections.jsonl は project_path（フルパス）を使用しており、
    project パラメータと照合するため末尾ディレクトリ名を抽出して比較する。
    """
    filepath = corrections_file or (DATA_DIR / "corrections.jsonl")
    if not filepath.exists():
        return []

    if HAS_DUCKDB:
        return _duckdb_query_corrections(filepath, project=project, include_unknown=include_unknown, since=since, until=until)

    _warn_no_duckdb()
    records = _load_jsonl(filepath)
    records = _filter_corrections_by_project(records, project, include_unknown)
    return _filter_by_time(records, since, until)


def _filter_corrections_by_project(
    records: List[Dict[str, Any]],
    project: Optional[str],
    include_unknown: bool = False,
) -> List[Dict[str, Any]]:
    """corrections の project_path から末尾名を抽出してフィルタする。"""
    if project is None:
        return records
    result = []
    for rec in records:
        project_path = rec.get("project_path", "")
        if project_path:
            tail = project_path.rstrip("/").rsplit("/", 1)[-1] if "/" in project_path else project_path
            # projects ディレクトリパスの場合: -Users-xxx-project-name → project-name
            if tail.startswith("-"):
                tail = tail.rsplit("-", 1)[-1] if "-" in tail[1:] else tail
            if tail == project:
                result.append(rec)
                continue
        if include_unknown and not project_path:
            result.append(rec)
    return result


def _duckdb_query_corrections(
    filepath: Path,
    *,
    project: Optional[str] = None,
    include_unknown: bool = False,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """DuckDB で corrections.jsonl をクエリする。project_path からの末尾名抽出でフィルタ。"""
    conn = duckdb.connect()
    try:
        read_expr = f"read_json_auto('{filepath}', ignore_errors=true)"
        params: Dict[str, Any] = {}
        where_parts: List[str] = []

        if project is not None:
            params["project"] = project
            if include_unknown:
                where_parts.append(
                    "(string_split(project_path, '/')[-1] = $project OR project_path IS NULL)"
                )
            else:
                where_parts.append("string_split(project_path, '/')[-1] = $project")

        time_clause = _build_time_where(since, until, params)
        if time_clause:
            where_parts.append(time_clause)

        where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
        cursor = conn.execute(f"SELECT * FROM {read_expr}{where_sql}", params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def query_workflows(
    *,
    workflows_file: Optional[Path] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """workflows.jsonl をクエリして結果を返す。

    Phase 1 では project フィルタなし（workflows.jsonl に project フィールドがないため）。
    時間範囲フィルタは started_at フィールドで適用する。
    """
    filepath = workflows_file or (DATA_DIR / "workflows.jsonl")
    if not filepath.exists():
        return []

    if HAS_DUCKDB:
        return _duckdb_query_workflows(filepath, since=since, until=until)

    _warn_no_duckdb()
    records = _load_jsonl(filepath)
    return _filter_by_time(records, since, until, timestamp_field="started_at")


def _duckdb_query_workflows(
    filepath: Path,
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """DuckDB で workflows.jsonl をクエリする。"""
    conn = duckdb.connect()
    try:
        read_expr = f"read_json_auto('{filepath}', ignore_errors=true)"
        params: Dict[str, Any] = {}
        where_parts: List[str] = []

        if since:
            params["since"] = since
            where_parts.append("started_at >= $since")
        if until:
            params["until"] = until
            where_parts.append("started_at < $until")

        where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
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


# ---------------------------------------------------------------------------
# query_usage_by_skill_session
# ---------------------------------------------------------------------------

TRACE_WINDOW_MINUTES = 5


def query_usage_by_skill_session(
    skill_name: str,
    *,
    project: Optional[str] = None,
    usage_file: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """スキル単位でセッションごとのツール使用統計を返す。

    1. usage.jsonl から全レコードを取得
    2. Skill ツール呼び出し（skill_name フィールドあり）を検出
    3. 指定 skill_name のレコードを session_id でグループ化
    4. 各グループ内で、Skill 発火後〜min(次のSkill発火, TRACE_WINDOW_MINUTES分後) の
       ツール呼び出しを集計
    5. 返り値: [{"session_id": str, "tool_calls": int, "read_edit_cycles": int,
                "errors": int, "duration_seconds": float}, ...]
    """
    filepath = usage_file or (DATA_DIR / "usage.jsonl")
    if not filepath.exists():
        return []

    # DuckDB / Python フォールバック共通で全レコード取得してから Python で集計
    # （ウィンドウ計算が複雑なため Python で統一）
    if HAS_DUCKDB:
        records = _duckdb_query_file(filepath, project=project)
    else:
        records = _load_jsonl(filepath)
        records = _filter_by_project(records, project)

    return _aggregate_skill_sessions(records, skill_name)


def _parse_ts(ts_str: str) -> Optional[datetime]:
    """ISO 8601 タイムスタンプ文字列を datetime に変換する。"""
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _aggregate_skill_sessions(
    records: List[Dict[str, Any]], skill_name: str,
) -> List[Dict[str, Any]]:
    """レコードリストからスキル単位のセッション統計を集計する。"""
    by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rec in records:
        sid = rec.get("session_id")
        if sid:
            by_session[sid].append(rec)

    results = []
    window_seconds = TRACE_WINDOW_MINUTES * 60

    for sid, session_records in by_session.items():
        sorted_recs = sorted(session_records, key=lambda r: r.get("timestamp", ""))

        skill_fires = []
        for i, rec in enumerate(sorted_recs):
            if rec.get("tool_name") == "Skill" and rec.get("skill_name") == skill_name:
                skill_fires.append((i, rec))

        if not skill_fires:
            continue

        for fire_idx, (pos, fire_rec) in enumerate(skill_fires):
            fire_ts = _parse_ts(fire_rec.get("timestamp", ""))
            if fire_ts is None:
                continue

            next_skill_ts = None
            for j in range(pos + 1, len(sorted_recs)):
                if sorted_recs[j].get("tool_name") == "Skill":
                    next_skill_ts = _parse_ts(sorted_recs[j].get("timestamp", ""))
                    break

            window_end_ts = fire_ts.timestamp() + window_seconds
            if next_skill_ts is not None:
                window_end_ts = min(window_end_ts, next_skill_ts.timestamp())

            tool_calls = 0
            errors = 0
            read_edit_cycles = 0
            last_was_read = False
            last_ts_str = fire_rec.get("timestamp", "")

            for j in range(pos + 1, len(sorted_recs)):
                rec = sorted_recs[j]
                rec_ts = _parse_ts(rec.get("timestamp", ""))
                if rec_ts is None:
                    continue
                if rec_ts.timestamp() >= window_end_ts:
                    break

                tool_calls += 1
                last_ts_str = rec.get("timestamp", last_ts_str)

                if rec.get("error"):
                    errors += 1

                tool = rec.get("tool_name", "")
                if tool == "Read":
                    last_was_read = True
                elif tool == "Edit" and last_was_read:
                    read_edit_cycles += 1
                    last_was_read = False
                else:
                    last_was_read = False

            last_rec_ts = _parse_ts(last_ts_str)
            duration = 0.0
            if last_rec_ts and fire_ts:
                duration = max(0.0, last_rec_ts.timestamp() - fire_ts.timestamp())

            results.append({
                "session_id": sid,
                "tool_calls": tool_calls,
                "read_edit_cycles": read_edit_cycles,
                "errors": errors,
                "duration_seconds": duration,
            })

    return results
