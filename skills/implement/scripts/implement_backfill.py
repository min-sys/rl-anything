#!/usr/bin/env python3
"""git log からリリース間のコミット群を「実装セッション」として推定し、
implement スキルのテレメトリ（usage.jsonl + growth-journal.jsonl）にバックフィルする。

推定ロジック:
  - chore(release) コミットをセッション境界として使用
  - 境界間の feat/fix/refactor コミットを 1 実装セッションとみなす
  - コミット数 ≒ タスク数、変更ファイル数からモード推定
  - 準拠率は backfill では推定不能なため 1.0 と仮定
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# backfill で推定できない準拠率のデフォルト値
_DEFAULT_CONFORMANCE = 1.0
# parallel 判定の閾値
_PARALLEL_FILE_THRESHOLD = 5
_PARALLEL_COMMIT_THRESHOLD = 5
# release コミットの判定パターン
_RELEASE_RE = re.compile(r"chore\(release\):")
# 除外するコミットタイプ（docs, chore, ci のみのセッションはスキップ）
_IMPL_TYPES = re.compile(r"^(feat|fix|refactor|perf|test)")


def _run_git(args: list[str], cwd: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def parse_git_sessions(repo_dir: str) -> list[dict[str, Any]]:
    """リリースコミット間のコミット群を実装セッションとして抽出."""
    # 全コミットをリリース境界で分割
    log = _run_git(
        ["log", "--oneline", "--reverse", "--first-parent", "HEAD"],
        repo_dir,
    )
    if not log:
        return []

    lines = log.splitlines()

    # リリースコミットの位置を検出
    release_indices: list[int] = []
    for i, line in enumerate(lines):
        parts = line.split(" ", 1)
        if len(parts) == 2 and _RELEASE_RE.search(parts[1]):
            release_indices.append(i)

    if not release_indices:
        return []

    sessions: list[dict[str, Any]] = []

    for idx in range(len(release_indices) - 1):
        start = release_indices[idx]
        end = release_indices[idx + 1]

        # 境界間のコミット（release コミット自体は除外）
        segment = lines[start + 1 : end]
        if not segment:
            continue

        # 実装系コミットがあるかチェック
        impl_commits = []
        for line in segment:
            parts = line.split(" ", 1)
            if len(parts) == 2 and _IMPL_TYPES.match(parts[1]):
                impl_commits.append(parts)

        if not impl_commits:
            continue

        # リリースコミットからバージョンを抽出
        start_hash = lines[start].split(" ", 1)[0]
        end_hash = lines[end].split(" ", 1)[0]
        start_msg = lines[start].split(" ", 1)[1] if len(lines[start].split(" ", 1)) > 1 else ""
        end_msg = lines[end].split(" ", 1)[1] if len(lines[end].split(" ", 1)) > 1 else ""

        version_from = _extract_version(start_msg)
        version_to = _extract_version(end_msg)

        # 変更ファイル数を取得
        diff_stat = _run_git(
            ["diff", "--stat", f"{start_hash}..{end_hash}", "--", ".", ":!CHANGELOG.md", ":!SPEC.md", ":!README.md"],
            repo_dir,
        )
        files_changed = _count_files(diff_stat)

        # タイムスタンプ（最後の実装コミットの日時）
        last_impl_hash = impl_commits[-1][0]
        ts = _run_git(["log", "-1", "--format=%aI", last_impl_hash], repo_dir)

        sessions.append({
            "commits": len(segment),
            "impl_commits": len(impl_commits),
            "files_changed": files_changed,
            "ts": ts or datetime.now(timezone.utc).isoformat(),
            "version_from": version_from,
            "version_to": version_to,
            "hash_from": start_hash,
            "hash_to": end_hash,
        })

    return sessions


def _extract_version(msg: str) -> str:
    m = re.search(r"v(\d+\.\d+\.\d+)", msg)
    return m.group(0) if m else "unknown"


def _count_files(diff_stat: str) -> int:
    if not diff_stat:
        return 0
    # diff --stat の最終行以外の行数 = ファイル数
    lines = [l for l in diff_stat.splitlines() if "|" in l]
    return len(lines)


def estimate_mode(commits: int, files: int) -> str:
    """コミット数と変更ファイル数からモードを推定."""
    if commits >= _PARALLEL_COMMIT_THRESHOLD or files >= _PARALLEL_FILE_THRESHOLD:
        return "parallel"
    return "standard"


def _data_dir() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_DATA", os.path.expanduser("~/.claude/rl-anything"))
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_existing_backfill_hashes(path: Path) -> set[str]:
    """既存の backfill レコードのハッシュを取得（冪等性保証用）."""
    if not path.exists():
        return set()
    hashes = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            if rec.get("backfill") and rec.get("skill") == "implement":
                h = rec.get("hash_to", "")
                if h:
                    hashes.add(h)
        except json.JSONDecodeError:
            continue
    return hashes


def backfill_implement(repo_dir: str) -> dict[str, int]:
    """git log から実装セッションを推定し、テレメトリにバックフィルする."""
    dd = _data_dir()
    usage_path = dd / "usage.jsonl"
    journal_path = dd / "growth-journal.jsonl"

    existing = _load_existing_backfill_hashes(usage_path)
    sessions = parse_git_sessions(repo_dir)

    project = Path(repo_dir).name

    written = 0
    skipped = 0

    for s in sessions:
        if s["hash_to"] in existing:
            skipped += 1
            continue

        mode = estimate_mode(s["commits"], s["files_changed"])
        lanes = min(4, max(2, s["files_changed"] // 3)) if mode == "parallel" else 1

        usage_record = {
            "ts": s["ts"],
            "skill": "implement",
            "project": project,
            "tasks_total": s["impl_commits"],
            "tasks_completed": s["impl_commits"],
            "mode": mode,
            "conformance_rate": _DEFAULT_CONFORMANCE,
            "lanes": lanes,
            "outcome": "success",
            "backfill": True,
            "hash_to": s["hash_to"],
            "version_from": s["version_from"],
            "version_to": s["version_to"],
        }
        with open(usage_path, "a") as f:
            f.write(json.dumps(usage_record, ensure_ascii=False) + "\n")

        journal_record = {
            "ts": s["ts"],
            "type": "implementation",
            "source": "implement-backfill",
            "tasks_completed": s["impl_commits"],
            "conformance_rate": _DEFAULT_CONFORMANCE,
            "mode": mode,
            "phase": "unknown",
            "backfill": True,
        }
        with open(journal_path, "a") as f:
            f.write(json.dumps(journal_record, ensure_ascii=False) + "\n")

        written += 1

    return {
        "sessions_found": len(sessions),
        "records_written": written,
        "skipped": skipped,
    }


if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    result = backfill_implement(repo)
    print(json.dumps(result, indent=2))
