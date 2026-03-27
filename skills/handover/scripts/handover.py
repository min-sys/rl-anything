#!/usr/bin/env python3
"""handover — セッション作業状態の収集。

git + テレメトリから handover ノート用のデータを収集する。
LLM 呼び出しなし。SKILL.md が LLM にノート生成を指示する。
"""
import json
import re
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


_GH_TIMEOUT_SECONDS = 10


def is_github_repo(*, cwd: str | None = None) -> bool:
    """origin リモートが GitHub かどうかを判定する。"""
    url = _run_git(["remote", "get-url", "origin"], cwd=cwd).strip()
    return "github.com" in url


def format_issue_title(data: dict) -> str:
    """Issue のタイトルを生成する。"""
    ts = data.get("timestamp", "")
    date_part = ts[:10] if len(ts) >= 10 else "unknown"
    branch = data.get("work_context", {}).get("git_branch", "")
    if branch:
        return f"Handover: {branch} ({date_part})"
    return f"Handover: {date_part}"


def format_issue_body(data: dict) -> str:
    """Issue のボディを生成する（Context セクションのみ自動埋め、残りは LLM が埋める）。"""
    wc = data.get("work_context", {})
    branch = wc.get("git_branch", "") or "(none)"
    commits = "\n".join(wc.get("recent_commits", [])) or "(none)"
    uncommitted = "\n".join(wc.get("uncommitted_files", [])) or "(none)"
    skills = ", ".join(s.get("skill", "") for s in data.get("skills_used", [])) or "(none)"
    corrections = json.dumps(data.get("corrections", []), ensure_ascii=False) if data.get("corrections") else "(none)"

    return f"""\
## Decisions
<!-- LLM: 会話コンテキストから決定事項とその理由を記入 -->

## Discarded Alternatives
<!-- LLM: 検討したが捨てた選択肢とその理由を記入。なければ「なし」 -->

## Deploy State
<!-- LLM: 会話コンテキストからデプロイ状態を記入 -->

## Next Actions
<!-- LLM: 次にやるべきことを優先順付きで記入 -->

## Context (auto)
branch: {branch}
commits:
{commits}
uncommitted:
{uncommitted}
skills: {skills}
corrections: {corrections}
"""


def create_issue(title: str, body: str, labels: list[str] | None = None) -> str | None:
    """gh issue create で Issue を作成し、URL を返す。失敗時は None。"""
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    if labels:
        for label in labels:
            cmd.extend(["--label", label])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_GH_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _run_git(args: list[str], *, cwd: str | None = None) -> str:
    """git コマンドを実行し stdout を返す。失敗時は空文字列。"""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            cwd=cwd,
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


def _load_checkpoint() -> dict | None:
    """checkpoint.json を読み込む。存在しないか壊れている場合は None。"""
    checkpoint_file = DATA_DIR / "checkpoint.json"
    if not checkpoint_file.exists():
        return None
    try:
        return json.loads(checkpoint_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _collect_work_context_from_git(*, project_dir: str | None = None) -> dict:
    """git から作業コンテキストを収集する（checkpoint がない場合のフォールバック）。"""
    context: dict = {
        "recent_commits": [],
        "uncommitted_files": [],
        "git_branch": "",
    }

    branch_out = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir)
    context["git_branch"] = branch_out.strip()

    log_out = _run_git(["log", "--oneline", f"-{_MAX_COMMITS}"], cwd=project_dir)
    if log_out:
        context["recent_commits"] = [
            line for line in log_out.strip().splitlines() if line.strip()
        ]

    status_out = _run_git(["status", "--short"], cwd=project_dir)
    if status_out:
        context["uncommitted_files"] = [
            line.strip() for line in status_out.strip().splitlines() if line.strip()
        ]

    return context


def collect_handover_data(project_dir: str) -> dict:
    """checkpoint + テレメトリからハンドオーバー用データを収集する。LLM 不使用。

    checkpoint.json があればそこから work_context/corrections を取得（git 再呼び出し不要）。
    なければ git にフォールバックする。
    """
    checkpoint = _load_checkpoint()

    # work_context: checkpoint 優先、なければ git フォールバック
    if checkpoint and checkpoint.get("work_context"):
        work_context = checkpoint["work_context"]
    else:
        work_context = _collect_work_context_from_git(project_dir=project_dir)

    # corrections: checkpoint 優先、なければ corrections.jsonl フォールバック
    if checkpoint and checkpoint.get("corrections_snapshot"):
        corrections = checkpoint["corrections_snapshot"][-10:]
    else:
        corrections = _load_session_records(DATA_DIR / "corrections.jsonl")[-10:]

    # usage.jsonl — 当セッションのスキル使用
    usage_records = _load_session_records(DATA_DIR / "usage.jsonl")
    skills_used = [
        {"skill": r.get("skill_name", ""), "timestamp": r.get("timestamp", "")}
        for r in usage_records
        if r.get("skill_name")
    ][-20:]

    return {
        "project_dir": project_dir,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "work_context": work_context,
        "skills_used": skills_used,
        "corrections": corrections,
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


def extract_section(content: str, section_name: str) -> str:
    """Markdown の ## セクションを名前で抽出する。見つからなければ空文字列。"""
    pattern = rf"^## {re.escape(section_name)}\s*\n"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    # 次の ## ヘッダーまたは末尾まで
    next_header = re.search(r"^## ", content[start:], re.MULTILINE)
    if next_header:
        body = content[start : start + next_header.start()]
    else:
        body = content[start:]
    return body.strip()


def extract_deploy_state(project_dir: str, stale_hours: float = STALE_HOURS) -> str | None:
    """最新 handover から Deploy State セクションを抽出する。なければ None。"""
    content = latest_handover(project_dir, stale_hours=stale_hours)
    if content is None:
        return None
    section = extract_section(content, "Deploy State")
    return section if section else None


def main() -> None:
    """CLI エントリポイント。"""
    import argparse

    parser = argparse.ArgumentParser(description="Collect handover data")
    parser.add_argument("--project-dir", default=".", help="Project directory")
    parser.add_argument("--list", action="store_true", help="List existing handovers")
    parser.add_argument("--latest", action="store_true", help="Show latest handover")
    parser.add_argument("--deploy-state", action="store_true", help="Extract deploy state from latest handover")
    parser.add_argument("--issue", action="store_true", help="Output issue-ready JSON (title + body)")
    args = parser.parse_args()

    project_dir = str(Path(args.project_dir).resolve())

    if args.deploy_state:
        state = extract_deploy_state(project_dir)
        if state:
            print(state)
        else:
            print(json.dumps({"status": "no_deploy_state"}, ensure_ascii=False))
        return

    if args.issue:
        data = collect_handover_data(project_dir)
        issue_data = {
            "title": format_issue_title(data),
            "body": format_issue_body(data),
            "is_github": is_github_repo(cwd=project_dir),
            "data": data,
        }
        print(json.dumps(issue_data, ensure_ascii=False, indent=2))
        return

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
