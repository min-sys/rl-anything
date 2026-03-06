"""ツール利用分析モジュール。

セッション JSONL からツール呼び出しを抽出・分類し、
discover / audit 向けの分析結果を提供する。
"""
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

REPEATING_THRESHOLD = 5

# Built-in 代替可能コマンド → 推奨ツール
BUILTIN_REPLACEABLE_MAP = {
    "cat": "Read",
    "grep": "Grep",
    "rg": "Grep",
    "find": "Glob",
    "head": "Read",
    "tail": "Read",
    "wc": "Read",
    "sed": "Edit",
    "awk": "Edit",
}


def _resolve_session_dir(
    project_root: Optional[Path] = None,
    projects_dir: Optional[Path] = None,
) -> Optional[Path]:
    """project_root からセッション JSONL のディレクトリを解決する。"""
    if projects_dir is None:
        projects_dir = CLAUDE_PROJECTS_DIR

    if not projects_dir.is_dir():
        return None

    if project_root is None:
        return None

    # プロジェクト名から slug を探索（discover.py と同パターン）
    project_name = project_root.name
    for d in projects_dir.iterdir():
        if d.is_dir() and d.name.endswith(project_name):
            return d

    return None


def extract_tool_calls(
    project_root: Optional[Path] = None,
    *,
    projects_dir: Optional[Path] = None,
) -> Tuple[Counter, List[str]]:
    """セッション JSONL からツール呼び出しを抽出する。

    Returns:
        (tool_counts, bash_commands): ツール名別カウントと Bash コマンド文字列リスト
    """
    session_dir = _resolve_session_dir(project_root, projects_dir)
    if session_dir is None:
        return Counter(), []

    tool_counts: Counter = Counter()
    bash_commands: List[str] = []

    for session_file in session_dir.glob("*.jsonl"):
        try:
            text = session_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for line in text.splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            if rec.get("type") != "assistant":
                continue

            msg = rec.get("message", {})
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue

            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "tool_use":
                    continue

                name = item.get("name", "")
                tool_counts[name] += 1

                if name == "Bash":
                    cmd = item.get("input", {}).get("command", "")
                    if cmd:
                        bash_commands.append(cmd)

    return tool_counts, bash_commands


def _is_cat_replaceable(command: str) -> bool:
    """cat コマンドが Read 代替可能かどうかを判定する。

    heredoc (<<) やリダイレクト出力 (>, >>) がある場合は除外。
    """
    if "<<" in command:
        return False
    # リダイレクト出力の検出（> だが >> も含む、ただしパイプ後の > は含む）
    # シンプルに: コマンド文字列に > が含まれ、それが stderr redirect (2>) でもパイプ後でもない場合
    # → design の方針: シンプルな文字列マッチで十分
    for i, ch in enumerate(command):
        if ch == ">" and i > 0 and command[i - 1] != "|" and command[i - 1] != "2":
            return False
        if ch == ">" and i == 0:
            return False
    return True


def _get_command_head(command: str) -> str:
    """コマンド文字列から先頭語を取得する。"""
    parts = command.strip().split()
    if not parts:
        return ""
    # env や sudo をスキップ
    idx = 0
    while idx < len(parts) and parts[idx] in ("env", "sudo"):
        idx += 1
    return parts[idx] if idx < len(parts) else ""


