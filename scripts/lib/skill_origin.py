"""プラグイン由来スキルの origin 判定・編集保護・代替先提案モジュール。

installed_plugins.json + パスベースのハイブリッド判定で、スキルの出自を分類し、
プラグインスキルへの編集保護と代替先パスの提案を行う。
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Constants ----------------------------------------------------------------

# pitfall_manager Candidate フォーマットテンプレート
CANDIDATE_TEMPLATE = """\
## Candidate: {title}

- **Status**: Candidate
- **First-seen**: {date}
- **Context**: {context}
- **Pattern**: {pattern}
- **Solution**: {solution}
"""

# --- Cache --------------------------------------------------------------------

_plugin_skill_map_cache: Optional[Dict[str, str]] = None
_plugin_skill_map_mtime: Optional[float] = None


def _installed_plugins_path() -> Path:
    """installed_plugins.json のパスを返す。"""
    return Path.home() / ".claude" / "plugins" / "installed_plugins.json"


def _load_plugin_skill_map() -> Dict[str, str]:
    """installed_plugins.json → {skill_name: plugin_name} マッピングを構築。

    mtime ベースの cache invalidation を適用し、ファイル変更時のみ再パースする。
    ファイルが存在しない・不正 JSON・version 未知の場合は空 dict を返す。
    """
    global _plugin_skill_map_cache, _plugin_skill_map_mtime

    ip_path = _installed_plugins_path()

    # mtime チェックによるキャッシュ判定
    try:
        current_mtime = ip_path.stat().st_mtime
    except OSError:
        # ファイルが存在しない
        _plugin_skill_map_cache = {}
        _plugin_skill_map_mtime = None
        return _plugin_skill_map_cache

    if _plugin_skill_map_cache is not None and _plugin_skill_map_mtime == current_mtime:
        return _plugin_skill_map_cache

    mapping: Dict[str, str] = {}
    try:
        data = json.loads(ip_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # 不正 JSON またはファイル読み取りエラー → パスベースフォールバック
        _plugin_skill_map_cache = {}
        _plugin_skill_map_mtime = current_mtime
        return _plugin_skill_map_cache

    # version チェック — 未知の形式は空 map を返却
    version = data.get("version")
    if version is not None and not isinstance(version, (int, float)):
        try:
            v = float(version)
            if v >= 3.0:
                _plugin_skill_map_cache = {}
                _plugin_skill_map_mtime = current_mtime
                return _plugin_skill_map_cache
        except (ValueError, TypeError):
            _plugin_skill_map_cache = {}
            _plugin_skill_map_mtime = current_mtime
            return _plugin_skill_map_cache

    try:
        plugins = data.get("plugins", {})
        for plugin_key, entries in plugins.items():
            if not isinstance(entries, list):
                continue
            plugin_name = plugin_key.split("@")[0]
            for entry in entries:
                install_path = entry.get("installPath")
                if not install_path:
                    continue
                for skills_dir in [
                    Path(install_path) / ".claude" / "skills",
                    Path(install_path) / "skills",
                ]:
                    if skills_dir.is_dir():
                        for child in skills_dir.iterdir():
                            if child.is_dir():
                                mapping[child.name] = plugin_name
    except (TypeError, KeyError, AttributeError):
        pass

    _plugin_skill_map_cache = mapping
    _plugin_skill_map_mtime = current_mtime
    return _plugin_skill_map_cache


def get_plugin_skill_map() -> Dict[str, str]:
    """外部モジュール向けの公開 API。_load_plugin_skill_map() を返す。"""
    return _load_plugin_skill_map()


def get_plugin_skill_names() -> frozenset:
    """プラグインスキル名のセットを返す（後方互換）。"""
    return frozenset(_load_plugin_skill_map().keys())


# --- Origin Classification ---------------------------------------------------

def classify_skill_origin(path: Path) -> str:
    """スキルの出自を分類する。

    Args:
        path: スキルのファイルパス

    Returns:
        "plugin" — プラグイン由来
        "global" — ~/.claude/skills/ 配下
        "custom" — プロジェクトローカル等
    """
    resolved = path.expanduser().resolve()
    resolved_str = str(resolved)

    # プラグインキャッシュパス
    plugins_dir = os.environ.get("CLAUDE_PLUGINS_DIR")
    if plugins_dir:
        plugins_path = str(Path(plugins_dir).resolve())
    else:
        plugins_path = str(Path.home() / ".claude" / "plugins" / "cache")

    if resolved_str.startswith(plugins_path):
        return "plugin"

    global_skills_path = str(Path.home() / ".claude" / "skills")
    if resolved_str.startswith(global_skills_path):
        return "global"

    # プロジェクトの .claude/skills/ 配下でプラグインインストール済みスキル名に一致
    if "/.claude/skills/" in resolved_str:
        parts = resolved.parts
        try:
            skills_idx = len(parts) - 1 - list(reversed(parts)).index("skills")
            if skills_idx + 1 < len(parts):
                skill_dir_name = parts[skills_idx + 1]
                if skill_dir_name in _load_plugin_skill_map():
                    return "plugin"
        except ValueError:
            pass

    return "custom"


# --- Protection ---------------------------------------------------------------

def is_protected_skill(path: Path) -> bool:
    """スキルが編集保護対象かを判定する。plugin origin → True。"""
    return classify_skill_origin(path) == "plugin"


def suggest_local_alternative(
    skill_name: str,
    project_root: Path,
) -> Tuple[str, bool]:
    """保護スキルへの代替先パスを提案する。

    Args:
        skill_name: スキル名
        project_root: プロジェクトルート

    Returns:
        (代替先パス文字列, 既存ファイルが存在するか) のタプル
    """
    alt_path = project_root / ".claude" / "skills" / skill_name / "references" / "pitfalls.md"
    return (str(alt_path), alt_path.exists())


def generate_protection_warning(
    skill_name: str,
    alternative_path: str,
) -> str:
    """保護スキルへの編集操作に対する警告メッセージを生成する。

    Args:
        skill_name: スキル名
        alternative_path: 代替先パス

    Returns:
        警告メッセージ文字列
    """
    return (
        f"⚠ スキル '{skill_name}' はプラグイン由来のため変更保護されています。\n"
        f"プラグイン更新時に変更が上書きで消失するリスクがあります。\n"
        f"代替先: {alternative_path}\n"
        f"知見はこのファイルに追記してください。"
    )


def format_pitfall_candidate(
    title: str,
    context: str,
    pattern: str,
    solution: str,
    date: Optional[str] = None,
) -> str:
    """pitfall_manager Candidate フォーマットでエントリを生成する。

    Args:
        title: pitfall タイトル
        context: 発生コンテキスト
        pattern: 問題パターン
        solution: 解決策
        date: 日付文字列（省略時は今日）

    Returns:
        Candidate フォーマットの Markdown 文字列
    """
    if date is None:
        from datetime import date as dt_date
        date = dt_date.today().isoformat()
    return CANDIDATE_TEMPLATE.format(
        title=title,
        date=date,
        context=context,
        pattern=pattern,
        solution=solution,
    )


# --- Prefix Utilities (audit 互換) -------------------------------------------

_plugin_prefix_cache: Optional[Dict[str, List[str]]] = None


def build_plugin_prefixes(mapping: Optional[Dict[str, str]] = None) -> Dict[str, List[str]]:
    """インストール済みスキル名から各プラグインの prefix パターンを推定する。

    audit.py の _build_plugin_prefixes() と同等の機能を提供。
    """
    global _plugin_prefix_cache
    if _plugin_prefix_cache is not None and mapping is None:
        return _plugin_prefix_cache

    from collections import defaultdict

    if mapping is None:
        mapping = _load_plugin_skill_map()

    plugin_skills: Dict[str, List[str]] = defaultdict(list)
    for skill_name, plugin_name in mapping.items():
        plugin_skills[plugin_name].append(skill_name)

    prefixes: Dict[str, List[str]] = {}
    for plugin_name, skills in plugin_skills.items():
        prefix_counts: Dict[str, int] = defaultdict(int)
        for skill in skills:
            for sep in ("-", ":"):
                idx = skill.find(sep)
                if idx > 0:
                    prefix_counts[skill[:idx + 1]] += 1
        found = [p for p, c in prefix_counts.items() if c >= 2]
        if found:
            prefixes[plugin_name] = found

    _plugin_prefix_cache = prefixes
    return _plugin_prefix_cache


def classify_usage_skill(skill_name: str) -> Optional[str]:
    """usage レコードのスキル名をプラグインに分類する。

    audit.py の classify_usage_skill() と同等の機能を提供。
    """
    plugin_map = _load_plugin_skill_map()

    # 1. 完全一致
    if skill_name in plugin_map:
        return plugin_map[skill_name]

    # 2. prefix マッチ
    prefixes = build_plugin_prefixes()
    if prefixes:
        for plugin_name, pfxs in prefixes.items():
            for prefix in pfxs:
                if skill_name.startswith(prefix):
                    return plugin_name

    # 3. plugin_name: prefix マッチ
    colon_idx = skill_name.find(":")
    if colon_idx > 0 and not skill_name.startswith("Agent:"):
        prefix_part = skill_name[:colon_idx]
        plugin_names = set(plugin_map.values())
        if prefix_part in plugin_names:
            return prefix_part
        if prefixes:
            for plugin_name, pfxs in prefixes.items():
                for pfx in pfxs:
                    pfx_base = pfx.rstrip("-:")
                    if prefix_part == pfx_base or pfx_base.startswith(prefix_part):
                        return plugin_name

    # 4. Agent:plugin-agent パターン
    if skill_name.startswith("Agent:"):
        agent_name = skill_name[6:]
        if agent_name in plugin_map:
            return plugin_map[agent_name]
        if prefixes:
            for plugin_name, pfxs in prefixes.items():
                for prefix in pfxs:
                    if agent_name.startswith(prefix):
                        return plugin_name

    return None


def invalidate_cache() -> None:
    """テスト用にキャッシュをクリアする。"""
    global _plugin_skill_map_cache, _plugin_skill_map_mtime, _plugin_prefix_cache
    _plugin_skill_map_cache = None
    _plugin_skill_map_mtime = None
    _plugin_prefix_cache = None
