"""行数制限チェック共通モジュール。

スキル/ルールファイルの行数上限を一元管理する Single Source of Truth。
"""
import sys

MAX_SKILL_LINES = 500
MAX_RULE_LINES = 3


def check_line_limit(target_path: str, content: str) -> bool:
    """行数制限をチェック。超過時は stderr に警告を出して False を返す。

    Args:
        target_path: 対象ファイルのパス文字列
        content: ファイル内容

    Returns:
        行数制限内なら True、超過なら False
    """
    is_rule = ".claude/rules/" in target_path
    max_lines = MAX_RULE_LINES if is_rule else MAX_SKILL_LINES
    lines = content.count("\n") + 1
    if lines > max_lines:
        file_type = "ルール" if is_rule else "スキル"
        print(
            f"  行数超過: {lines}/{max_lines}行（{file_type}制限）。適用を拒否。",
            file=sys.stderr,
        )
        return False
    return True
