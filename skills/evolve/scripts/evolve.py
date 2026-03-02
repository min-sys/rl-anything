#!/usr/bin/env python3
"""Evolve オーケストレーター。

Observe データ確認 → Discover → Optimize → Prune → Report の全フェーズを
1つのコマンドで実行する。

前提: セクション 1-6 のコンポーネントが全て実装されていること。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))

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
    """前回 evolve 実行以降のセッション数を数える。"""
    state = load_evolve_state()
    last_run = state.get("last_run_timestamp", "")

    sessions_file = DATA_DIR / "sessions.jsonl"
    if not sessions_file.exists():
        return 0

    count = 0
    for line in sessions_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "")
            if ts > last_run:
                count += 1
        except json.JSONDecodeError:
            continue
    return count


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
    """観測データの十分性をチェックする。"""
    sessions = count_new_sessions()
    observations = count_new_observations()

    return {
        "sessions": sessions,
        "observations": observations,
        "sufficient": sessions >= 3 and observations >= 10,
        "message": (
            f"前回 evolve 以降: {sessions} セッション, {observations} 観測"
            if sessions < 3 or observations < 10
            else f"{sessions} セッション, {observations} 観測 — データ十分"
        ),
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

    # Phase 2: Discover
    try:
        from discover import run_discover
        discover_result = run_discover()
        result["phases"]["discover"] = discover_result
    except Exception as e:
        result["phases"]["discover"] = {"error": str(e)}

    # Phase 3: Audit
    try:
        from audit import run_audit
        audit_report = run_audit(project_dir)
        result["phases"]["audit"] = {"report": audit_report}
    except Exception as e:
        result["phases"]["audit"] = {"error": str(e)}

    # Phase 4: Prune（dry-run 時は候補のみ）
    try:
        from prune import run_prune
        prune_result = run_prune(project_dir)
        result["phases"]["prune"] = prune_result
    except Exception as e:
        result["phases"]["prune"] = {"error": str(e)}

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
