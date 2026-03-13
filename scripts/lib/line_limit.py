"""行数制限チェック共通モジュール。

スキル/ルールファイルの行数上限を一元管理する Single Source of Truth。
"""
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

MAX_SKILL_LINES = 500
MAX_RULE_LINES = 3
MAX_PROJECT_RULE_LINES = 5
CLAUDEMD_WARNING_LINES = 300


@dataclass
class SeparationProposal:
    """rule 行数超過時の分離提案。"""

    target_path: str
    reference_path: str
    summary_template: str
    excess_lines: int


def _is_global_rule(target_path: str) -> bool:
    """グローバルルール（~/.claude/rules/ 配下）かどうかを判定する。"""
    home = str(Path.home())
    return target_path.startswith(home) and ".claude/rules/" in target_path


def check_line_limit(target_path: str, content: str) -> bool:
    """行数制限をチェック。超過時は stderr に警告を出して False を返す。

    Args:
        target_path: 対象ファイルのパス文字列
        content: ファイル内容

    Returns:
        行数制限内なら True、超過なら False
    """
    is_rule = ".claude/rules/" in target_path
    if is_rule:
        if _is_global_rule(target_path):
            max_lines = MAX_RULE_LINES
        else:
            max_lines = MAX_PROJECT_RULE_LINES
    else:
        max_lines = MAX_SKILL_LINES
    lines = content.count("\n") + 1
    if lines > max_lines:
        file_type = "ルール" if is_rule else "スキル"
        print(
            f"  行数超過: {lines}/{max_lines}行（{file_type}制限）。適用を拒否。",
            file=sys.stderr,
        )
        return False
    return True


def _resolve_reference_path(rule_path: Path) -> Path:
    """rule ファイルから分離先の references ディレクトリパスを決定する。"""
    rules_dir = rule_path.parent
    return rules_dir.parent / "references" / rule_path.name


def _deduplicate_path(ref_path: Path) -> Path:
    """既存ファイルと衝突しない参照先パスを返す。"""
    if not ref_path.exists():
        return ref_path
    stem = ref_path.stem
    suffix = ref_path.suffix
    parent = ref_path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def suggest_separation(
    target_path: str, content: str
) -> Optional[SeparationProposal]:
    """rule 行数超過時の分離提案を生成する。

    rule ファイルが行数制限を超過している場合に分離先パスと
    要約テンプレートを含む SeparationProposal を返す。
    rule 以外のファイルや制限内の場合は None を返す。
    """
    if ".claude/rules/" not in target_path:
        return None

    is_global = _is_global_rule(target_path)
    max_lines = MAX_RULE_LINES if is_global else MAX_PROJECT_RULE_LINES
    lines = content.count("\n") + 1
    excess = lines - max_lines

    if excess <= 0:
        return None

    rule_path = Path(target_path)
    ref_path = _resolve_reference_path(rule_path)
    ref_path = _deduplicate_path(ref_path)

    rel_ref = ref_path.name
    summary_template = (
        f"# {rule_path.stem}\n"
        f"詳細は [references/{rel_ref}](../references/{rel_ref}) を参照。"
    )

    return SeparationProposal(
        target_path=target_path,
        reference_path=str(ref_path),
        summary_template=summary_template,
        excess_lines=excess,
    )
