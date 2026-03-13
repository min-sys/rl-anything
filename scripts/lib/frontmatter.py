"""汎用 YAML frontmatter パーサー / ライター。

SKILL.md / rule ファイルの YAML frontmatter を解析・更新する共通ユーティリティ。
prune.py と reflect_utils.py の両方から利用する。
"""
from pathlib import Path
from typing import Any, Dict, Tuple

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


def update_frontmatter(filepath: Path, updates: Dict[str, Any]) -> Tuple[bool, str]:
    """frontmatter のキー/値を追加・更新してファイルを書き戻す。

    Args:
        filepath: 対象ファイルのパス
        updates: 追加/更新するキー/値の辞書

    Returns:
        (success, error_message): 成功時は (True, "")、失敗時は (False, エラー詳細)
    """
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return False, str(e)

    if not text.strip():
        return False, "empty_file"

    if text.startswith("---"):
        end = text.find("---", 3)
        if end == -1:
            return False, "yaml_parse_error"

        yaml_str = text[3:end].strip()
        try:
            parsed = yaml.safe_load(yaml_str)
            if not isinstance(parsed, dict):
                parsed = {}
        except yaml.YAMLError:
            return False, "yaml_parse_error"

        parsed.update(updates)
        new_yaml = yaml.dump(parsed, default_flow_style=False, allow_unicode=True).rstrip()
        body = text[end + 3:]  # content after closing ---
        new_text = f"---\n{new_yaml}\n---{body}"
    else:
        # No existing frontmatter — add one at the top
        new_yaml = yaml.dump(updates, default_flow_style=False, allow_unicode=True).rstrip()
        new_text = f"---\n{new_yaml}\n---\n{text}"

    try:
        filepath.write_text(new_text, encoding="utf-8")
    except OSError as e:
        return False, str(e)

    return True, ""


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
