#!/usr/bin/env python3
"""プロジェクト固有の fitness 関数テンプレート

このファイルは generate-fitness スキルによって自動生成されるスケルトンです。
Claude CLI がこのテンプレートを元に、プロジェクト分析結果に基づいて
evaluate() 関数のロジックを実装します。

インターフェース:
    - 入力: stdin からスキル/ルールの内容（Markdown テキスト）
    - 出力: stdout に 0.0〜1.0 のスコア（浮動小数点数）

使用方法:
    cat SKILL.md | python3 scripts/rl/fitness/{name}.py
    python3 optimize.py --target SKILL.md --fitness {name}
"""

import re
import sys
from typing import Dict, List, Tuple


def evaluate(content: str) -> float:
    """スキル/ルールの内容を評価し、0.0〜1.0 のスコアを返す。

    Args:
        content: スキル/ルールの Markdown テキスト

    Returns:
        0.0〜1.0 の浮動小数点数
    """
    scores: Dict[str, Tuple[float, float]] = {}  # {axis_name: (score, weight)}

    # --- ここに評価ロジックを実装 ---
    # 各評価軸について 0.0〜1.0 のスコアと重みを設定
    #
    # 例:
    # scores["clarity"] = (check_clarity(content), 0.3)
    # scores["completeness"] = (check_completeness(content), 0.25)
    # scores["structure"] = (check_structure(content), 0.25)
    # scores["practicality"] = (check_practicality(content), 0.2)
    #
    # ワークフロー統計が利用可能な場合:
    # workflow_stats = load_workflow_stats()  # ~/.claude/rl-anything/workflow_stats.json
    # if workflow_stats and skill_name in workflow_stats:
    #     ws = workflow_stats[skill_name]
    #     consistency_bonus = 0.05 if ws.get("consistency", 0) >= 0.6 else 0
    #     scores["workflow_efficiency"] = (consistency_bonus + 0.5, 0.1)

    # --- アンチパターンチェック ---
    penalty = check_anti_patterns(content)

    # --- 加重平均を計算 ---
    if not scores:
        print(
            "Warning: no scoring axes implemented, returning 0.0",
            file=sys.stderr,
        )
        return 0.0

    total = sum(score * weight for score, weight in scores.values())
    total_weight = sum(weight for _, weight in scores.values())
    weighted_avg = total / total_weight if total_weight > 0 else 0.5

    # アンチパターンのペナルティを適用（最大 -0.3）
    final = max(0.0, min(1.0, weighted_avg - penalty))
    return round(final, 3)


def check_anti_patterns(content: str) -> float:
    """アンチパターンの検出によるペナルティを計算。

    Args:
        content: スキル/ルールの Markdown テキスト

    Returns:
        0.0〜0.3 のペナルティ値
    """
    anti_patterns: List[str] = [
        # --- ここにアンチパターンを定義 ---
        # 例:
        # "曖昧な指示",
        # "矛盾する記述",
    ]

    penalty = 0.0
    content_lower = content.lower()
    for pattern in anti_patterns:
        if pattern.lower() in content_lower:
            penalty += 0.05

    return min(0.3, penalty)


def main():
    content = sys.stdin.read()
    if not content.strip():
        print("0.0")
        sys.exit(0)

    score = evaluate(content)
    print(f"{score}")


if __name__ == "__main__":
    main()
