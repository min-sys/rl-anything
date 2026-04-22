"""rl-anything fleet — 全 PJ 横断のメンテナンス拠点（Phase 1: status のみ）。

設計: `matsukaze-takashi-main-design-20260422-140954.md` Phase 1 節。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

STATUS_ENABLED = "ENABLED"
STATUS_STALE = "STALE"
STATUS_NOT_ENABLED = "NOT_ENABLED"

AUDIT_OK = "OK"
AUDIT_TIMEOUT = "TIMEOUT"
AUDIT_ERROR = "ERROR"

from rl_common import DATA_DIR as _DEFAULT_DATA_DIR  # honors CLAUDE_PLUGIN_DATA

_DEFAULT_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
_DEFAULT_AUTO_MEMORY_ROOT = Path.home() / ".claude" / "projects"
_DEFAULT_MATSUKAZE_ROOT = Path.home() / "matsukaze-utils"
_DEFAULT_RL_AUDIT_BIN = Path(__file__).resolve().parent.parent.parent / "bin" / "rl-audit"
_PLUGIN_KEY_PREFIX = "rl-anything@"
_SETTINGS_RETRY_SLEEP_SEC = 0.1
_DEFAULT_TIMEOUT_SEC = 10.0
_DEFAULT_MAX_WORKERS = 2
_KILL_GRACE_SEC = 2.0


def _current_data_dir() -> Path:
    """CLAUDE_PLUGIN_DATA を呼び出し時に再参照して DATA_DIR を返す。

    `rl_common._DEFAULT_DATA_DIR` は import-time capture のため env 後追い変更を
    反映できない。fleet-runs 書き出しなど呼び出しタイミングが重要な処理では
    こちらを使う。
    """
    env_val = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    return Path(env_val) if env_val else Path.home() / ".claude" / "rl-anything"


@dataclass
class AuditResult:
    """PJ audit の結果（TIMEOUT/ERROR 区別付き）。"""

    status: str  # AUDIT_OK | AUDIT_TIMEOUT | AUDIT_ERROR
    env_score: float | None = None
    phase: str | None = None
    growth_level: int | None = None
    latest_audit: datetime | None = None
    message: str = ""


@dataclass
class FleetRow:
    """fleet status 表示 1 行分。"""

    pj_name: str
    status: str  # STATUS_ENABLED / STATUS_STALE / STATUS_NOT_ENABLED
    env_score: float | None = None
    growth_level: int | None = None
    phase: str | None = None
    latest_audit: datetime | None = None
    audit_status: str = AUDIT_OK
    message: str = ""


def _pj_safe_name(pj_path: Path) -> str:
    """growth-state cache 命名に使う safe_name（growth_engine._cache_path と同じルール）。"""
    name = pj_path.resolve().name or "unknown"
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


def resolve_auto_memory_dir(pj_path: Path) -> Path:
    """PJ パスから Claude Code auto-memory ディレクトリを逆引きする。

    命名規則: `~/.claude/projects/-<絶対パスを `/` → `-` に置換>`

    例: `/Users/foo/bar` → `~/.claude/projects/-Users-foo-bar`

    相対パスや trailing slash は `Path.resolve()` で正規化してから変換する。
    特殊文字 (`-` を含むディレクトリ名等) は Phase 3 で扱う (本実装は非対応)。
    """
    absolute = pj_path.resolve()
    slug = str(absolute).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug


def enumerate_projects(root: Path) -> list[Path]:
    """PJ 候補を列挙する。

    `root` 直下の子ディレクトリで、以下いずれかを持つものを PJ とみなす:
    - `.claude/` ディレクトリ
    - `CLAUDE.md` ファイル

    除外ルール:
    - ドットで始まるディレクトリ (`.worktrees/` 等) は開発メタデータのため
    - シンボリックリンクは任意パスへの audit trampoline を防ぐため

    `root` 自体が存在しない場合は空リストを返す。
    返り値はディレクトリ名でソート。
    """
    if not root.is_dir():
        return []
    projects: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith(".") or child.is_symlink():
            continue
        if (child / ".claude").is_dir() or (child / "CLAUDE.md").is_file():
            projects.append(child)
    return projects


def _load_settings_with_retry(settings_path: Path) -> dict | None:
    """settings.json を読んで dict を返す。parse 失敗時は 100ms 後に 1 回 retry。"""
    for attempt in range(2):
        if not settings_path.is_file():
            return None
        try:
            return json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            if attempt == 0:
                time.sleep(_SETTINGS_RETRY_SLEEP_SEC)
                continue
            return None


def _is_plugin_enabled(settings: dict) -> bool:
    """settings.enabledPlugins に rl-anything@* が truthy で含まれるか。"""
    enabled = settings.get("enabledPlugins") or {}
    if not isinstance(enabled, dict):
        return False
    for key, value in enabled.items():
        if key.startswith(_PLUGIN_KEY_PREFIX) and bool(value):
            return True
    return False


def _latest_activity(auto_memory_dir: Path) -> float | None:
    """auto-memory ディレクトリ内の `.jsonl` の最新 mtime を返す。無ければ None。"""
    if not auto_memory_dir.is_dir():
        return None
    latest: float | None = None
    for f in auto_memory_dir.glob("*.jsonl"):
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        if latest is None or mtime > latest:
            latest = mtime
    return latest


def classify_project(
    pj_path: Path,
    settings_path: Path | None = None,
    auto_memory_root: Path | None = None,
    stale_days: int = 30,
    now: datetime | None = None,
) -> str:
    """PJ の rl-anything 導入状況を 3 値で判定する。

    判定表 (設計 Phase 1 ハイブリッド):
    - `rl-anything@*` 有効 + auto-memory の直近 `.jsonl` が `stale_days` 以内 → ENABLED
    - `rl-anything@*` 有効 + auto-memory 古い or 欠損 → STALE
    - `rl-anything@*` 無効 or settings 欠損 / 破損（retry も失敗） → NOT_ENABLED

    `settings_path` が破損していた場合は 100ms sleep 後に 1 回だけ retry する。
    """
    settings_path = settings_path or _DEFAULT_SETTINGS_PATH
    auto_memory_root = auto_memory_root or _DEFAULT_AUTO_MEMORY_ROOT
    now = now or datetime.now(timezone.utc)

    settings = _load_settings_with_retry(settings_path)
    if settings is None or not _is_plugin_enabled(settings):
        return STATUS_NOT_ENABLED

    slug = str(pj_path.resolve()).replace("/", "-")
    auto_memory_dir = auto_memory_root / slug

    latest = _latest_activity(auto_memory_dir)
    if latest is None:
        return STATUS_STALE
    age_sec = now.timestamp() - latest
    if age_sec > stale_days * 86400:
        return STATUS_STALE
    return STATUS_ENABLED


def run_audit_subprocess(
    pj_path: Path,
    timeout: float = 10.0,
    data_dir: Path | None = None,
    rl_audit_bin: Path | None = None,
) -> AuditResult:
    """PJ の audit を subprocess で実行し growth-state から結果を読み取る。

    - `bin/rl-audit --growth --skip-rescore -- <pj_path>` を実行（副作用: growth-state 更新）
    - `--` 区切りで PJ パスに leading `-` があっても argparse を誤動作させない
    - `data_dir` 指定時は `CLAUDE_PLUGIN_DATA=<data_dir>` を env に設定
    - subprocess は `start_new_session=True` で別プロセスグループに隔離し、timeout 時は
      `os.killpg` で子孫まで確実に終了させる（孤児化した rl-audit 子孫が growth-state を
      半書き状態で残すことを防ぐ）
    - subprocess timeout / returncode 非ゼロ / growth-state 破損は `AuditResult.status` で区別

    Phase 1 では rl-audit stdout は parse せず growth-state JSON を唯一の真実とする。
    """
    rl_audit_bin = rl_audit_bin or _DEFAULT_RL_AUDIT_BIN
    effective_data_dir = data_dir or _DEFAULT_DATA_DIR
    # flags を positional より前に置き `--` で区切る → PJ 名が `-` で始まっても安全
    cmd = [
        sys.executable, str(rl_audit_bin),
        "--growth", "--skip-rescore",
        "--", str(pj_path),
    ]
    env = os.environ.copy()
    if data_dir is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(data_dir)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,  # 別プロセスグループ → killpg 可能
        )
    except OSError as e:
        return AuditResult(AUDIT_ERROR, message=f"spawn failed: {e}")

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_process_group(proc)
        return AuditResult(AUDIT_TIMEOUT, message=f"timeout after {timeout}s")

    if proc.returncode != 0:
        stderr_tail = (stderr or "").strip().splitlines()
        tail = stderr_tail[-1] if stderr_tail else f"returncode {proc.returncode}"
        return AuditResult(AUDIT_ERROR, message=tail[:200])

    state_path = effective_data_dir / f"growth-state-{_pj_safe_name(pj_path)}.json"
    if not state_path.is_file():
        return AuditResult(AUDIT_OK, message="no growth-state cache")
    try:
        state = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return AuditResult(AUDIT_ERROR, message=f"state parse: {e}")

    env_score = state.get("progress")
    phase = state.get("phase")
    growth_level = _safe_compute_level(env_score)
    latest_audit = _parse_iso(state.get("updated_at"))
    return AuditResult(
        status=AUDIT_OK,
        env_score=env_score if isinstance(env_score, (int, float)) else None,
        phase=phase if isinstance(phase, str) else None,
        growth_level=growth_level,
        latest_audit=latest_audit,
    )


def _terminate_process_group(proc: subprocess.Popen) -> None:
    """subprocess のプロセスグループを SIGTERM→SIGKILL で順次停止させる。

    `start_new_session=True` で起動した子プロセスは別セッション/PGID を持つので、
    `os.killpg` で子孫まとめて落とせる。
    """
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = proc.pid
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except OSError:
            break
        try:
            proc.wait(timeout=_KILL_GRACE_SEC)
            return
        except subprocess.TimeoutExpired:
            continue


def _safe_compute_level(env_score: object) -> int | None:
    if not isinstance(env_score, (int, float)):
        return None
    try:
        from growth_level import compute_level
    except ImportError:
        return None
    return compute_level(float(env_score)).level


_TABLE_HEADERS = ["PJ", "STATUS", "SCORE", "LV", "PHASE", "LAST_AUDIT", "AUDIT"]


def _format_relative(dt: datetime, now: datetime) -> str:
    """`1h ago` / `3d ago` のような短い相対時刻表記。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "future"
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    if days >= 1:
        return f"{days}d ago"
    if hours >= 1:
        return f"{hours}h ago"
    if minutes >= 1:
        return f"{minutes}m ago"
    return "just now"


