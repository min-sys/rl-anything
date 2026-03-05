#!/usr/bin/env python3
"""Evolve オーケストレーター。

Observe データ確認 → Discover → Enrich → Optimize → Reorganize → Prune(+Merge) →
Fitness Evolution → Report の全フェーズを1つのコマンドで実行する。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "discover" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "prune" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "evolve-fitness" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "enrich" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "reorganize" / "scripts"))

DATA_DIR = Path.home() / ".claude" / "rl-anything"
EVOLVE_STATE_FILE = DATA_DIR / "evolve-state.json"


def load_evolve_state() -> Dict[str, Any]:
    """前回の evolve 実行状態を読み込む。"""
    if not EVOLVE_STATE_FILE.exists():
        return {}
    try:
        return json.loads(EVOLVE_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_evolve_state(state: Dict[str, Any]) -> None:
    """evolve 実行状態を保存する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVOLVE_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def count_new_sessions() -> int:
    """前回 evolve 実行以降のセッション数を数える。

    sessions.jsonl と usage.jsonl 両方からユニーク session_id を集計する。
    backfill データ（sessions.jsonl に書かれない）も含めてカウントできる。
    """
    state = load_evolve_state()
    last_run = state.get("last_run_timestamp", "")
    session_ids: set = set()

    # sessions.jsonl から集計
    sessions_file = DATA_DIR / "sessions.jsonl"
    if sessions_file.exists():
        for line in sessions_file.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                ts = rec.get("timestamp", "")
                if ts > last_run:
                    sid = rec.get("session_id", "")
                    if sid:
                        session_ids.add(sid)
            except json.JSONDecodeError:
                continue

    # usage.jsonl からもユニーク session_id を集計（backfill 対応）
    usage_file = DATA_DIR / "usage.jsonl"
    if usage_file.exists():
        for line in usage_file.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                ts = rec.get("timestamp", "")
                if ts > last_run:
                    sid = rec.get("session_id", "")
                    if sid:
                        session_ids.add(sid)
            except json.JSONDecodeError:
                continue

    return len(session_ids)


def count_new_observations() -> int:
    """前回 evolve 実行以降の観測数を数える。"""
    state = load_evolve_state()
    last_run = state.get("last_run_timestamp", "")

    usage_file = DATA_DIR / "usage.jsonl"
    if not usage_file.exists():
        return 0

    count = 0
    for line in usage_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "")
            if ts > last_run:
                count += 1
        except json.JSONDecodeError:
            continue
    return count


def check_data_sufficiency() -> Dict[str, Any]:
    """観測データの十分性をチェックする。

    判定基準: セッション3+かつ観測10+、
    または全観測が20+（backfill で大量データがある場合を考慮）。
    """
    sessions = count_new_sessions()
    observations = count_new_observations()

    # 全データ（last_run 以前も含む）の観測数もフォールバックで確認
    total_observations = _count_total_observations()

    sufficient = (
        (sessions >= 3 and observations >= 10)
        or total_observations >= 20
    )

    if sufficient:
        msg = f"{sessions} セッション, {observations} 新規観測 (全{total_observations}) — データ十分"
    else:
        msg = f"前回 evolve 以降: {sessions} セッション, {observations} 観測 (全{total_observations})"

    return {
        "sessions": sessions,
        "observations": observations,
        "total_observations": total_observations,
        "sufficient": sufficient,
        "message": msg,
    }


