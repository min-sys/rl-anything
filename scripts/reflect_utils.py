#!/usr/bin/env python3
"""8層メモリ階層ルーティングユーティリティ。

claude-reflect の reflect_utils.py から移植。
corrections を適切な CLAUDE.md / rules / auto-memory にルーティングする。
"""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from lib.frontmatter import parse_frontmatter as _parse_rule_frontmatter  # noqa: F401 — 共通化済み
from lib.skill_triggers import extract_skill_triggers

# Auto-memory トピック分類キーワード
_AUTO_MEMORY_TOPICS = {
    "model-preferences": ["gpt-", "claude-", "gemini-", "o3", "o4", "model", "llm"],
    "tool-usage": ["mcp", "tool", "plugin", "api", "endpoint"],
    "coding-style": ["indent", "format", "style", "naming", "convention", "lint"],
    "environment": ["venv", "env", "docker", "port", "database", "redis", "postgres"],
    "workflow": ["commit", "deploy", "test", "build", "ci", "cd", "pipeline"],
    "debugging": ["debug", "error", "log", "trace", "breakpoint"],
}

# モデル名キーワード
_MODEL_KEYWORDS = [
    "gpt-", "claude-", "gemini-", "o3", "o4", "model", "llm",
    "sonnet", "opus", "haiku",
]