def _format_cell_score(row: FleetRow) -> str:
    if row.status != STATUS_ENABLED:
        return "N/A"
    if row.env_score is None:
        return "—"
    return f"{row.env_score:.2f}"


def _format_cell_level(row: FleetRow) -> str:
    if row.growth_level is None:
        return "—"
    return f"Lv.{row.growth_level}"


def _format_cell_phase(row: FleetRow) -> str:
    return row.phase or "—"


def _format_cell_last_audit(row: FleetRow, now: datetime) -> str:
    if row.latest_audit is None:
        return "—"
    return _format_relative(row.latest_audit, now)


def _format_cell_audit(row: FleetRow) -> str:
    if row.status == STATUS_NOT_ENABLED:
        return "—"
    return row.audit_status


def format_status_table(rows: list[FleetRow], now: datetime | None = None) -> str:
    """fleet status 行を整列済みテキストテーブルに整形する。

    列: PJ / STATUS / SCORE / LV / PHASE / LAST_AUDIT / AUDIT
    列幅は各列の最大値に合わせ、各セルは左詰め（英数字のみ想定）。
    """
    now = now or datetime.now(timezone.utc)
    cells: list[list[str]] = [list(_TABLE_HEADERS)]
    for row in rows:
        cells.append([
            row.pj_name,
            row.status,
            _format_cell_score(row),
            _format_cell_level(row),
            _format_cell_phase(row),
            _format_cell_last_audit(row, now),
            _format_cell_audit(row),
        ])
    widths = [max(len(c) for c in col) for col in zip(*cells)]
    lines = []
    for row_cells in cells:
        parts = [row_cells[i].ljust(widths[i]) for i in range(len(widths))]
        lines.append("  ".join(parts).rstrip())
    return "\n".join(lines) + "\n"


