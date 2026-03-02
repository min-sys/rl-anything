#!/usr/bin/env python3
"""ワークフロー分析スクリプト。

workflows.jsonl / usage.jsonl を読み込み、
Phase C proposal の設計入力となるマークダウンレポートを stdout に出力する。
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

# hooks/common.py を import
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "hooks"))

import common


def load_jsonl(filepath: Path) -> List[Dict[str, Any]]:
    """JSONL ファイルを読み込む。"""
    if not filepath.exists():
        return []
    records = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def analyze_consistency(workflows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """同一 skill_name のステップ構成パターンを比較し consistency_score を算出する。

    consistency_score = 最頻パターンの出現率（0.0〜1.0）。
    """
    by_skill: Dict[str, List[List[str]]] = defaultdict(list)
    for wf in workflows:
        skill = wf.get("skill_name", "unknown")
        steps = wf.get("steps", [])
        pattern = [s.get("tool", "") for s in steps]
        by_skill[skill].append(pattern)

    results = {}
    for skill, patterns in by_skill.items():
        # パターンを文字列化してカウント
        pattern_strs = [" → ".join(p) for p in patterns]
        counter = Counter(pattern_strs)
        total = len(pattern_strs)
        most_common_count = counter.most_common(1)[0][1] if counter else 0
        consistency_score = most_common_count / total if total > 0 else 0.0

        results[skill] = {
            "total_workflows": total,
            "unique_patterns": len(counter),
            "consistency_score": round(consistency_score, 3),
            "most_common_pattern": counter.most_common(1)[0][0] if counter else "",
            "most_common_count": most_common_count,
            "all_patterns": dict(counter.most_common()),
        }

    return results


def analyze_variations(workflows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """ステップの順序・種類・回数のばらつきを集計する。"""
    by_skill: Dict[str, List[Dict]] = defaultdict(list)
    for wf in workflows:
        skill = wf.get("skill_name", "unknown")
        by_skill[skill].append(wf)

    results = {}
    for skill, wfs in by_skill.items():
        step_counts = [wf.get("step_count", 0) for wf in wfs]
        tool_types: Counter = Counter()
        intent_types: Counter = Counter()
        for wf in wfs:
            for step in wf.get("steps", []):
                tool_types[step.get("tool", "")] += 1
                intent_types[step.get("intent_category", "")] += 1

        avg_steps = sum(step_counts) / len(step_counts) if step_counts else 0
        results[skill] = {
            "workflow_count": len(wfs),
            "avg_steps": round(avg_steps, 1),
            "min_steps": min(step_counts) if step_counts else 0,
            "max_steps": max(step_counts) if step_counts else 0,
            "tool_distribution": dict(tool_types.most_common()),
            "intent_distribution": dict(intent_types.most_common()),
        }

    return results


def analyze_intervention(usage: List[Dict[str, Any]]) -> Dict[str, Any]:
    """workflow 内 vs ad-hoc の比率、セッション内混在パターンを分析する。"""
    total_agents = 0
    contextualized = 0
    ad_hoc = 0
    sessions_with_both: set = set()

    by_session: Dict[str, Dict[str, bool]] = defaultdict(lambda: {"has_wf": False, "has_adhoc": False})

    for rec in usage:
        if not rec.get("skill_name", "").startswith("Agent:"):
            continue
        total_agents += 1
        session_id = rec.get("session_id", "")

        if rec.get("workflow_id"):
            contextualized += 1
            by_session[session_id]["has_wf"] = True
        else:
            ad_hoc += 1
            by_session[session_id]["has_adhoc"] = True

    for sid, flags in by_session.items():
        if flags["has_wf"] and flags["has_adhoc"]:
            sessions_with_both.add(sid)

    return {
        "total_agent_calls": total_agents,
        "contextualized": contextualized,
        "ad_hoc": ad_hoc,
        "contextualized_ratio": round(contextualized / total_agents, 3) if total_agents > 0 else 0.0,
        "sessions_with_mixed_patterns": len(sessions_with_both),
        "total_sessions_with_agents": len(by_session),
    }


def analyze_discover_prune(usage: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Discover/Prune の精度比較に必要なデータを集計する。"""
    backfill_count = 0
    trace_count = 0
    hook_count = 0
    skills_with_parent: set = set()
    skills_without_parent: set = set()

    for rec in usage:
        source = rec.get("source", "")
        if source == "backfill":
            backfill_count += 1
        elif source == "trace":
            trace_count += 1
        else:
            hook_count += 1

        parent = rec.get("parent_skill")
        skill = rec.get("skill_name", "")
        if parent:
            skills_with_parent.add(parent)
        elif skill.startswith("Agent:") and source != "backfill":
            skills_without_parent.add(skill)

    return {
        "total_records": len(usage),
        "backfill_records": backfill_count,
        "trace_records": trace_count,
        "hook_records": hook_count,
        "skills_referenced_as_parent": sorted(skills_with_parent),
        "ad_hoc_agent_types": sorted(skills_without_parent),
    }


