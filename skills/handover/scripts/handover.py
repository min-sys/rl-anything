#!/usr/bin/env python3
"""handover — セッション作業状態の収集。

git + テレメトリから handover ノート用のデータを収集する。
LLM 呼び出しなし。SKILL.md が LLM にノート生成を指示する。
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "hooks"))

from common import DATA_DIR

# Constants
HANDOVER_DIR = ".claude/handovers"
STALE_HOURS = 48.0
COOLDOWN_SECONDS = 3600
_GIT_TIMEOUT_SECONDS = 3
_MAX_COMMITS = 10


def _run_git(args: list[str]) -> str:
    """git コマンドを実行し stdout を返す。失敗時は空文字列。"""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _load_session_records(jsonl_file: Path) -> list[dict]:
    """JSONL ファイルからレコードを読み込む。"""
    if not jsonl_file.exists():
        return []
    records = []
    try:
        for line in jsonl_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return records


def collect_handover_data(project_dir: str) -> dict:
    """git + テレメトリからハンドオーバー用データを収集する。LLM 不使用。"""
    # git status
    status_out = _run_git(["status", "--short"])
    uncommitted = [
        line.strip() for line in status_out.strip().splitlines() if line.strip()
    ] if status_out else []

    # git log
    log_out = _run_git(["log", "--oneline", f"-{_MAX_COMMITS}"])
    commits = [
        line for line in log_out.strip().splitlines() if line.strip()
    ] if log_out else []

    # git diff --stat
    diff_stat = _run_git(["diff", "--stat"]).strip()

    # usage.jsonl — 当セッションのスキル使用
    usage_records = _load_session_records(DATA_DIR / "usage.jsonl")
    skills_used = [
        {"skill": r.get("skill_name", ""), "timestamp": r.get("timestamp", "")}
        for r in usage_records
        if r.get("skill_name")
    ]
    # 直近 20 件に絞る
    skills_used = skills_used[-20:]

    # corrections.jsonl
    corrections = _load_session_records(DATA_DIR / "corrections.jsonl")
    # 直近 10 件に絞る
    corrections = corrections[-10:]

    # checkpoint.json の work_context
    work_context = {}
    checkpoint_file = DATA_DIR / "checkpoint.json"
    if checkpoint_file.exists():
        try:
            cp = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            work_context = cp.get("work_context", {})
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "project_dir": project_dir,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uncommitted_files": uncommitted,
        "recent_commits": commits,
        "diff_stat": diff_stat,
        "skills_used": skills_used,
        "corrections": corrections,
        "work_context": work_context,
    }


def list_handovers(project_dir: str) -> list[dict]:
    """既存の handover ノート一覧を日付降順で返す。"""
    hdir = Path(project_dir) / HANDOVER_DIR
    if not hdir.exists():
        return []
    files = sorted(hdir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [
        {"name": f.name, "path": str(f), "mtime": f.stat().st_mtime}
        for f in files
    ]


def latest_handover(project_dir: str, stale_hours: float = STALE_HOURS) -> str | None:
    """最新の handover ノートの内容を返す。stale_hours 超は None。"""
    entries = list_handovers(project_dir)
    if not entries:
        return None
    latest_file = Path(entries[0]["path"])
    age_hours = (time.time() - latest_file.stat().st_mtime) / 3600
    if age_hours > stale_hours:
        return None
    try:
        return latest_file.read_text(encoding="utf-8")
    except OSError:
        return None


def main() -> None:
    """CLI エントリポイント。"""
    import argparse

    parser = argparse.ArgumentParser(description="Collect handover data")
    parser.add_argument("--project-dir", default=".", help="Project directory")
    parser.add_argument("--list", action="store_true", help="List existing handovers")
    parser.add_argument("--latest", action="store_true", help="Show latest handover")
    args = parser.parse_args()

    project_dir = str(Path(args.project_dir).resolve())

    if args.list:
        entries = list_handovers(project_dir)
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    elif args.latest:
        content = latest_handover(project_dir)
        if content:
            print(content)
        else:
            print(json.dumps({"status": "no_recent_handover"}, ensure_ascii=False))
    else:
        data = collect_handover_data(project_dir)
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