def find_claude_files(project_root: Optional[Path] = None) -> Dict[str, List[Path]]:
    """8層メモリ階層のファイルパスを探索して返す。

    Args:
        project_root: プロジェクトルート。None の場合は cwd を使用。

    Returns:
        層名 → ファイルパスリストの辞書。
    """
    root = project_root or Path.cwd()
    home = Path.home()
    result: Dict[str, List[Path]] = {
        "global": [],
        "root": [],
        "local": [],
        "subdirectory": [],
        "rule": [],
        "user-rule": [],
        "auto-memory": [],
        "skill": [],
    }

    # global: ~/.claude/CLAUDE.md
    global_file = home / ".claude" / "CLAUDE.md"
    if global_file.exists():
        result["global"].append(global_file)

    # root: ./CLAUDE.md
    root_file = root / "CLAUDE.md"
    if root_file.exists():
        result["root"].append(root_file)

    # local: ./CLAUDE.local.md
    local_file = root / "CLAUDE.local.md"
    if local_file.exists():
        result["local"].append(local_file)

    # subdirectory: ./**/CLAUDE.md (root 直下は除外)
    for p in root.rglob("CLAUDE.md"):
        if p == root_file:
            continue
        # .claude ディレクトリ内は除外
        try:
            p.relative_to(root / ".claude")
            continue
        except ValueError:
            pass
        result["subdirectory"].append(p)

    # rule: ./.claude/rules/*.md
    rules_dir = root / ".claude" / "rules"
    if rules_dir.is_dir():
        result["rule"] = sorted(rules_dir.glob("*.md"))

    # user-rule: ~/.claude/rules/*.md
    user_rules_dir = home / ".claude" / "rules"
    if user_rules_dir.is_dir():
        result["user-rule"] = sorted(user_rules_dir.glob("*.md"))

    # auto-memory: ~/.claude/projects/<project>/memory/*.md
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", str(root))
    # Claude Code の auto-memory パスは project_dir を "-" 区切りにエンコード
    encoded = project_dir.replace("/", "-")
    # 先頭ハイフンあり/なし両方を試す（Claude Code バージョンにより異なる）
    for candidate in [encoded, encoded.lstrip("-")]:
        memory_dir = home / ".claude" / "projects" / candidate / "memory"
        if memory_dir.is_dir():
            result["auto-memory"] = sorted(memory_dir.glob("*.md"))
            break

    # skill: ./.claude/commands/*/SKILL.md
    commands_dir = root / ".claude" / "commands"
    if commands_dir.is_dir():
        for skill_dir in sorted(commands_dir.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                result["skill"].append(skill_file)

    return result


def detect_project_signals(
    message: str,
    project_root: Optional[Path] = None,
) -> bool:
    """correction テキストにプロジェクト固有のシグナルが含まれるかを判定する。

    シグナル:
    - CLAUDE.md の Skills セクションに記載されたスキル名
    - correction テキスト内のパスがプロジェクトルートに実在するディレクトリ

    Args:
        message: correction テキスト。
        project_root: プロジェクトルート。

    Returns:
        プロジェクト固有シグナルが検出された場合 True。
    """
    root = project_root or Path.cwd()
    msg_lower = message.lower()

    # 1. CLAUDE.md のスキル名との照合
    skill_triggers = extract_skill_triggers(project_root=root)
    for entry in skill_triggers:
        skill_name = entry["skill"]
        # スキル名がメッセージに含まれるかチェック
        if skill_name.lower() in msg_lower or f"/{skill_name}".lower() in msg_lower:
            return True

    # 2. プロジェクト内の実在パスとの照合
    # メッセージ内のパスらしい文字列を抽出
    path_candidates = re.findall(r"(?:^|\s)([\w./\-]+/)", message)
    for candidate in path_candidates:
        candidate_path = root / candidate
        if candidate_path.is_dir():
            return True

    return False


def suggest_claude_file(
    correction: Dict[str, Any],
    project_root: Optional[Path] = None,
) -> Optional[Tuple[str, float]]:
    """correction のテキストからルーティング先を提案する。

    Args:
        correction: correction レコード辞書。message, correction_type, confidence 等を含む。
        project_root: プロジェクトルート。

    Returns:
        (ファイルパス文字列, confidence) のタプル。マッチなしは None。
    """
    root = project_root or Path.cwd()
    message = correction.get("message", "")
    ctype = correction.get("correction_type", "")
    confidence = correction.get("confidence", 0.5)
    msg_lower = message.lower()

    # 1. guardrail タイプ → .claude/rules/guardrails.md
    if correction.get("guardrail") or ctype == "guardrail" or correction.get("sentiment") == "guardrail":
        return (str(root / ".claude" / "rules" / "guardrails.md"), 0.90)

    # 2. プロジェクト固有シグナル → .claude/rules/
    if detect_project_signals(message, project_root=root):
        return (str(root / ".claude" / "rules" / "project-specific.md"), 0.85)

    # 3. モデル名キーワード → ~/.claude/CLAUDE.md or model-preferences rule
    if any(kw in msg_lower for kw in _MODEL_KEYWORDS):
        # model-preferences rule があればそちらを優先
        model_rule = root / ".claude" / "rules" / "model-preferences.md"
        if model_rule.exists():
            return (str(model_rule), 0.85)
        return (str(Path.home() / ".claude" / "CLAUDE.md"), 0.85)

    # 4. "always/never/prefer" → ~/.claude/CLAUDE.md (global behavior)
    if re.search(r"\b(always|never|prefer)\b", msg_lower):
        return (str(Path.home() / ".claude" / "CLAUDE.md"), 0.80)

    # 4. rule の paths: frontmatter にマッチ
    rules_dir = root / ".claude" / "rules"
    if rules_dir.is_dir():
        for rule_file in sorted(rules_dir.glob("*.md")):
            fm = _parse_rule_frontmatter(rule_file)
            paths = fm.get("paths", [])
            if isinstance(paths, str):
                paths = [paths]
            if not isinstance(paths, list):
                continue
            for p in paths:
                if isinstance(p, str) and p in msg_lower:
                    return (str(rule_file), 0.80)

    # 5. サブディレクトリ名にマッチ
    for item in sorted(root.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            claude_file = item / "CLAUDE.md"
            if claude_file.exists() and item.name.lower() in msg_lower:
                return (str(claude_file), 0.75)

    # 6. 低信頼度 (confidence < 0.75) → auto-memory
    if confidence < 0.75:
        topic = suggest_auto_memory_topic(message)
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", str(root))
        encoded = project_dir.replace("/", "-")
        # 先頭ハイフンあり/なし両方を試す（Claude Code バージョンにより異なる）
        for candidate in [encoded, encoded.lstrip("-")]:
            memory_dir = Path.home() / ".claude" / "projects" / candidate / "memory"
            if memory_dir.is_dir():
                return (str(memory_dir / f"{topic}.md"), 0.60)
        # どちらも見つからない場合はハイフンあり版をデフォルトに
        memory_dir = Path.home() / ".claude" / "projects" / encoded / "memory"
        return (str(memory_dir / f"{topic}.md"), 0.60)

    # 7. CLAUDE.local.md はユーザー選択時のみ (ここでは返さない)
    # 8. マッチなし → None
    return None


def read_auto_memory(project_path: Optional[str] = None) -> List[Dict[str, str]]:
    """auto-memory ディレクトリのファイルを読み取る。

    Args:
        project_path: プロジェクトパス。None の場合は CLAUDE_PROJECT_DIR or cwd。

    Returns:
        各ファイルの {path, topic, content} のリスト。
    """
    proj = project_path or os.environ.get("CLAUDE_PROJECT_DIR", str(Path.cwd()))
    encoded = proj.replace("/", "-")
    # 先頭ハイフンあり/なし両方を試す（Claude Code バージョンにより異なる）
    memory_dir = None
    for candidate in [encoded, encoded.lstrip("-")]:
        candidate_dir = Path.home() / ".claude" / "projects" / candidate / "memory"
        if candidate_dir.is_dir():
            memory_dir = candidate_dir
            break
    if memory_dir is None:
        memory_dir = Path.home() / ".claude" / "projects" / encoded / "memory"

    entries = []
    if not memory_dir.is_dir():
        return entries

    for md_file in sorted(memory_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        entries.append({
            "path": str(md_file),
            "topic": md_file.stem,
            "content": content,
        })
    return entries


def read_all_memory_entries(project_root: Optional[Path] = None) -> List[Dict[str, str]]:
    """全メモリ層のエントリを読み取る。

    Args:
        project_root: プロジェクトルート。

    Returns:
        各ファイルの {tier, path, content} のリスト。
    """
    files = find_claude_files(project_root)
    entries = []
    for tier, paths in files.items():
        for p in paths:
            try:
                content = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            entries.append({
                "tier": tier,
                "path": str(p),
                "content": content,
            })
    return entries


def suggest_auto_memory_topic(text: str) -> str:
    """テキストからトピックを判定する。

    キーワードスコアリングで最適トピックを選択。マッチなしは "general"。

    Args:
        text: 分類対象のテキスト。

    Returns:
        トピック名。
    """
    text_lower = text.lower()
    scores: Dict[str, int] = {}

    for topic, keywords in _AUTO_MEMORY_TOPICS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score

    if not scores:
        return "general"

    return max(scores, key=scores.get)  # type: ignore[arg-type]


def split_memory_sections(
    content: str,
    file_path: str = "",
) -> List[Dict[str, Any]]:
    """MEMORY コンテンツを ``## `` 見出し単位でセクション分割する。

    Args:
        content: MEMORY ファイルの全文。
        file_path: ファイルパス（出力に含める）。

    Returns:
        各セクションの ``{file, heading, content, line_range}`` のリスト。
        見出しの無い先頭部分は ``heading: "_header"`` として返す。
    """
    lines = content.splitlines()
    sections: List[Dict[str, Any]] = []
    current_heading = "_header"
    current_lines: List[str] = []
    start_line = 1

    for i, line in enumerate(lines, start=1):
        if line.startswith("## ") and not line.startswith("### "):
            # 前のセクションを確定
            body = "\n".join(current_lines).strip()
            if body:
                sections.append({
                    "file": file_path,
                    "heading": current_heading,
                    "content": body,
                    "line_range": [start_line, i - 1],
                })
            current_heading = line[3:].strip()
            current_lines = []
            start_line = i
        else:
            current_lines.append(line)

    # 最後のセクションを確定
    body = "\n".join(current_lines).strip()
    if body:
        sections.append({
            "file": file_path,
            "heading": current_heading,
            "content": body,
            "line_range": [start_line, len(lines)],
        })

    return sections
