"""汎用 YAML frontmatter パーサー。

SKILL.md / rule ファイルの YAML frontmatter を解析する共通ユーティリティ。
prune.py と reflect_utils.py の両方から利用する。
"""
from pathlib import Path
from typing import Any, Dict

import yaml


def parse_frontmatter(filepath: Path) -> Dict[str, Any]:
    """YAML frontmatter（--- 区切り）を辞書として返す。

    Args:
        filepath: 対象ファイルのパス

    Returns:
        frontmatter の辞書。frontmatter がなければ空辞書。
    """
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    if not text.startswith("---"):
        return {}

    end = text.find("---", 3)
    if end == -1:
        return {}

    yaml_str = text[3:end].strip()
    if not yaml_str:
        return {}

    try:
        parsed = yaml.safe_load(yaml_str)
        return parsed if isinstance(parsed, dict) else {}
    except yaml.YAMLError:
        return {}


def extract_description(filepath: Path) -> str:
    """frontmatter から description を抽出する。multiline の場合は1行目のみ返す。

    Args:
        filepath: 対象ファイルのパス

    Returns:
        description 文字列。取得不可の場合は空文字。
    """
    fm = parse_frontmatter(filepath)
    desc = fm.get("description", "")
    if not isinstance(desc, str):
        desc = str(desc) if desc is not None else ""
    # multiline 対応: 1行目のみ返す
    first_line = desc.strip().split("\n")[0].strip() if desc.strip() else ""
    return first_line
