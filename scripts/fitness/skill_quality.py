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

# ── CSO (Claude Search Optimization) 定数 ──────────────────
CSO_WEIGHT = 0.15
CSO_SUMMARY_THRESHOLD = 0.5
CSO_ACTION_BONUS = 0.1
CSO_MAX_DESCRIPTION_LENGTH = 1024
CSO_LENGTH_PENALTY = -0.1

# frontmatter パーサー
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# 行動促進パターン
_CSO_ACTION_PATTERNS = re.compile(
    r"(?:Use (?:when|this skill when|this agent when)|"
    r"Trigger[:\s]|"
    r"トリガー[:\s]|"
    r"使用タイミング[:\s]|"
    r"以下の場合に使用)",
    re.IGNORECASE,
)


def _tokenize(text: str) -> set:
    """簡易トークナイザー（CSO 類似度計算用）。"""
    return set(re.findall(r"\w{2,}", text.lower()))


def _evaluate_cso(content: str) -> float:
    """CSO 軸のスコアを 0.0〜1.0 で返す。

    frontmatter の description を対象に、要約ペナルティ・行動促進ボーナス・
    長さペナルティを評価する。content ベースで動作する（ファイルパス不要）。
    """
    cso = 0.5  # ベーススコア

    # frontmatter から description を抽出
    fm_match = _FRONTMATTER_RE.match(content)
    if not fm_match:
        return 0.0
    description = ""
    for line in fm_match.group(1).splitlines():
        if line.strip().startswith("description:"):
            _, _, val = line.partition(":")
            description = val.strip().strip('"').strip("'")
            break
    if not description:
        return 0.0

    # 1. 要約ペナルティ: description vs 本文冒頭の Jaccard 類似度
    body = _FRONTMATTER_RE.sub("", content).strip()
    first_para_lines = []
    for line in body.splitlines():
        if not line.strip():
            if first_para_lines:
                break
            continue
        first_para_lines.append(line)
    first_paragraph = " ".join(first_para_lines)

    if first_paragraph:
        desc_tokens = _tokenize(description)
        para_tokens = _tokenize(first_paragraph)
        if desc_tokens and para_tokens:
            intersection = desc_tokens & para_tokens
            union = desc_tokens | para_tokens
            similarity = len(intersection) / len(union) if union else 0.0
            if similarity > CSO_SUMMARY_THRESHOLD:
                cso -= 0.2

    # 2. 行動促進ボーナス
    if _CSO_ACTION_PATTERNS.search(description):
        cso += CSO_ACTION_BONUS

    # 3. 長さペナルティ
    if len(description) > CSO_MAX_DESCRIPTION_LENGTH:
        cso += CSO_LENGTH_PENALTY

    return max(0.0, min(1.0, cso))


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

    # --- 8. CSO (Claude Search Optimization) (CSO_WEIGHT) ---
    max_score += CSO_WEIGHT
    cso_score = _evaluate_cso(content)
    score += CSO_WEIGHT * cso_score

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
