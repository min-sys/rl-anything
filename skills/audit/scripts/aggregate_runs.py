#!/usr/bin/env python3
"""クロスラン集計スクリプト。

複数の optimize/rl-loop 実行結果を集計し、
戦略別（elite/mutation/crossover）の有効性・スコア推移・accept/reject 比率を出力する。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

GENERATIONS_DIR = Path(__file__).parent.parent / "skills" / "genetic-prompt-optimizer" / "scripts" / "generations"
RL_LOOP_DIR = Path.cwd() / ".rl-loop"


def load_generation_data() -> List[Dict[str, Any]]:
    """generations/ から全ランの個体データを収集する。"""
    records = []
    if not GENERATIONS_DIR.exists():
        return records

    for run_dir in GENERATIONS_DIR.iterdir():
        if not run_dir.is_dir():
            continue
        for gen_dir in sorted(run_dir.iterdir()):
            if not gen_dir.is_dir() or not gen_dir.name.startswith("gen_"):
                continue
            for ind_file in gen_dir.glob("*.json"):
                try:
                    data = json.loads(ind_file.read_text(encoding="utf-8"))
                    data["run_id"] = run_dir.name
                    records.append(data)
                except (json.JSONDecodeError, OSError):
                    continue
    return records


def load_history() -> List[Dict[str, Any]]:
    """history.jsonl からデータを読み込む。"""
    history_file = GENERATIONS_DIR / "history.jsonl"
    records = []
    if history_file.exists():
        for line in history_file.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def aggregate(records: List[Dict[str, Any]], history: List[Dict[str, Any]]) -> str:
    """集計レポートを生成する。"""
    lines = ["# Cross-Run Aggregation Report", ""]

    # 戦略別スコア
    strategy_scores: Dict[str, List[float]] = defaultdict(list)
    for rec in records:
        strategy = rec.get("strategy", "unknown")
        fitness = rec.get("fitness")
        if fitness is not None:
            strategy_scores[strategy or "unknown"].append(fitness)

    if strategy_scores:
        lines.append("## Strategy Effectiveness")
        for strategy, scores in sorted(strategy_scores.items()):
            avg = sum(scores) / len(scores) if scores else 0
            lines.append(f"- {strategy}: avg={avg:.3f}, count={len(scores)}")
        lines.append("")

    # Accept/Reject 比率
    total_accepted = sum(1 for h in history if h.get("human_accepted") is True)
    total_rejected = sum(1 for h in history if h.get("human_accepted") is False)
    total_decisions = total_accepted + total_rejected

    if total_decisions > 0:
        lines.append("## Accept/Reject Ratio")
        lines.append(f"- Accepted: {total_accepted}/{total_decisions} ({total_accepted/total_decisions*100:.0f}%)")
        lines.append(f"- Rejected: {total_rejected}/{total_decisions} ({total_rejected/total_decisions*100:.0f}%)")
        lines.append("")

    # Rejection reasons
    reasons: Dict[str, int] = defaultdict(int)
    for h in history:
        reason = h.get("rejection_reason")
        if reason:
            reasons[reason] += 1

    if reasons:
        lines.append("## Top Rejection Reasons")
        for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"- [{count}x] {reason}")
        lines.append("")

    # スコア推移
    if history:
        lines.append("## Score Trend")
        for h in history[-10:]:
            status = "accepted" if h.get("human_accepted") else "rejected" if h.get("human_accepted") is False else "pending"
            lines.append(
                f"- {h.get('run_id', '?')}: "
                f"fitness={h.get('best_fitness', '?')}, "
                f"strategy={h.get('best_strategy', '?')}, "
                f"{status}"
            )
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    records = load_generation_data()
    history = load_history()
    print(aggregate(records, history))
