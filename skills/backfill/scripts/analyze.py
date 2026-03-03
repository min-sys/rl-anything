#!/usr/bin/env python3
"""ワークフロー分析スクリプト。

workflows.jsonl / usage.jsonl を読み込み、
Phase C proposal の設計入力となるマークダウンレポートを stdout に出力する。
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# hooks/common.py を import
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "hooks"))

import common


def get_project_session_ids(project_name: str) -> Set[str]:
    """sessions.jsonl から該当 project_name の session_id セットを返す。

    project_name フィールドが存在しないレコードはフィルタ対象外となる。
    """
    sessions_file = common.DATA_DIR / "sessions.jsonl"
    if not sessions_file.exists():
        return set()
    session_ids: Set[str] = set()
    for line in sessions_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            if record.get("project_name") == project_name:
                sid = record.get("session_id", "")
                if sid:
                    session_ids.add(sid)
        except json.JSONDecodeError:
            continue
    return session_ids


def load_jsonl(filepath: Path, session_ids: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """JSONL ファイルを読み込む。session_ids が指定された場合はフィルタする。"""
    if not filepath.exists():
        return []
    records = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            if session_ids is not None and record.get("session_id") not in session_ids:
                continue
            records.append(record)
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


def analyze_sessions(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """セッションメタデータを分析する。"""
    if not sessions:
        return {
            "total_sessions": 0,
            "avg_tool_calls": 0,
            "avg_duration_minutes": 0,
            "avg_errors": 0,
            "avg_human_messages": 0,
            "tool_distribution": {},
            "intent_distribution": {},
            "sessions_by_duration": {"short": 0, "medium": 0, "long": 0},
        }

    total_tool_calls = []
    durations = []
    errors = []
    human_msgs = []
    tool_dist: Counter = Counter()
    intent_dist: Counter = Counter()
    project_dist: Counter = Counter()

    for sess in sessions:
        total_tool_calls.append(sess.get("total_tool_calls", 0))
        durations.append(sess.get("session_duration_seconds", 0))
        errors.append(sess.get("error_count", 0))
        human_msgs.append(sess.get("human_message_count", 0))

        for tool, count in sess.get("tool_counts", {}).items():
            tool_dist[tool] += count

        for intent in sess.get("user_intents", []):
            intent_dist[intent] += 1

        proj = sess.get("project_name", "unknown")
        if proj:
            project_dist[proj] += 1

    avg_duration_min = (sum(durations) / len(durations) / 60) if durations else 0

    # セッション長の分布（short < 5min, medium 5-30min, long > 30min）
    short = sum(1 for d in durations if d < 300)
    medium = sum(1 for d in durations if 300 <= d < 1800)
    long = sum(1 for d in durations if d >= 1800)

    return {
        "total_sessions": len(sessions),
        "avg_tool_calls": round(sum(total_tool_calls) / len(total_tool_calls), 1) if total_tool_calls else 0,
        "avg_duration_minutes": round(avg_duration_min, 1),
        "avg_errors": round(sum(errors) / len(errors), 1) if errors else 0,
        "avg_human_messages": round(sum(human_msgs) / len(human_msgs), 1) if human_msgs else 0,
        "tool_distribution": dict(tool_dist.most_common()),
        "intent_distribution": dict(intent_dist.most_common()),
        "sessions_by_duration": {"short": short, "medium": medium, "long": long},
        "sessions_by_project": dict(project_dist.most_common()),
    }


def format_report(
    consistency: Dict[str, Any],
    variations: Dict[str, Any],
    intervention: Dict[str, Any],
    discover_prune: Dict[str, Any],
    session_analysis: Dict[str, Any],
    workflow_count: int,
    usage_count: int,
    session_count: int,
) -> str:
    """マークダウンレポートを生成する。"""
    lines = []
    lines.append("# Workflow Analysis Report")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **sessions.jsonl レコード数**: {session_count}")
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

    # セッション分析
    lines.append("## 5. セッション分析")
    lines.append("")
    sa = session_analysis
    if sa["total_sessions"] == 0:
        lines.append("*データなし*")
    else:
        lines.append(f"- **総セッション数**: {sa['total_sessions']}")
        lines.append(f"- **平均ツール呼び出し数**: {sa['avg_tool_calls']}")
        lines.append(f"- **平均セッション長**: {sa['avg_duration_minutes']} 分")
        lines.append(f"- **平均エラー数**: {sa['avg_errors']}")
        lines.append(f"- **平均 human メッセージ数**: {sa['avg_human_messages']}")
        lines.append("")
        lines.append("### セッション長の分布")
        lines.append("")
        lines.append(f"- Short (< 5分): {sa['sessions_by_duration']['short']}")
        lines.append(f"- Medium (5-30分): {sa['sessions_by_duration']['medium']}")
        lines.append(f"- Long (> 30分): {sa['sessions_by_duration']['long']}")
        lines.append("")
        lines.append("### ツール分布（全セッション合計）")
        lines.append("")
        if sa["tool_distribution"]:
            lines.append("| Tool | Count |")
            lines.append("|------|-------|")
            for tool, count in sorted(sa["tool_distribution"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"| {tool} | {count} |")
        lines.append("")
        lines.append("### プロジェクト別セッション数")
        lines.append("")
        if sa["sessions_by_project"]:
            lines.append("| Project | Sessions |")
            lines.append("|---------|----------|")
            for proj, count in sorted(sa["sessions_by_project"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"| {proj} | {count} |")
        lines.append("")
        lines.append("### ユーザー意図の分布")
        lines.append("")
        if sa["intent_distribution"]:
            lines.append("| Intent | Count |")
            lines.append("|--------|-------|")
            for intent, count in sorted(sa["intent_distribution"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"| {intent} | {count} |")
        lines.append("")

    return "\n".join(lines)


def run_analysis(project: Optional[str] = None) -> str:
    """分析を実行してマークダウンレポートを返す。

    project が指定された場合、sessions.jsonl から該当プロジェクトの
    session_id セットを取得し、全データをフィルタする。
    """
    if project is not None:
        session_ids: Optional[Set[str]] = get_project_session_ids(project)
    else:
        session_ids = None
    workflows = load_jsonl(common.DATA_DIR / "workflows.jsonl", session_ids)
    usage = load_jsonl(common.DATA_DIR / "usage.jsonl", session_ids)
    sessions = load_jsonl(common.DATA_DIR / "sessions.jsonl", session_ids)

    consistency = analyze_consistency(workflows)
    variations = analyze_variations(workflows)
    intervention = analyze_intervention(usage)
    discover_prune = analyze_discover_prune(usage)
    session_analysis = analyze_sessions(sessions)

    return format_report(
        consistency=consistency,
        variations=variations,
        intervention=intervention,
        discover_prune=discover_prune,
        session_analysis=session_analysis,
        workflow_count=len(workflows),
        usage_count=len(usage),
        session_count=len(sessions),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ワークフロー分析レポートを生成する"
    )
    parser.add_argument(
        "--project",
        default=common.project_name_from_dir(os.getcwd()),
        help="フィルタ対象のプロジェクト名（デフォルト: カレントディレクトリ名）",
    )
    args = parser.parse_args()

    report = run_analysis(project=args.project)
    print(report)


if __name__ == "__main__":
    main()