def format_report(
    consistency: Dict[str, Any],
    variations: Dict[str, Any],
    intervention: Dict[str, Any],
    discover_prune: Dict[str, Any],
    workflow_count: int,
    usage_count: int,
) -> str:
    """マークダウンレポートを生成する。"""
    lines = []
    lines.append("# Workflow Analysis Report")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **workflows.jsonl レコード数**: {workflow_count}")
    lines.append(f"- **usage.jsonl レコード数**: {usage_count}")
    lines.append(f"- **分析対象スキル数**: {len(consistency)}")
    lines.append("")

    # 一貫性分析
    lines.append("## 1. ワークフロー構造の一貫性分析")
    lines.append("")
    if not consistency:
        lines.append("*データなし*")
    else:
        lines.append("| Skill | Workflows | Unique Patterns | Consistency Score | Most Common Pattern |")
        lines.append("|-------|-----------|-----------------|-------------------|---------------------|")
        for skill, data in sorted(consistency.items(), key=lambda x: x[1]["consistency_score"], reverse=True):
            lines.append(
                f"| {skill} | {data['total_workflows']} | {data['unique_patterns']} "
                f"| {data['consistency_score']:.3f} | {data['most_common_pattern'][:60]} |"
            )
    lines.append("")

    # バリエーション分析
    lines.append("## 2. ステップバリエーション分析")
    lines.append("")
    if not variations:
        lines.append("*データなし*")
    else:
        for skill, data in sorted(variations.items()):
            lines.append(f"### {skill}")
            lines.append("")
            lines.append(f"- Workflow 数: {data['workflow_count']}")
            lines.append(f"- 平均ステップ数: {data['avg_steps']}")
            lines.append(f"- ステップ数範囲: {data['min_steps']} - {data['max_steps']}")
            lines.append(f"- ツール分布: {json.dumps(data['tool_distribution'], ensure_ascii=False)}")
            lines.append(f"- Intent 分布: {json.dumps(data['intent_distribution'], ensure_ascii=False)}")
            lines.append("")

    # 介入分析
    lines.append("## 3. 介入分析（workflow 内 vs ad-hoc）")
    lines.append("")
    lines.append(f"- **総 Agent 呼び出し数**: {intervention['total_agent_calls']}")
    lines.append(f"- **Contextualized（ワークフロー内）**: {intervention['contextualized']}")
    lines.append(f"- **Ad-hoc（手動）**: {intervention['ad_hoc']}")
    lines.append(f"- **Contextualized 比率**: {intervention['contextualized_ratio']:.1%}")
    lines.append(f"- **混在セッション数**: {intervention['sessions_with_mixed_patterns']} / {intervention['total_sessions_with_agents']}")
    lines.append("")

    # Discover/Prune 比較データ
    lines.append("## 4. Discover/Prune 比較データ")
    lines.append("")
    lines.append(f"- **Backfill レコード**: {discover_prune['backfill_records']}")
    lines.append(f"- **Trace レコード**: {discover_prune['trace_records']}")
    lines.append(f"- **Hook レコード**: {discover_prune['hook_records']}")
    lines.append(f"- **Parent として参照されているスキル**: {', '.join(discover_prune['skills_referenced_as_parent']) or 'なし'}")
    lines.append(f"- **Ad-hoc Agent タイプ**: {', '.join(discover_prune['ad_hoc_agent_types']) or 'なし'}")
    lines.append("")

    return "\n".join(lines)


def run_analysis() -> str:
    """分析を実行してマークダウンレポートを返す。"""
    workflows = load_jsonl(common.DATA_DIR / "workflows.jsonl")
    usage = load_jsonl(common.DATA_DIR / "usage.jsonl")

    consistency = analyze_consistency(workflows)
    variations = analyze_variations(workflows)
    intervention = analyze_intervention(usage)
    discover_prune = analyze_discover_prune(usage)

    return format_report(
        consistency=consistency,
        variations=variations,
        intervention=intervention,
        discover_prune=discover_prune,
        workflow_count=len(workflows),
        usage_count=len(usage),
    )


def main() -> None:
    report = run_analysis()
    print(report)


if __name__ == "__main__":
    main()