def _collect_single(
    pj_path: Path,
    *,
    settings_path: Path,
    auto_memory_root: Path,
    data_dir: Path | None,
    timeout: float,
) -> FleetRow:
    status = classify_project(pj_path, settings_path, auto_memory_root)
    if status != STATUS_ENABLED:
        return FleetRow(pj_name=pj_path.name, status=status)
    audit = run_audit_subprocess(pj_path, timeout=timeout, data_dir=data_dir)
    return FleetRow(
        pj_name=pj_path.name,
        status=status,
        env_score=audit.env_score,
        growth_level=audit.growth_level,
        phase=audit.phase,
        latest_audit=audit.latest_audit,
        audit_status=audit.status,
        message=audit.message,
    )


def _find_duplicate_basenames(projects: list[Path]) -> set[str]:
    """同一 basename を持つ PJ を検出し、重複 basename 集合を返す。

    rl-audit の growth-state cache (`growth-state-<basename>.json`) は basename 単位で
    命名されるため、同じ basename の PJ が複数あると cache が衝突し fleet は誤った
    score を表示する。Phase 1 では該当 PJ を AUDIT_ERROR として surface する。
    Phase 3 の per-PJ CLAUDE_PLUGIN_DATA 分離で根本解決予定。
    """
    seen: dict[str, int] = {}
    for pj in projects:
        seen[pj.name] = seen.get(pj.name, 0) + 1
    return {name for name, count in seen.items() if count > 1}