def classify_bash_commands(
    commands: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """Bash コマンドを3カテゴリに分類する。

    Returns:
        {
            "builtin_replaceable": [{"command": ..., "head": ..., "alternative": ...}],
            "repeating_pattern": [],  # detect_repeating_commands で後処理
            "cli_legitimate": [{"command": ..., "head": ...}],
        }
    """
    result: Dict[str, List[Dict[str, Any]]] = {
        "builtin_replaceable": [],
        "repeating_pattern": [],
        "cli_legitimate": [],
    }

    for cmd in commands:
        head = _get_command_head(cmd)
        if not head:
            continue

        if head in BUILTIN_REPLACEABLE_MAP:
            # cat の特殊ルール
            if head == "cat" and not _is_cat_replaceable(cmd):
                result["cli_legitimate"].append({"command": cmd, "head": head})
            else:
                result["builtin_replaceable"].append({
                    "command": cmd,
                    "head": head,
                    "alternative": BUILTIN_REPLACEABLE_MAP[head],
                })
        else:
            result["cli_legitimate"].append({"command": cmd, "head": head})

    return result


def _get_command_key(command: str) -> str:
    """コマンドの「先頭語 + サブコマンド」キーを生成する。"""
    parts = command.strip().split()
    if not parts:
        return ""

    idx = 0
    while idx < len(parts) and parts[idx] in ("env", "sudo"):
        idx += 1

    if idx >= len(parts):
        return ""

    head = parts[idx]

    # サブコマンドがあれば2語目も取得
    if idx + 1 < len(parts):
        sub = parts[idx + 1]
        # オプション（-で始まる）はスキップ
        if not sub.startswith("-"):
            return f"{head} {sub}"

    return head


def detect_repeating_commands(
    commands: List[str],
    threshold: int = REPEATING_THRESHOLD,
) -> List[Dict[str, Any]]:
    """繰り返しパターンを検出する。

    先頭語+サブコマンドでグルーピングし、閾値以上のパターンを返す。
    """
    key_counter: Counter = Counter()
    key_examples: Dict[str, List[str]] = defaultdict(list)

    for cmd in commands:
        key = _get_command_key(cmd)
        if not key:
            continue
        key_counter[key] += 1
        if len(key_examples[key]) < 3:
            key_examples[key].append(cmd)

    patterns = []
    for key, count in key_counter.most_common():
        if count >= threshold:
            head = key.split()[0]
            # サブカテゴリ分類
            subcategory = _classify_subcategory(head, key)
            patterns.append({
                "pattern": key,
                "count": count,
                "subcategory": subcategory,
                "examples": key_examples[key],
            })

    return patterns


def _classify_subcategory(head: str, key: str) -> str:
    """先頭語からサブカテゴリを推定する。"""
    if head == "python3":
        if "pytest" in key:
            return "pytest"
        return "script"
    if head == "git":
        return "vcs"
    if head == "gh":
        return "github"
    if head in ("npm", "npx", "yarn", "pnpm", "bun"):
        return "package_manager"
    if head in ("pip", "pip3", "uv"):
        return "python_package"
    if head in ("docker", "docker-compose"):
        return "container"
    if head in ("aws", "cdk"):
        return "cloud"
    return "cli"


def analyze_tool_usage(
    project_root: Optional[Path] = None,
    threshold: int = REPEATING_THRESHOLD,
    *,
    projects_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """ツール利用分析を一括実行する。

    Returns:
        discover 向けの結果辞書
    """
    tool_counts, bash_commands = extract_tool_calls(
        project_root, projects_dir=projects_dir,
    )

    if not tool_counts:
        return {
            "builtin_replaceable": [],
            "repeating_patterns": [],
            "cli_summary": {},
            "total_tool_calls": 0,
            "bash_calls": 0,
        }

    classified = classify_bash_commands(bash_commands)
    repeating = detect_repeating_commands(bash_commands, threshold=threshold)

    # builtin_replaceable をサマリ化
    replaceable_summary: Counter = Counter()
    for item in classified["builtin_replaceable"]:
        replaceable_summary[f"{item['head']} → {item['alternative']}"] += 1

    builtin_replaceable = [
        {"pattern": pattern, "count": count}
        for pattern, count in replaceable_summary.most_common()
    ]

    # CLI サマリ
    cli_counter: Counter = Counter()
    for item in classified["cli_legitimate"]:
        cli_counter[item["head"]] += 1

    return {
        "builtin_replaceable": builtin_replaceable,
        "repeating_patterns": repeating,
        "cli_summary": dict(cli_counter.most_common(10)),
        "total_tool_calls": sum(tool_counts.values()),
        "bash_calls": tool_counts.get("Bash", 0),
    }
