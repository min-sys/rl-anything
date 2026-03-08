#!/usr/bin/env python3
"""テレメトリ駆動の環境実効性スコア。

3軸（Utilization / Effectiveness / Implicit Reward）で
LLM コストゼロの行動実績スコア（0.0〜1.0）を算出する。
"""
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent


def _ensure_paths():
    paths = [
        str(_plugin_root / "scripts" / "lib"),
        str(_plugin_root / "scripts"),
    ]
    for p in paths:
        if p not in sys.path:
            sys.path.insert(0, p)


THRESHOLDS = {
    "min_sessions": 30,
    "min_days": 7,
    "implicit_reward_window_sec": 60,
}

WEIGHTS = {
    "utilization": 0.30,
    "effectiveness": 0.40,
    "implicit_reward": 0.30,
}

_EFFECTIVENESS_WEIGHTS = {
    "error_reduction": 0.35,
    "correction_trend": 0.35,
    "workflow_completion": 0.30,
}

_IMPLICIT_WEIGHTS = {
    "success_rate": 0.60,
    "repeat_usage": 0.40,
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _find_all_skills(project_dir: Path) -> List[str]:
    """project_dir/.claude/skills/ 配下の SKILL.md を持つディレクトリ名を返す。"""
    skills_dir = project_dir / ".claude" / "skills"
    if not skills_dir.exists():
        return []
    return [p.parent.name for p in skills_dir.rglob("SKILL.md")]


def score_utilization(project_dir: Path, days: int = 30) -> float:
    """Skill 利用率 + Shannon entropy 正規化。"""
    _ensure_paths()
    from telemetry_query import query_usage

    project_dir = Path(project_dir)
    all_skills = _find_all_skills(project_dir)
    if not all_skills:
        return 0.0

    project_name = project_dir.name
    since = _iso_days_ago(days)
    records = query_usage(project=project_name, since=since, include_unknown=True)

    if not records:
        return 0.0

    # Skill 利用カウント
    skill_counts: Dict[str, int] = {}
    for rec in records:
        skill = rec.get("skill_name", "")
        if skill:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

    # 利用率: invoke された Skill 数 / 全 Skill 数
    used_skills = set(skill_counts.keys()) & set(all_skills)
    utilization_rate = len(used_skills) / len(all_skills)

    # Shannon entropy 正規化
    total = sum(skill_counts.values())
    if total == 0 or len(skill_counts) <= 1:
        normalized_entropy = 0.0
    else:
        entropy = 0.0
        for count in skill_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        max_entropy = math.log2(len(skill_counts))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

    return round(utilization_rate * 0.5 + normalized_entropy * 0.5, 4)


def score_effectiveness(project_dir: Path, days: int = 30) -> float:
    """エラー減少率 + 修正トレンド + ワークフロー完走率。"""
    _ensure_paths()
    from telemetry_query import query_errors, query_corrections, query_workflows

    project_dir = Path(project_dir)
    project_name = project_dir.name
    now = _iso_now()
    mid = _iso_days_ago(days)
    start = _iso_days_ago(days * 2)

    # エラー減少率
    recent_errors = query_errors(project=project_name, since=mid, until=now, include_unknown=True)
    prev_errors = query_errors(project=project_name, since=start, until=mid, include_unknown=True)
    prev_count = len(prev_errors)
    recent_count = len(recent_errors)
    if prev_count == 0 and recent_count == 0:
        error_reduction = 0.5  # 中立
    elif prev_count == 0:
        error_reduction = 0.5  # 前期間データなし → 中立
    else:
        raw = (prev_count - recent_count) / max(prev_count, 1)
        error_reduction = (max(min(raw, 1.0), -1.0) + 1.0) / 2.0  # [-1,1] → [0,1]

    # 修正トレンド（corrections 減少 = 良い）
    recent_corrections = query_corrections(project=project_name, since=mid, until=now, include_unknown=True)
    prev_corrections = query_corrections(project=project_name, since=start, until=mid, include_unknown=True)
    prev_corr = len(prev_corrections)
    recent_corr = len(recent_corrections)
    if prev_corr == 0 and recent_corr == 0:
        correction_trend = 0.5
    elif prev_corr == 0:
        correction_trend = 0.5
    else:
        raw = (prev_corr - recent_corr) / max(prev_corr, 1)
        correction_trend = (max(min(raw, 1.0), -1.0) + 1.0) / 2.0

    # ワークフロー完走率（step_count >= 2 を完走とみなす）
    workflows = query_workflows(since=mid, until=now)
    if not workflows:
        workflow_completion = 0.5  # データなし → 中立
    else:
        completed = sum(1 for w in workflows if (w.get("step_count") or 0) >= 2)
        workflow_completion = completed / len(workflows)

    return round(
        _EFFECTIVENESS_WEIGHTS["error_reduction"] * error_reduction
        + _EFFECTIVENESS_WEIGHTS["correction_trend"] * correction_trend
        + _EFFECTIVENESS_WEIGHTS["workflow_completion"] * workflow_completion,
        4,
    )


def score_implicit_reward(project_dir: Path, days: int = 30) -> float:
    """Skill 成功率推定 + 繰り返し利用率。"""
    _ensure_paths()
    from telemetry_query import query_usage, query_corrections

    project_dir = Path(project_dir)
    project_name = project_dir.name
    since = _iso_days_ago(days)

    records = query_usage(project=project_name, since=since, include_unknown=True)
    corrections = query_corrections(project=project_name, since=since, include_unknown=True)

    if not records:
        return 0.0

    # corrections をセッション別・タイムスタンプでインデックス化
    corrections_by_session: Dict[str, List[str]] = {}
    for c in corrections:
        sid = c.get("session_id", "")
        ts = c.get("timestamp", "")
        if sid and ts:
            corrections_by_session.setdefault(sid, []).append(ts)

    # Skill 成功率推定: invoke 後60秒以内に同セッションの correction がない = success
    window = THRESHOLDS["implicit_reward_window_sec"]
    success_count = 0
    total_invocations = 0
    skill_usage_counts: Dict[str, int] = {}

    for rec in records:
        skill = rec.get("skill_name", "")
        if not skill:
            continue
        total_invocations += 1
        skill_usage_counts[skill] = skill_usage_counts.get(skill, 0) + 1

        session_id = rec.get("session_id", "")
        invoke_ts = rec.get("timestamp", "")
        if not session_id or not invoke_ts:
            success_count += 1  # データ不足 → success とみなす
            continue

        session_corrections = corrections_by_session.get(session_id, [])
        has_nearby_correction = False
        for corr_ts in session_corrections:
            try:
                invoke_dt = datetime.fromisoformat(invoke_ts.replace("Z", "+00:00"))
                corr_dt = datetime.fromisoformat(corr_ts.replace("Z", "+00:00"))
                diff = (corr_dt - invoke_dt).total_seconds()
                if 0 <= diff <= window:
                    has_nearby_correction = True
                    break
            except (ValueError, AttributeError):
                continue
        if not has_nearby_correction:
            success_count += 1

    success_rate = success_count / total_invocations if total_invocations > 0 else 1.0

    # 繰り返し利用率: 2回以上利用された Skill の割合
    if not skill_usage_counts:
        repeat_rate = 0.0
    else:
        repeated = sum(1 for c in skill_usage_counts.values() if c >= 2)
        repeat_rate = repeated / len(skill_usage_counts)

    return round(
        _IMPLICIT_WEIGHTS["success_rate"] * success_rate
        + _IMPLICIT_WEIGHTS["repeat_usage"] * repeat_rate,
        4,
    )


def _get_session_timestamp(session: Dict[str, Any]) -> str:
    """セッションの timestamp を取得する（live: timestamp, backfill: first_timestamp）。"""
    return session.get("timestamp") or session.get("first_timestamp") or ""


def _get_session_project(session: Dict[str, Any]) -> Optional[str]:
    """セッションの project 名を取得する（live: project, backfill: project_name）。"""
    return session.get("project") or session.get("project_name")


def _check_data_sufficiency(project_dir: Path, days: int = 30) -> Dict[str, Any]:
    """データ充足度を判定する。"""
    _ensure_paths()
    from telemetry_query import query_sessions

    project_dir = Path(project_dir)
    project_name = project_dir.name
    # project フィルタなしで全件取得し、Python 側で project/project_name 両方にマッチさせる
    all_sessions = query_sessions(include_unknown=True)
    sessions = [
        s for s in all_sessions
        if _get_session_project(s) == project_name or _get_session_project(s) is None
    ]

    session_count = len(sessions)

    # データ幅（日数）— timestamp / first_timestamp の両方を考慮
    if sessions:
        timestamps = [_get_session_timestamp(s) for s in sessions]
        timestamps = [t for t in timestamps if t]
        if timestamps:
            timestamps.sort()
            try:
                earliest = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
                latest = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
                data_span_days = (latest - earliest).days
            except (ValueError, AttributeError):
                data_span_days = 0
        else:
            data_span_days = 0
    else:
        data_span_days = 0

    sufficient = (
        session_count >= THRESHOLDS["min_sessions"]
        and data_span_days >= THRESHOLDS["min_days"]
    )

    return {
        "sufficient": sufficient,
        "session_count": session_count,
        "data_span_days": data_span_days,
        "min_sessions": THRESHOLDS["min_sessions"],
        "min_days": THRESHOLDS["min_days"],
    }


def compute_telemetry_score(project_dir: Path, days: int = 30) -> Dict[str, Any]:
    """3軸の重み付き平均で統合 Telemetry Score を算出する。"""
    project_dir = Path(project_dir)

    util = score_utilization(project_dir, days)
    effect = score_effectiveness(project_dir, days)
    implicit = score_implicit_reward(project_dir, days)
    sufficiency = _check_data_sufficiency(project_dir, days)

    overall = (
        WEIGHTS["utilization"] * util
        + WEIGHTS["effectiveness"] * effect
        + WEIGHTS["implicit_reward"] * implicit
    )

    return {
        "overall": round(overall, 4),
        "utilization": util,
        "effectiveness": effect,
        "implicit_reward": implicit,
        "data_sufficiency": sufficiency["sufficient"],
        "data_details": sufficiency,
        "weights": WEIGHTS,
    }


def format_telemetry_report(result: Dict[str, Any]) -> List[str]:
    """Telemetry Score を audit レポート用にフォーマットする。"""
    lines = [f"## Telemetry Score: {result['overall']:.2f}", ""]

    for axis in ("utilization", "effectiveness", "implicit_reward"):
        score = result[axis]
        bar_filled = int(score * 20)
        bar_empty = 20 - bar_filled
        bar = "\u2588" * bar_filled + "\u2591" * bar_empty
        label = axis.replace("_", " ").capitalize()
        lines.append(f"{label:18s} {score:.2f} {bar}")

    if not result["data_sufficiency"]:
        details = result["data_details"]
        lines.append("")
        lines.append(
            f"**Warning**: Data insufficient: {details['session_count']} sessions "
            f"(minimum {details['min_sessions']} required), "
            f"{details['data_span_days']} days span "
            f"(minimum {details['min_days']} required)"
        )

    lines.append("")
    return lines


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Telemetry Score 算出")
    parser.add_argument("project_dir", help="プロジェクトディレクトリ")
    parser.add_argument("--days", type=int, default=30, help="集計期間（日）")
    args = parser.parse_args()

    result = compute_telemetry_score(Path(args.project_dir), args.days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
