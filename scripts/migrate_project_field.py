#!/usr/bin/env python3
"""既存 usage.jsonl に project フィールドをバックフィルするワンショットマイグレーション。

2層リカバリ:
  Tier 1: sessions.jsonl の session_id → project_name（last-wins dedup）
  Tier 2: ~/.claude/projects/ の filesystem consensus（同ディレクトリ内の多数決）
"""
import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

# プラグインルートを sys.path に追加して hooks/common.py を import
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "hooks"))

import common

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _load_jsonl(filepath: Path) -> List[dict]:
    """JSONL ファイルを読み込む。"""
    if not filepath.exists():
        return []
    records = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def build_session_mapping(
    sessions_file: Optional[Path] = None,
) -> Dict[str, str]:
    """Tier 1: sessions.jsonl から session_id → project_name マッピングを構築する。

    - 同一 session_id の重複は last-wins
    - project_name が null のレコードはスキップ
    """
    filepath = sessions_file or (common.DATA_DIR / "sessions.jsonl")
    records = _load_jsonl(filepath)
    mapping: Dict[str, str] = {}
    for rec in records:
        sid = rec.get("session_id")
        project = rec.get("project_name")
        if sid and project:
            mapping[sid] = project
    return mapping


def build_fs_recovery(
    tier1_mapping: Dict[str, str],
    projects_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """Tier 2: ~/.claude/projects/ の consensus で session_id → project_name を補完する。

    各プロジェクトディレクトリ内のセッションファイルを走査し、
    Tier 1 でマッピング済みのセッションから多数決で project_name を推定する。
    """
    pdir = projects_dir or CLAUDE_PROJECTS_DIR
    if not pdir.is_dir():
        return {}

    # ディレクトリごとに session_id を収集
    recovery: Dict[str, str] = {}

    for project_subdir in sorted(pdir.iterdir()):
        if not project_subdir.is_dir():
            continue

        # セッションファイルを探索（*.jsonl がセッションファイル）
        session_ids_in_dir: List[str] = []
        for f in project_subdir.iterdir():
            if f.suffix == ".jsonl" and f.stem != "":
                session_ids_in_dir.append(f.stem)

        if not session_ids_in_dir:
            continue

        # Tier 1 マッピング済みセッションから project_name を収集
        known_projects: List[str] = []
        unmapped_sids: List[str] = []

        for sid in session_ids_in_dir:
            if sid in tier1_mapping:
                known_projects.append(tier1_mapping[sid])
            else:
                unmapped_sids.append(sid)

        if not known_projects or not unmapped_sids:
            continue

        # 多数決で consensus を決定
        consensus_project = Counter(known_projects).most_common(1)[0][0]

        for sid in unmapped_sids:
            recovery[sid] = consensus_project

    return recovery


def build_project_mapping(
    sessions_file: Optional[Path] = None,
    projects_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """Tier 1 + Tier 2 を合成した最終マッピングを返す。"""
    tier1 = build_session_mapping(sessions_file)
    tier2 = build_fs_recovery(tier1, projects_dir)

    # Tier 2 は Tier 1 にないものだけ追加
    merged = dict(tier1)
    for sid, project in tier2.items():
        if sid not in merged:
            merged[sid] = project

    return merged


def migrate_usage(
    mapping: Dict[str, str],
    usage_file: Optional[Path] = None,
    dry_run: bool = False,
) -> dict:
    """usage.jsonl の各レコードに project フィールドを追加する。

    - 既に project フィールドを持つレコードは上書きしない（冪等）
    - dry_run=True の場合はファイルを変更しない

    Returns:
        {"total": int, "mapped": int, "unmapped": int, "already_has_project": int}
    """
    filepath = usage_file or (common.DATA_DIR / "usage.jsonl")
    records = _load_jsonl(filepath)

    total = len(records)
    mapped = 0
    unmapped = 0
    already_has_project = 0
    updated_records: List[dict] = []

    for rec in records:
        if "project" in rec:
            already_has_project += 1
            updated_records.append(rec)
            continue

        sid = rec.get("session_id")
        if sid and sid in mapping:
            rec["project"] = mapping[sid]
            mapped += 1
        else:
            rec["project"] = None
            unmapped += 1

        updated_records.append(rec)

    if not dry_run:
        lines = [json.dumps(r, ensure_ascii=False) for r in updated_records]
        filepath.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

    return {
        "total": total,
        "mapped": mapped,
        "unmapped": unmapped,
        "already_has_project": already_has_project,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="既存 usage.jsonl に project フィールドをバックフィルする"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイルを変更せず、マッピング結果のサマリのみ表示",
    )
    args = parser.parse_args()

    usage_file = common.DATA_DIR / "usage.jsonl"
    if not usage_file.exists():
        print("usage.jsonl が見つかりません。", file=sys.stderr)
        sys.exit(1)

    # マッピング構築
    mapping = build_project_mapping()
    tier1 = build_session_mapping()
    tier2_count = len(mapping) - len(tier1)

    print(f"Mapping: Tier 1 (sessions.jsonl): {len(tier1)} sessions")
    print(f"Mapping: Tier 2 (fs consensus):   {tier2_count} sessions")
    print(f"Mapping: Total:                   {len(mapping)} sessions")

    # バックアップ
    if not args.dry_run:
        backup_path = usage_file.with_suffix(".jsonl.bak")
        shutil.copy2(str(usage_file), str(backup_path))
        print(f"Backup: {backup_path}")

    # マイグレーション
    result = migrate_usage(mapping, dry_run=args.dry_run)

    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{mode}Result:")
    print(f"  total:             {result['total']}")
    print(f"  mapped:            {result['mapped']}")
    print(f"  unmapped:          {result['unmapped']}")
    print(f"  already_has_project: {result['already_has_project']}")

    if result["total"] > 0:
        coverage = (result["mapped"] + result["already_has_project"]) / result["total"] * 100
        print(f"  coverage:          {coverage:.1f}%")


if __name__ == "__main__":
    main()
