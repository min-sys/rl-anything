#!/usr/bin/env python3
"""汎用スキル品質の適応度関数。

stdin からスキル内容を受け取り、0.0〜1.0 のスコアを stdout に出力。
プロジェクト非依存の汎用評価。

評価基準:
- 構造の整理（見出し・セクション）
- 具体例の存在
- コード例の存在
- NG/OK 対比の存在
- 適切な長さ
"""

import re
import sys


def evaluate(content: str) -> float:
    """スキル内容を評価し、0.0〜1.0 のスコアを返す"""
    score = 0.0
    max_score = 0.0

    # --- 1. 構造の整理（見出しの数、セクション） (0.20) ---
    max_score += 0.20
    headings = re.findall(r"^#{1,3}\s+.+", content, re.MULTILINE)
    if len(headings) >= 7:
        score += 0.20
    elif len(headings) >= 5:
        score += 0.15
    elif len(headings) >= 3:
        score += 0.10
    elif len(headings) >= 1:
        score += 0.05

    # --- 2. frontmatter の存在 (0.10) ---
    max_score += 0.10
    if content.strip().startswith("---"):
        # frontmatter に name または description があるか
        fm_match = re.match(r"---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            has_name = "name:" in fm
            has_desc = "description:" in fm or "description: |" in fm
            if has_name and has_desc:
                score += 0.10
            elif has_name or has_desc:
                score += 0.06

    # --- 3. 具体例の存在 (0.20) ---
    max_score += 0.20
    # コードブロック
    code_blocks = re.findall(r"```\w*\n", content)
    # 引用例（「」または > ）
    quoted_examples = re.findall(r"「[^」]{3,}」", content)
    example_count = len(code_blocks) + len(quoted_examples)
    if example_count >= 5:
        score += 0.20
    elif example_count >= 3:
        score += 0.15
    elif example_count >= 1:
        score += 0.08

    # --- 4. NG/OK 対比の存在 (0.15) ---
    max_score += 0.15
    has_ng = bool(re.search(r"[❌✗]|NG|悪い例|改善前|Before", content))
    has_ok = bool(re.search(r"[✅✓]|OK|良い例|改善後|After", content))
    has_table_comparison = bool(re.search(r"\|.*\|.*\|", content))
    contrast_score = sum([has_ng, has_ok, has_table_comparison])
    if contrast_score >= 2:
        score += 0.15
    elif contrast_score >= 1:
        score += 0.08

    # --- 5. 適切な長さ (0.15) ---
    max_score += 0.15
    lines = content.count("\n") + 1
    if 100 <= lines <= 500:
        score += 0.15
    elif 50 <= lines <= 100 or 500 < lines <= 700:
        score += 0.10
    elif 20 <= lines <= 50:
        score += 0.05
    # 短すぎる or 長すぎる → 0

    # --- 6. 引数・設定の文書化 (0.10) ---
    max_score += 0.10
    has_args_section = bool(re.search(r"^#{1,3}\s+.*(引数|Arguments|パラメータ|Parameters)", content, re.MULTILINE))
    has_table = bool(re.search(r"\|.*\|.*\|.*\|", content))
    if has_args_section and has_table:
        score += 0.10
    elif has_args_section or has_table:
        score += 0.05

    # --- 7. ワークフロー・手順の記述 (0.10) ---
    max_score += 0.10
    has_steps = bool(re.search(r"(Step\s+\d|ステップ\s*\d|手順|ワークフロー)", content, re.IGNORECASE))
    has_numbered_list = len(re.findall(r"^\d+\.\s+", content, re.MULTILINE)) >= 3
    if has_steps and has_numbered_list:
        score += 0.10
    elif has_steps or has_numbered_list:
        score += 0.05

    # スコアを 0.0〜1.0 に正規化
    return round(min(score / max_score, 1.0) if max_score > 0 else 0.0, 3)


def main():
    """stdin からスキル内容を読み込み、スコアを stdout に出力"""
    content = sys.stdin.read()
    if not content.strip():
        print("0.0")
        return

    score = evaluate(content)
    print(f"{score}")


if __name__ == "__main__":
    main()