def collect_fleet_status(
    root: Path | None = None,
    settings_path: Path | None = None,
    auto_memory_root: Path | None = None,
    data_dir: Path | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SEC,
    max_workers: int = _DEFAULT_MAX_WORKERS,
) -> list[FleetRow]:
    """全 PJ の fleet ステータスを並列収集して行リストを返す。

    STATUS_ENABLED の PJ のみ subprocess audit を走らせる（STALE/NOT_ENABLED は
    低コストで判定のみ）。並列度は ThreadPoolExecutor(max_workers)。

    同じ basename の PJ が複数ある場合は growth-state cache が衝突するため、
    該当 PJ を AUDIT_ERROR 扱いにして誤ったスコア表示を防ぐ。
    """
    root = root or _DEFAULT_MATSUKAZE_ROOT
    settings_path = settings_path or _DEFAULT_SETTINGS_PATH
    auto_memory_root = auto_memory_root or _DEFAULT_AUTO_MEMORY_ROOT
    projects = enumerate_projects(root)
    if not projects:
        return []
    dup_basenames = _find_duplicate_basenames(projects)

    def _work(pj: Path) -> FleetRow:
        if pj.name in dup_basenames:
            status = classify_project(pj, settings_path, auto_memory_root)
            return FleetRow(
                pj_name=pj.name,
                status=status,
                audit_status=AUDIT_ERROR,
                message="duplicate basename (cache would collide)",
            )
        return _collect_single(
            pj,
            settings_path=settings_path,
            auto_memory_root=auto_memory_root,
            data_dir=data_dir,
            timeout=timeout,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(_work, projects))


def _serialize_row(row: FleetRow) -> dict:
    d = asdict(row)
    if row.latest_audit is not None:
        d["latest_audit"] = row.latest_audit.isoformat()
    return d


def write_fleet_run(
    rows: list[FleetRow],
    fleet_runs_dir: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """fleet-run を `<dir>/<ts>.jsonl` に追記する。各行は 1 PJ の状態。

    `fleet_runs_dir` 未指定時は呼び出し時点の `CLAUDE_PLUGIN_DATA` を再参照して
    `<data_dir>/fleet-runs/` を使う（import-time capture で stale 化しない）。
    """
    if fleet_runs_dir is None:
        fleet_runs_dir = _current_data_dir() / "fleet-runs"
    now = now or datetime.now(timezone.utc)
    fleet_runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = fleet_runs_dir / f"{stamp}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_serialize_row(row), ensure_ascii=False) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    """`bin/rl-fleet` エントリポイント。"""
    parser = argparse.ArgumentParser(
        prog="rl-fleet",
        description="全 PJ 横断で rl-anything の健康状態を一覧表示する（Phase 1）",
    )
    sub = parser.add_subparsers(dest="command")
    status_p = sub.add_parser("status", help="各 PJ のステータスを表形式で表示（default）")
    for p in (parser, status_p):
        p.add_argument("--root", type=Path, default=None, help="PJ 列挙のルート (default: ~/matsukaze-utils)")
        p.add_argument("--timeout", type=float, default=_DEFAULT_TIMEOUT_SEC, help="PJ 毎の audit タイムアウト秒 (default: 10)")
        p.add_argument("--max-workers", type=int, default=_DEFAULT_MAX_WORKERS, help="並列数 (default: 2)")
        p.add_argument("--no-write", action="store_true", help="fleet-runs/*.jsonl への追記をスキップ")
    args = parser.parse_args(argv)

    rows = collect_fleet_status(
        root=args.root,
        timeout=args.timeout,
        max_workers=args.max_workers,
    )
    print(format_status_table(rows), end="")
    if not args.no_write:
        write_fleet_run(rows)
    return 0


def _parse_iso(ts: object) -> datetime | None:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
