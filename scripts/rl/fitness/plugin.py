#!/usr/bin/env python3
"""rl-anything プロジェクト固有の fitness 関数

品質基準:
- LLM呼び出しを最小化し、ルールベース処理を優先 (weight: 0.3)
- べき等性が保証されていること (weight: 0.3)
- ユーザー承認なしの自動変更を行わないこと (weight: 0.2)
- 既存インターフェース（stdin→stdout）との互換性 (weight: 0.2)

インターフェース:
    - 入力: stdin からスキル/ルールの内容（Markdown テキスト）
    - 出力: stdout に 0.0〜1.0 のスコア（浮動小数点数）
"""

import re
import sys
from typing import Dict, List, Tuple


def evaluate(content: str) -> float:
    """スキル/ルールの内容を評価し、0.0〜1.0 のスコアを返す。"""
    scores: Dict[str, Tuple[float, float]] = {}

    # 軸1: LLM呼び出し最小化・ルールベース処理優先 (weight: 0.3)
    scores["llm_minimization"] = (check_llm_minimization(content), 0.3)

    # 軸2: べき等性の保証 (weight: 0.3)
    scores["idempotency"] = (check_idempotency(content), 0.3)

    # 軸3: ユーザー承認フロー (weight: 0.2)
    scores["user_approval"] = (check_user_approval(content), 0.2)

    # 軸4: 既存インターフェース互換性 (weight: 0.2)
    scores["interface_compat"] = (check_interface_compat(content), 0.2)

    # アンチパターンチェック
    penalty = check_anti_patterns(content)

    total = sum(score * weight for score, weight in scores.values())
    total_weight = sum(weight for _, weight in scores.values())
    weighted_avg = total / total_weight if total_weight > 0 else 0.5

    final = max(0.0, min(1.0, weighted_avg - penalty))
    return round(final, 3)


def check_llm_minimization(content: str) -> float:
    """LLM呼び出しを最小化し、ルールベース処理を優先しているか。"""
    score = 0.5  # ベースライン

    content_lower = content.lower()

    # ルールベース処理のキーワード（加点）
    rule_based_keywords = [
        "ルールベース", "rule-based", "rule based",
        "正規表現", "regex", "re\\.", "パターンマッチ",
        "json", "jsonl", "stdin", "stdout",
        "python3", "scripts/", "スクリプト",
    ]
    for kw in rule_based_keywords:
        if kw in content_lower:
            score += 0.05

    # LLM依存のキーワード（減点）
    llm_keywords = [
        "claude -p", "claude --print",
        "llm", "gpt", "openai",
        "api呼び出し", "api call",
    ]
    for kw in llm_keywords:
        if kw in content_lower:
            score -= 0.1

    # 「型Aパターン: LLM呼び出しなし」への言及（加点）
    if "型a" in content_lower or "llm 呼び出しなし" in content_lower:
        score += 0.15

    return max(0.0, min(1.0, score))


def check_idempotency(content: str) -> float:
    """べき等性が保証されているか。"""
    score = 0.5

    content_lower = content.lower()

    # べき等性に関するキーワード（加点）
    idempotency_keywords = [
        "べき等", "idempoten", "冪等",
        "連続実行", "重複", "duplicate",
        "前回以降", "新規データのみ",
        "スキップ", "skip",
    ]
    for kw in idempotency_keywords:
        if kw in content_lower:
            score += 0.08

    # 状態管理のキーワード（加点）
    state_keywords = [
        "last_run", "timestamp", "checkpoint",
        "前回実行", "state", "状態",
    ]
    for kw in state_keywords:
        if kw in content_lower:
            score += 0.05

    return max(0.0, min(1.0, score))


def check_user_approval(content: str) -> float:
    """ユーザー承認なしの自動変更を行わない設計か。"""
    score = 0.5

    content_lower = content.lower()

    # ユーザー承認フローのキーワード（加点）
    approval_keywords = [
        "askuserquestion", "ask user",
        "ユーザーに", "承認", "確認",
        "提案", "propose", "proposed",
        "must", "対話的",
    ]
    for kw in approval_keywords:
        if kw in content_lower:
            score += 0.06

    # 自動変更の危険キーワード（減点）
    auto_change_keywords = [
        "自動的に変更", "自動で上書き",
        "確認なしに", "without confirmation",
    ]
    for kw in auto_change_keywords:
        if kw in content_lower:
            score -= 0.15

    return max(0.0, min(1.0, score))


def check_interface_compat(content: str) -> float:
    """既存インターフェース（stdin→stdout）との互換性。"""
    score = 0.5

    content_lower = content.lower()

    # 標準インターフェースのキーワード（加点）
    compat_keywords = [
        "stdin", "stdout", "json",
        "インターフェース", "interface",
        "互換", "compat",
        "0.0〜1.0", "0.0-1.0",
    ]
    for kw in compat_keywords:
        if kw in content_lower:
            score += 0.06

    # CLI互換のキーワード（加点）
    cli_keywords = [
        "--dry-run", "--project-dir", "--fitness",
        "argparse", "引数", "argument",
    ]
    for kw in cli_keywords:
        if kw in content_lower:
            score += 0.04

    return max(0.0, min(1.0, score))


def check_anti_patterns(content: str) -> float:
    """アンチパターンの検出によるペナルティ。"""
    anti_patterns: List[str] = [
        "hardcoded",
        "ハードコード",
        "magic number",
        "todo: fix",
        "hack",
        "workaround",
    ]

    penalty = 0.0
    content_lower = content.lower()
    for pattern in anti_patterns:
        if pattern in content_lower:
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
