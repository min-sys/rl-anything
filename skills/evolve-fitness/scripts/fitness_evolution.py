#!/usr/bin/env python3
"""評価関数の自己成長スクリプト。

score-acceptance 相関追跡、rejection_reason 分析、欠落軸提案、
adversarial probe を行い、fitness function の改善を提案する。

human_accepted / rejection_reason のデータは
optimize スキルの history.jsonl（SSoT）を参照する。
"""
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HISTORY_DIR = (
    Path(__file__).parent.parent
    / "skills"
    / "genetic-prompt-optimizer"
    / "scripts"
    / "generations"
)

MIN_DATA_COUNT = 30
BOOTSTRAP_MIN = 5
CORRELATION_WINDOW = 20
CORRELATION_THRESHOLD = 0.50
REJECTION_PATTERN_THRESHOLD = 3


def load_history() -> List[Dict[str, Any]]:
    """optimize スキルの history.jsonl（SSoT）を読み込む。"""
    history_file = HISTORY_DIR / "history.jsonl"
    if not history_file.exists():
        return []

    records = []
    for line in history_file.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def compute_correlation(
    scores: List[float], accepted: List[bool]
) -> Optional[float]:
    """score と accepted のピアソン相関係数を計算する。

    直近20件に満たない場合、計算をスキップし次回に持ち越す（MUST）。
    """
    if len(scores) < CORRELATION_WINDOW:
        return None

    # 直近20件のみ使用
    scores = scores[-CORRELATION_WINDOW:]
    accepted_float = [1.0 if a else 0.0 for a in accepted[-CORRELATION_WINDOW:]]

    n = len(scores)
    mean_x = sum(scores) / n
    mean_y = sum(accepted_float) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(scores, accepted_float)) / n
    std_x = math.sqrt(sum((x - mean_x) ** 2 for x in scores) / n)
    std_y = math.sqrt(sum((y - mean_y) ** 2 for y in accepted_float) / n)

    if std_x == 0 or std_y == 0:
        return 0.0

    return cov / (std_x * std_y)


def analyze_correlations(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """score-acceptance 相関を分析する。"""
    scores = []
    accepted = []

    for rec in history:
        fitness = rec.get("best_fitness")
        ha = rec.get("human_accepted")
        if fitness is not None and ha is not None:
            scores.append(fitness)
            accepted.append(ha)

    corr = compute_correlation(scores, accepted)

    result: Dict[str, Any] = {
        "data_points": len(scores),
        "correlation": corr,
        "sufficient_data": len(scores) >= CORRELATION_WINDOW,
    }

    if corr is not None and corr < CORRELATION_THRESHOLD:
        result["warning"] = (
            f"score-acceptance 相関が {corr:.3f} (< {CORRELATION_THRESHOLD}) に低下。"
            "評価関数の再キャリブレーション推奨。"
        )

    return result


def analyze_rejection_reasons(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """rejection_reason の頻度分析から欠落評価軸を検出する。"""
    counter: Counter = Counter()
    for rec in history:
        reason = rec.get("rejection_reason")
        if reason:
            counter[reason] += 1

    frequent = []
    for reason, count in counter.most_common():
        if count >= REJECTION_PATTERN_THRESHOLD:
            frequent.append({"reason": reason, "count": count})

    proposals = []
    if frequent:
        for item in frequent:
            proposals.append({
                "type": "missing_axis",
                "reason": item["reason"],
                "count": item["count"],
                "proposal": f"評価軸追加提案: '{item['reason']}' に対応する新しい軸",
            })

    return {
        "total_rejections": sum(counter.values()),
        "frequent_patterns": frequent,
        "proposals": proposals,
    }


def get_adversarial_templates() -> List[Dict[str, str]]:
    """adversarial probe 用テンプレート辞書の提供。

    実際の候補生成は Claude CLI で行う。ここではプロンプトテンプレートを返す。
    """
    return [
        {
            "name": "score_maximizer",
            "description": "スコアを最大化するが実用性が低い候補",
            "prompt_hint": "全ての評価基準のキーワードを含むが中身のない候補を生成",
        },
        {
            "name": "length_gamer",
            "description": "行数制限ギリギリの冗長な候補",
            "prompt_hint": "制限行数ちょうどの冗長な候補を生成",
        },
        {
            "name": "template_repeater",
            "description": "テンプレートをそのまま繰り返す候補",
            "prompt_hint": "既存パターンを機械的に繰り返す候補を生成",
        },
    ]


def run_fitness_evolution(history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """評価関数の改善レポートを生成する。"""
    if history is None:
        history = load_history()

    # データ十分性チェック
    decisions = [r for r in history if r.get("human_accepted") is not None]

    if len(decisions) < BOOTSTRAP_MIN:
        return {
            "status": "insufficient_data",
            "data_count": len(decisions),
            "required": MIN_DATA_COUNT,
            "message": f"データ不足: {len(decisions)}/{MIN_DATA_COUNT}件。"
                       f"あと {MIN_DATA_COUNT - len(decisions)} 件の accept/reject が必要。",
        }

    if len(decisions) < MIN_DATA_COUNT:
        # Bootstrap モード: 簡易分析
        scores = [r.get("best_fitness", 0.0) for r in decisions if r.get("best_fitness") is not None]
        accepted_count = sum(1 for d in decisions if d.get("human_accepted"))
        approval_rate = accepted_count / len(decisions) if decisions else 0.0
        mean_score = sum(scores) / len(scores) if scores else 0.0

        # スコア分布
        score_distribution = {}
        if scores:
            score_distribution = {
                "min": min(scores),
                "max": max(scores),
                "mean": mean_score,
                "median": sorted(scores)[len(scores) // 2],
            }

        return {
            "status": "bootstrap",
            "data_count": len(decisions),
            "required": MIN_DATA_COUNT,
            "message": f"簡易分析モード ({len(decisions)}/{MIN_DATA_COUNT}件)",
            "bootstrap_analysis": {
                "approval_rate": approval_rate,
                "mean_score": mean_score,
                "score_distribution": score_distribution,
            },
        }

    # 完全分析
    correlation = analyze_correlations(history)
    rejections = analyze_rejection_reasons(history)
    adversarial = get_adversarial_templates()

    return {
        "status": "ready",
        "data_count": len(decisions),
        "correlation": correlation,
        "rejections": rejections,
        "adversarial_candidates": adversarial,
    }


if __name__ == "__main__":
    result = run_fitness_evolution()
    print(json.dumps(result, ensure_ascii=False, indent=2))