def _count_total_observations() -> int:
    """usage.jsonl の全レコード数を返す。"""
    usage_file = DATA_DIR / "usage.jsonl"
    if not usage_file.exists():
        return 0
    return sum(
        1 for line in usage_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def check_fitness_function(project_dir: Optional[str] = None) -> Dict[str, Any]:
    """プロジェクト固有の fitness 関数の有無をチェックする。"""
    proj = Path(project_dir) if project_dir else Path.cwd()
    fitness_dir = proj / "scripts" / "rl" / "fitness"
    criteria_file = proj / ".claude" / "fitness-criteria.md"

    fitness_files = []
    if fitness_dir.exists():
        fitness_files = [f.stem for f in fitness_dir.glob("*.py") if f.name != "__init__.py"]

    return {
        "has_fitness": len(fitness_files) > 0,
        "has_criteria": criteria_file.exists(),
        "fitness_functions": fitness_files,
        "fitness_dir": str(fitness_dir),
    }


def run_evolve(
    project_dir: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """全フェーズを実行する。

    Args:
        project_dir: プロジェクトディレクトリ
        dry_run: True の場合、レポートのみ出力し変更は行わない

    Returns:
        各フェーズの結果を含む辞書
    """
    result: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "phases": {},
    }

    # Phase 1: Observe データ確認
    sufficiency = check_data_sufficiency()
    result["phases"]["observe"] = sufficiency

    if not sufficiency["sufficient"]:
        result["phases"]["observe"]["action"] = "skip_recommended"
        # スキップ推奨だがユーザー選択に委ねる
        print(f"データ不足: {sufficiency['message']}")
        print("スキップ推奨。--force で強制実行可能。")

    # Phase 1.5: Fitness 関数チェック
    fitness_check = check_fitness_function(project_dir)
    result["phases"]["fitness"] = fitness_check

    # Phase 2: Discover
    try:
        from discover import run_discover
        project_root = Path(project_dir) if project_dir else None
        discover_result = run_discover(project_root=project_root)
        result["phases"]["discover"] = discover_result
    except Exception as e:
        result["phases"]["discover"] = {"error": str(e)}

    # Phase 2.5: Enrich（Discover の直後）
    try:
        from enrich import run_enrich
        discover_data = result["phases"].get("discover", {})
        enrich_result = run_enrich(discover_data, project_dir)
        result["phases"]["enrich"] = enrich_result
    except Exception as e:
        result["phases"]["enrich"] = {"error": str(e)}

    # Phase 3: Audit
    try:
        from audit import run_audit
        audit_report = run_audit(project_dir)
        result["phases"]["audit"] = {"report": audit_report}
    except Exception as e:
        result["phases"]["audit"] = {"error": str(e)}

    # Phase 3.5: Reorganize（Prune の前）
    try:
        from reorganize import run_reorganize
        reorganize_result = run_reorganize(project_dir)
        result["phases"]["reorganize"] = reorganize_result
    except Exception as e:
        result["phases"]["reorganize"] = {"error": str(e)}

    # Phase 4: Prune（dry-run 時は候補のみ）
    try:
        from prune import run_prune
        # Reorganize の merge_groups を Prune に渡す
        reorganize_data = result["phases"].get("reorganize", {})
        merge_groups = reorganize_data.get("merge_groups", []) if not reorganize_data.get("skipped") else []
        prune_result = run_prune(project_dir, reorganize_merge_groups=merge_groups)
        result["phases"]["prune"] = prune_result
    except Exception as e:
        result["phases"]["prune"] = {"error": str(e)}

    # Phase 5: Fitness Evolution（評価関数の改善チェック）
    try:
        from fitness_evolution import run_fitness_evolution
        fitness_evo_result = run_fitness_evolution()
        result["phases"]["fitness_evolution"] = fitness_evo_result
    except Exception as e:
        result["phases"]["fitness_evolution"] = {"error": str(e)}

    # State 更新（dry-run でない場合）
    if not dry_run:
        save_evolve_state({
            "last_run_timestamp": datetime.now(timezone.utc).isoformat(),
            "sessions_processed": sufficiency["sessions"],
            "observations_processed": sufficiency["observations"],
        })

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evolve オーケストレーター")
    parser.add_argument("--project-dir", default=None, help="プロジェクトディレクトリ")
    parser.add_argument("--dry-run", action="store_true", help="レポートのみ、変更なし")

    args = parser.parse_args()

    result = run_evolve(
        project_dir=args.project_dir,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
