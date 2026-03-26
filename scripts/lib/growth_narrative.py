#!/usr/bin/env python3
"""NFD Growth Narrative — 環境プロファイル + 成長ストーリー生成。

テレメトリから環境の特徴を自動抽出し、「この環境はどういう個性を持って
育ったか」を可視化する。デフォルトはテンプレートベース（LLM コストゼロ）。
"""
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "hooks"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))


# ── データクラス ────────────────────────────────────────────────


@dataclass
class EnvironmentProfile:
    strengths: List[str] = field(default_factory=list)
    personality_traits: List[str] = field(default_factory=list)
    growth_milestones: List[str] = field(default_factory=list)
    crystallization_style: str = "unknown"


# ── Personality Trait 定義 ──────────────────────────────────────


def _check_careful(stats: dict) -> bool:
    total = stats.get("total", 0)
    if total == 0:
        return False
    return stats.get("verify_count", 0) / total > 0.3


def _check_organizer(stats: dict) -> bool:
    total = stats.get("total", 0)
    if total == 0:
        return False
    return stats.get("refactor_count", 0) / total > 0.25


def _check_feedbacker(stats: dict, cryst_stats: dict) -> bool:
    return cryst_stats.get("eta", 0.0) > 0.5


def _check_explorer(skill_counts: list) -> bool:
    return len(skill_counts) > 10


FAST_SHIPPER_THRESHOLD = 2.0  # commits per session average


TRAIT_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "careful": {
        "name_en": "Careful",
        "name_ja": "慎重派",
        "check": "corrections",
    },
    "organizer": {
        "name_en": "Organizer",
        "name_ja": "整理好き",
        "check": "corrections",
    },
    "feedbacker": {
        "name_en": "Feedbacker",
        "name_ja": "フィードバッカー",
        "check": "crystallization",
    },
    "explorer": {
        "name_en": "Explorer",
        "name_ja": "探検家",
        "check": "skills",
    },
    "fast_shipper": {
        "name_en": "Fast Shipper",
        "name_ja": "速攻派",
        "check": "workflows",
    },
}


# ── データ取得ヘルパー ──────────────────────────────────────────


def _query_skill_counts(project: str) -> List[Dict[str, Any]]:
    """usage.jsonl からスキル使用頻度を取得。"""
    try:
        from telemetry_query import query_skill_counts
        return query_skill_counts(project=project, min_count=1)
    except Exception:
        return []


def _query_corrections_stats(project: str) -> dict:
    """corrections の傾向統計を取得。"""
    try:
        from telemetry_query import query_corrections
        corrections = query_corrections(project=project)
        if not corrections:
            return {}

        total = len(corrections)
        verify_count = sum(
            1 for c in corrections
            if any(kw in c.get("message", "").lower() for kw in ("verify", "check", "confirm", "test"))
        )
        refactor_count = sum(
            1 for c in corrections
            if any(kw in c.get("message", "").lower() for kw in ("refactor", "reorganize", "clean", "rename", "split"))
        )
        return {"total": total, "verify_count": verify_count, "refactor_count": refactor_count}
    except Exception:
        return {}


def _query_crystallization_stats(project: str) -> dict:
    """結晶化統計を取得。η = crystallized_rules / total_corrections (0.0-1.0)。"""
    try:
        from growth_journal import query_crystallizations, count_crystallized_rules
        from telemetry_query import query_corrections

        events = query_crystallizations(project=project)
        crystallized = count_crystallized_rules(project=project)
        corrections = query_corrections(project=project)
        total_corrections = len(corrections) if corrections else 0
        eta = crystallized / max(total_corrections, 1)
        return {"eta": eta, "count": len(events), "crystallized": crystallized}
    except Exception:
        return {"eta": 0.0, "count": 0, "crystallized": 0}


def _get_crystallization_events(project: str) -> List[Dict[str, Any]]:
    """結晶化イベントを取得。"""
    try:
        from growth_journal import query_crystallizations
        return query_crystallizations(project=project)
    except Exception:
        return []


def _query_commit_frequency(project: str) -> float:
    """workflows.jsonl から session あたり commit スキル使用頻度を算出。"""
    try:
        from telemetry_query import query_workflows, query_sessions

        workflows = query_workflows(project=project)
        sessions = query_sessions(project=project)
        if not sessions:
            return 0.0

        commit_count = sum(
            1 for w in (workflows or [])
            if w.get("skill_name") == "commit"
        )
        return commit_count / len(sessions)
    except Exception:
        return 0.0


# ── プロファイル計算 ────────────────────────────────────────────


def compute_profile(project: str) -> EnvironmentProfile:
    """テレメトリからプロファイルを生成（LLM 不使用）。"""
    profile = EnvironmentProfile()

    # strengths: top-3 スキル
    skill_counts = _query_skill_counts(project)
    if skill_counts:
        sorted_skills = sorted(skill_counts, key=lambda x: x.get("count", 0), reverse=True)
        profile.strengths = [s["skill_name"] for s in sorted_skills[:3]]

    # corrections stats
    corr_stats = _query_corrections_stats(project)
    cryst_stats = _query_crystallization_stats(project)

    # personality traits
    traits = []
    if _check_careful(corr_stats):
        traits.append("careful")
    if _check_organizer(corr_stats):
        traits.append("organizer")
    if _check_feedbacker(corr_stats, cryst_stats):
        traits.append("feedbacker")
    if _check_explorer(skill_counts):
        traits.append("explorer")
    if _query_commit_frequency(project) > FAST_SHIPPER_THRESHOLD:
        traits.append("fast_shipper")
    profile.personality_traits = traits

    # crystallization style
    eta = cryst_stats.get("eta", 0.0)
    if eta > 0.5:
        profile.crystallization_style = "correction-driven"
    elif cryst_stats.get("count", 0) > 0:
        profile.crystallization_style = "gradual"
    else:
        profile.crystallization_style = "unknown"

    # milestones
    events = _get_crystallization_events(project)
    if events:
        phases_seen = []
        for ev in events:
            p = ev.get("phase", "")
            if p and p not in phases_seen:
                phases_seen.append(p)
        profile.growth_milestones = [
            f"Phase transition: {p}" for p in phases_seen
        ]

    return profile


# ── ストーリー生成 ──────────────────────────────────────────────


def generate_story(project: str, use_llm: bool = False) -> str:
    """成長ストーリーを生成（テンプレートベース）。"""
    events = _get_crystallization_events(project)

    if not events:
        return "まだ結晶化イベントがありません。evolve/reflect を実行すると成長が記録されます。"

    lines = ["## 成長ストーリー", ""]

    # 時系列でグループ化
    for i, ev in enumerate(events):
        ts = ev.get("ts", "")[:10]  # YYYY-MM-DD
        targets = ev.get("targets", [])
        evidence = ev.get("evidence_count", 0)
        phase = ev.get("phase", "unknown")
        source = ev.get("source", "evolve")

        target_str = ", ".join(targets[:3]) if targets else "(no targets)"
        if len(targets) > 3:
            target_str += f" (+{len(targets) - 3})"

        lines.append(f"- **{ts}** [{phase}] {target_str} (evidence: {evidence}, source: {source})")

    lines.append("")
    lines.append(f"合計 {len(events)} 件の結晶化イベント")

    return "\n".join(lines)
