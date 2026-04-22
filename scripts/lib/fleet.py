"""rl-anything fleet — 全 PJ 横断のメンテナンス拠点（Phase 1: status のみ）。

設計: `matsukaze-takashi-main-design-20260422-140954.md` Phase 1 節。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STATUS_ENABLED = "ENABLED"
STATUS_STALE = "STALE"
STATUS_NOT_ENABLED = "NOT_ENABLED"

AUDIT_OK = "OK"
AUDIT_TIMEOUT = "TIMEOUT"
AUDIT_ERROR = "ERROR"

_DEFAULT_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
_DEFAULT_AUTO_MEMORY_ROOT = Path.home() / ".claude" / "projects"
_DEFAULT_DATA_DIR = Path.home() / ".claude" / "rl-anything"
_DEFAULT_RL_AUDIT_BIN = Path(__file__).resolve().parent.parent.parent / "bin" / "rl-audit"
_PLUGIN_KEY_PREFIX = "rl-anything@"
_SETTINGS_RETRY_SLEEP_SEC = 0.1


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


def enumerate_projects(root: Path) -> list[Path]:
    """PJ 候補を列挙する。

    `root` 直下の子ディレクトリで、以下いずれかを持つものを PJ とみなす:
    - `.claude/` ディレクトリ
    - `CLAUDE.md` ファイル

    ドットで始まるディレクトリ (`.worktrees/` 等) は開発メタデータのため除外。
    `root` 自体が存在しない場合は空リストを返す。
    返り値はディレクトリ名でソート。
    """
    if not root.is_dir():
        return []
    projects: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith("."):
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

    - `bin/rl-audit <pj_path> --growth --skip-rescore` を実行（副作用: growth-state 更新）
    - `data_dir` 指定時は `CLAUDE_PLUGIN_DATA=<data_dir>` を env に設定
    - subprocess timeout / returncode 非ゼロ / growth-state 破損は `AuditResult.status` で区別

    Phase 1 では rl-audit stdout は parse せず growth-state JSON を唯一の真実とする。
    """
    rl_audit_bin = rl_audit_bin or _DEFAULT_RL_AUDIT_BIN
    effective_data_dir = data_dir or _DEFAULT_DATA_DIR
    cmd = [sys.executable, str(rl_audit_bin), str(pj_path), "--growth", "--skip-rescore"]
    env = os.environ.copy()
    if data_dir is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(data_dir)

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env
        )
    except subprocess.TimeoutExpired:
        return AuditResult(AUDIT_TIMEOUT, message=f"timeout after {timeout}s")
    except OSError as e:
        return AuditResult(AUDIT_ERROR, message=f"spawn failed: {e}")

    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "").strip().splitlines()
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


def _parse_iso(ts: object) -> datetime | None:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


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
