#!/usr/bin/env python3
"""環境の健康診断スクリプト。

全 skills / rules / memory の棚卸し + 行数チェック + 使用状況集計を行い、
1画面レポートを出力する。
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "scripts"))

from reflect_utils import read_all_memory_entries, read_auto_memory, split_memory_sections
from hardcoded_detector import detect_hardcoded_values
from skill_origin import (
    classify_skill_origin as _so_classify_skill_origin,
    get_plugin_skill_map as _so_get_plugin_skill_map,
    get_plugin_skill_names as _so_get_plugin_skill_names,
    build_plugin_prefixes as _so_build_plugin_prefixes,
    classify_usage_skill as _so_classify_usage_skill,
    invalidate_cache as _so_invalidate_cache,
)

# 行数制限
LIMITS = {
    "CLAUDE.md": 200,  # warning のみ（violation としては扱わない）
    "rules": 3,
    "project_rules": 5,
    "SKILL.md": 500,
    "MEMORY.md": 200,
    "memory": 120,
}

DATA_DIR = Path.home() / ".claude" / "rl-anything"

# 既知のプロジェクトディレクトリプレフィックス（2セグメントパスフィルタ用）
KNOWN_DIR_PREFIXES = {"skills", "scripts", "hooks", ".claude", "openspec", "docs"}

# セマンティック検証用ストップワード（英語冠詞・前置詞・助動詞 + 日本語助詞）
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "and", "but", "or", "nor", "not", "so", "yet", "if", "then", "than",
    "it", "its", "this", "that", "these", "those", "he", "she", "they",
    "we", "you", "i", "me", "my", "your", "his", "her", "our", "their",
    "の", "は", "が", "を", "に", "で", "と", "も", "や", "か",
    "する", "した", "して", "です", "ます", "ある", "いる", "なる",
})

# 肥大化早期警告の閾値（行数上限に対する比率）
NEAR_LIMIT_RATIO = 0.8


# キャッシュ: skill_origin.py に委譲（後方互換ラッパー）
# テスト後方互換: audit._plugin_skill_map_cache を直接セットするテスト向け
_plugin_skill_map_cache: Optional[Dict[str, str]] = None


def _load_plugin_skill_map() -> Dict[str, str]:
    """installed_plugins.json → {skill_name: plugin_name} マッピングを構築。

    skill_origin.py に委譲。後方互換のためラッパーとして残す。
    テストが _plugin_skill_map_cache を直接セットした場合はそちらを優先。
    """
    if _plugin_skill_map_cache is not None:
        _build_plugin_prefixes(_plugin_skill_map_cache)
        return _plugin_skill_map_cache
    mapping = _so_get_plugin_skill_map()
    # prefix も構築（classify_usage_skill の後方互換用）
    _build_plugin_prefixes(mapping)
    return mapping


# プラグイン名 → prefix パターンのキャッシュ
_plugin_prefix_cache: Optional[Dict[str, List[str]]] = None


def _build_plugin_prefixes(mapping: Dict[str, str]) -> None:
    """skill_origin.py に委譲。後方互換ラッパー。"""
    global _plugin_prefix_cache
    _plugin_prefix_cache = _so_build_plugin_prefixes(mapping)


def classify_usage_skill(skill_name: str) -> Optional[str]:
    """usage レコードのスキル名をプラグインに分類する。

    skill_origin.py に委譲。後方互換ラッパー。
    """
    # prefix キャッシュ初期化を保証
    _load_plugin_skill_map()
    return _so_classify_usage_skill(skill_name)


def _load_plugin_skill_names() -> frozenset:
    """後方互換ラッパー。テストが _plugin_skill_map_cache を直接セットした場合はそちらを優先。"""
    if _plugin_skill_map_cache is not None:
        return frozenset(_plugin_skill_map_cache.keys())
    return frozenset(_load_plugin_skill_map().keys())


def classify_artifact_origin(path: Path) -> str:
    """スキル/ルールの出自を分類する。skill_origin.py に委譲。

    テストが _plugin_skill_map_cache を直接セットした場合は、
    そのキャッシュを使ってインライン判定する（後方互換）。

    Returns:
        "plugin" — プラグイン由来
        "global" — ~/.claude/skills/ 配下
        "custom" — その他（プロジェクトローカル等）
    """
    if _plugin_skill_map_cache is not None:
        # テスト後方互換: ローカルキャッシュが設定されている場合はインライン判定
        resolved = path.expanduser().resolve()
        resolved_str = str(resolved)

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

        if "/.claude/skills/" in resolved_str:
            parts = resolved.parts
            try:
                skills_idx = len(parts) - 1 - list(reversed(parts)).index("skills")
                if skills_idx + 1 < len(parts):
                    skill_dir_name = parts[skills_idx + 1]
                    if skill_dir_name in _plugin_skill_map_cache:
                        return "plugin"
            except ValueError:
                pass

        return "custom"

    return _so_classify_skill_origin(path)


def find_artifacts(project_dir: Path) -> Dict[str, List[Path]]:
    """プロジェクト内のアーティファクトを一覧する。"""
    result: Dict[str, List[Path]] = {
        "skills": [],
        "rules": [],
        "memory": [],
        "claude_md": [],
    }

    claude_dir = project_dir / ".claude"

    # CLAUDE.md
    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists():
        result["claude_md"].append(claude_md)

    # Skills
    skills_dir = claude_dir / "skills"
    if skills_dir.exists():
        for skill_md in skills_dir.rglob("SKILL.md"):
            result["skills"].append(skill_md)

    # Rules
    rules_dir = claude_dir / "rules"
    if rules_dir.exists():
        for rule_file in rules_dir.glob("*.md"):
            result["rules"].append(rule_file)

    # Memory
    memory_dir = claude_dir / "memory"
    if memory_dir.exists():
        for mem_file in memory_dir.glob("*.md"):
            result["memory"].append(mem_file)

    # Global artifacts
    global_claude = Path.home() / ".claude"
    global_skills = global_claude / "skills"
    if global_skills.exists():
        for skill_md in global_skills.rglob("SKILL.md"):
            result["skills"].append(skill_md)

    global_rules = global_claude / "rules"
    if global_rules.exists():
        for rule_file in global_rules.glob("*.md"):
            result["rules"].append(rule_file)

    return result


def check_line_limits(artifacts: Dict[str, List[Path]]) -> List[Dict[str, Any]]:
    """行数制限の超過を検出する。

    CLAUDE.md は violation ではなく warning のみ（collect_issues で除外）。
    """
    violations = []

    for path in artifacts.get("claude_md", []):
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        if lines > LIMITS["CLAUDE.md"]:
            violations.append({"file": str(path), "lines": lines, "limit": LIMITS["CLAUDE.md"], "warning_only": True})

    for path in artifacts.get("rules", []):
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        # グローバル/プロジェクトルールで制限値を分ける
        home_str = str(Path.home())
        is_global = str(path).startswith(home_str) and ".claude/rules/" in str(path)
        limit = LIMITS["rules"] if is_global else LIMITS["project_rules"]
        if lines > limit:
            violations.append({"file": str(path), "lines": lines, "limit": limit})

    for path in artifacts.get("skills", []):
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        if lines > LIMITS["SKILL.md"]:
            violations.append({"file": str(path), "lines": lines, "limit": LIMITS["SKILL.md"]})

    for path in artifacts.get("memory", []):
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        limit = LIMITS["MEMORY.md"] if path.name == "MEMORY.md" else LIMITS["memory"]
        if lines > limit:
            violations.append({"file": str(path), "lines": lines, "limit": limit})

    return violations


def _extract_section_keywords(text: str) -> List[str]:
    """MEMORY セクションのテキストからキーワードを抽出する。

    ストップワードと2文字以下の単語を除外して返す。
    """
    import re as _re

    # コードブロック除去
    cleaned = _re.sub(r"```[\s\S]*?```", "", text)
    # Markdown 記法除去（リンク、強調等）
    cleaned = _re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cleaned)
    cleaned = _re.sub(r"[*_`#>|]", " ", cleaned)
    # トークン化: アルファベット/数字/CJK を含む単語（CJK句読点を除外）
    tokens = _re.findall(r"[\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uf900-\ufaff]+", cleaned, _re.UNICODE)
    # フィルタリング
    keywords = []
    seen: set = set()
    for token in tokens:
        lower = token.lower()
        if len(token) <= 2 and not any("\u3040" <= c <= "\u9fff" for c in token):
            continue
        if lower in _STOPWORDS:
            continue
        if lower not in seen:
            seen.add(lower)
            keywords.append(token)
    return keywords


def _find_archive_mentions(
    keywords: List[str],
    project_dir: Path,
) -> List[str]:
    """OpenSpec archive ディレクトリ名とキーワードを照合しメンションを返す。"""
    archive_dir = project_dir / "openspec" / "changes" / "archive"
    if not archive_dir.is_dir():
        return []
    mentions = []
    kw_lower = {kw.lower() for kw in keywords}
    for entry in sorted(archive_dir.iterdir()):
        if not entry.is_dir():
            continue
        # アーカイブ名は "YYYY-MM-DD-name" 形式 → 日付部分を除去
        name = entry.name
        parts = name.split("-", 3)
        if len(parts) >= 4:
            name_part = parts[3]
        else:
            name_part = name
        # アーカイブ名のトークンとキーワードをマッチ
        name_tokens = {t.lower() for t in name_part.replace("-", " ").split()}
        if name_tokens & kw_lower:
            mentions.append(entry.name)
    return mentions


def _extract_paths_outside_codeblocks(text: str) -> List[Tuple[int, str]]:
    """テキストからコードブロック外のファイルパス参照を抽出する。

    Returns:
        [(line_number, path_string), ...] のリスト。行番号は1始まり。
    """
    import re

    # コードブロックの行範囲を特定
    lines = text.splitlines()
    in_codeblock = False
    codeblock_lines: set = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_codeblock = not in_codeblock
            codeblock_lines.add(i)
            continue
        if in_codeblock:
            codeblock_lines.add(i)

    # コードブロック外の行からパスを抽出
    # 相対パス (skills/update/, scripts/lib/) または絶対パス (/path/to/file)
    path_pattern = re.compile(r'(?:^|[\s`"\'])(/[a-zA-Z0-9_./-]{2,}|[a-zA-Z0-9_.-]+/[a-zA-Z0-9_./-]+)')
    results = []
    for i, line in enumerate(lines):
        if i in codeblock_lines:
            continue
        for match in path_pattern.finditer(line):
            path_str = match.group(1).rstrip("/.,;:)")
            # 短すぎるパスやURL風のものを除外
            if len(path_str) < 3 or path_str.startswith("http"):
                continue
            # スラッシュコマンド記法 (/plugin, /rl-anything:xxx) を除外
            if path_str.startswith("/") and "/" not in path_str[1:]:
                continue
            # Python シンボル参照 (CONST/func) を除外 — 全大文字セグメントを含む場合
            segments = path_str.split("/")
            if not path_str.startswith("/") and any(s.isupper() for s in segments if s):
                continue
            # 全セグメントが数値パターンのパスを除外（HTTP ステータスコード 429/500/503、バージョン 1.0/2.1 等）
            if all(s.replace(".", "").isdigit() for s in segments if s):
                continue
            # 拡張子なしの2セグメント相対パスは既知プレフィックスで検証
            if (
                not path_str.startswith("/")
                and len(segments) == 2
                and not any("." in s for s in segments)
                and segments[0] not in KNOWN_DIR_PREFIXES
            ):
                continue
            results.append((i + 1, path_str))
    return results


def _is_project_specific_section(
    section: Dict[str, Any],
    project_dir: Path,
) -> bool:
    """global memory のセクションが PJ 固有の記述を含むか判定する。"""
    project_name = project_dir.name
    content_lower = section.get("content", "").lower()
    heading_lower = section.get("heading", "").lower()
    combined = f"{heading_lower} {content_lower}"
    # PJ 名がセクション内に出現するか
    if project_name.lower() in combined:
        return True
    # PJ ディレクトリ内の主要ファイル名がメンションされているか
    for child in project_dir.iterdir():
        if child.name.startswith("."):
            continue
        if child.name.lower() in combined:
            return True
    return False


def build_memory_verification_context(
    project_dir: Path,
) -> Dict[str, Any]:
    """MEMORY セクションの検証用コンテキストを構造化 JSON で返す。

    セクション分割 → キーワード抽出 → grep → archive メンション を実行し、
    LLM 検証ステップに渡す構造化データを生成する。
    """
    import subprocess

    sections_out: List[Dict[str, Any]] = []

    # 1. auto-memory の読み取り
    for entry in read_auto_memory(str(project_dir)):
        try:
            sections = split_memory_sections(entry["content"], entry["path"])
            sections_out.extend(sections)
        except Exception as e:
            print(f"Warning: failed to parse {entry['path']}: {e}", file=sys.stderr)

    # 2. global memory（PJ 固有セクションのみ）
    all_entries = read_all_memory_entries(project_dir)
    for entry in all_entries:
        if entry["tier"] != "global":
            continue
        try:
            global_sections = split_memory_sections(entry["content"], entry["path"])
            for sec in global_sections:
                if _is_project_specific_section(sec, project_dir):
                    sections_out.append(sec)
        except Exception as e:
            print(f"Warning: failed to parse global memory: {e}", file=sys.stderr)

    if not sections_out:
        return {"sections": []}

    # 3. 各セクションにキーワード・codebase_evidence・archive_mentions を付与
    for sec in sections_out:
        keywords = _extract_section_keywords(sec["content"])
        sec["keywords"] = keywords

        # codebase grep（上位3キーワードで検索、各最大3件）
        evidence: List[Dict[str, str]] = []
        for kw in keywords[:3]:
            try:
                result = subprocess.run(
                    ["grep", "-r", "-l", "--include=*.py", "--include=*.md",
                     "--include=*.ts", "--include=*.js", "--include=*.yaml",
                     "--include=*.yml", "--include=*.json",
                     "-m", "3", kw, str(project_dir)],
                    capture_output=True, text=True, timeout=10,
                )
                for fpath in result.stdout.strip().splitlines()[:3]:
                    # MEMORY 自身は除外
                    if "memory/" in fpath or ".claude/projects/" in fpath:
                        continue
                    # ファイルからスニペット取得
                    try:
                        snippet_result = subprocess.run(
                            ["grep", "-n", "-m", "2", kw, fpath],
                            capture_output=True, text=True, timeout=5,
                        )
                        snippet = snippet_result.stdout.strip()[:200]
                    except (subprocess.TimeoutExpired, OSError):
                        snippet = ""
                    rel_path = str(Path(fpath).relative_to(project_dir)) if fpath.startswith(str(project_dir)) else fpath
                    evidence.append({"file": rel_path, "snippet": snippet})
            except (subprocess.TimeoutExpired, OSError):
                continue
        sec["codebase_evidence"] = evidence

        # archive メンション
        sec["archive_mentions"] = _find_archive_mentions(keywords, project_dir)

    return {"sections": sections_out}


def build_memory_health_section(
    artifacts: Dict[str, List[Path]],
    project_dir: Path,
) -> List[str]:
    """MEMORY ファイルの健康度を分析し、レポートセクションの行リストを返す。

    検出項目:
    - 陳腐化参照: MEMORY 内のパス参照がディスク上に存在しない
    - 肥大化警告: NEAR_LIMIT_RATIO 以上の行数

    問題がない場合は空リストを返す。
    """
    # project-local memory + auto-memory を統合
    memory_files: List[Tuple[Path, str]] = []  # (path, content)

    for path in artifacts.get("memory", []):
        try:
            content = path.read_text(encoding="utf-8")
            memory_files.append((path, content))
        except (OSError, UnicodeDecodeError) as e:
            print(f"Warning: failed to read {path}: {e}", file=sys.stderr)

    for entry in read_auto_memory(str(project_dir)):
        entry_path = Path(entry["path"])
        # project-local と重複しないように
        if not any(p == entry_path for p, _ in memory_files):
            memory_files.append((entry_path, entry["content"]))

    stale_refs: List[Dict[str, Any]] = []
    near_limits: List[Dict[str, Any]] = []

    for path, content in memory_files:
        # 陳腐化参照の検出
        extracted = _extract_paths_outside_codeblocks(content)
        for line_num, ref_path in extracted:
            # 絶対パスはそのまま、相対パスは project_dir からの相対で確認
            if ref_path.startswith("/"):
                check_path = Path(ref_path)
            else:
                check_path = project_dir / ref_path
            if not check_path.exists():
                # ファイル位置基準の相対パス解決（参照元ファイルの親ディレクトリ基準）
                if not ref_path.startswith("/"):
                    file_relative = path.parent / ref_path
                    if file_relative.exists():
                        continue
                # トップレベルディレクトリがプロジェクトルートに存在しない場合は除外
                if not ref_path.startswith("/"):
                    top_dir = ref_path.split("/")[0]
                    if top_dir not in KNOWN_DIR_PREFIXES and not (project_dir / top_dir).exists():
                        continue
                stale_refs.append({
                    "file": str(path),
                    "line": line_num,
                    "path": ref_path,
                })

        # 肥大化警告
        line_count = content.count("\n") + 1
        limit = LIMITS["MEMORY.md"] if path.name == "MEMORY.md" else LIMITS["memory"]
        threshold = int(limit * NEAR_LIMIT_RATIO)
        if line_count >= threshold:
            pct = int(line_count / limit * 100)
            near_limits.append({
                "file": str(path),
                "lines": line_count,
                "limit": limit,
                "pct": pct,
            })

    # 問題なしなら空リスト
    if not stale_refs and not near_limits:
        return []

    lines = ["## Memory Health", ""]

    if stale_refs:
        lines.append(f"### Stale References ({len(stale_refs)})")
        for ref in stale_refs:
            lines.append(f"- {ref['file']}:{ref['line']} — \"{ref['path']}\" not found on disk")
        lines.append("")

    if near_limits:
        lines.append("### Near Limit")
        for nl in near_limits:
            lines.append(f"- {nl['file']}: {nl['lines']}/{nl['limit']} lines ({nl['pct']}%)")
        lines.append("")

    # Suggestions
    suggestions = []
    if stale_refs:
        suggestions.append("Remove or update stale references")
    if near_limits:
        suggestions.append("Split large MEMORY.md entries into topic files")
    if suggestions:
        lines.append("### Suggestions")
        for s in suggestions:
            lines.append(f"- {s}")
        lines.append("")

    return lines


def load_usage_data(
    days: int = 30,
    *,
    project_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """usage.jsonl から直近N日のデータを読み込む。

    Args:
        days: 直近何日分のデータを読み込むか。
        project_root: 指定時は該当プロジェクトのレコードのみ返す。
    """
    from telemetry_query import query_usage

    project_name = project_root.name if project_root else None
    # project_root 未指定時は全レコードを対象（グローバル集計）
    include_unknown = project_root is None
    records = query_usage(
        project=project_name,
        include_unknown=include_unknown,
        usage_file=DATA_DIR / "usage.jsonl",
    )

    # 日数フィルタ
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return [r for r in records if r.get("timestamp", "") >= cutoff]


from agent_classifier import BUILTIN_AGENT_NAMES

_BUILTIN_TOOLS = {f"Agent:{n}" for n in BUILTIN_AGENT_NAMES} | {"commit"}


def _is_plugin_skill(skill_name: str) -> bool:
    """スキル名がプラグイン由来かどうかを判定する。

    classify_usage_skill（完全一致 + prefix マッチ）と _is_openspec_skill（キーワード）を併用。
    """
    if classify_usage_skill(skill_name) is not None:
        return True
    if _is_openspec_skill(skill_name):
        return True
    return False


def aggregate_usage(
    records: List[Dict[str, Any]],
    exclude_plugins: bool = False,
) -> Dict[str, int]:
    """スキル使用回数を集計する。基本ツールはノイズのため除外。

    Args:
        records: usage レコードのリスト
        exclude_plugins: True の場合、プラグインスキルを除外して PJ 固有のみ返す
    """
    counts: Dict[str, int] = {}
    for rec in records:
        skill = rec.get("skill_name", "unknown")
        if skill in _BUILTIN_TOOLS:
            continue
        if exclude_plugins and _is_plugin_skill(skill):
            continue
        counts[skill] = counts.get(skill, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def aggregate_plugin_usage(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """プラグイン別の使用回数を集計する。

    classify_usage_skill でプラグイン名が判定できるものはプラグイン名で集計。
    _is_openspec_skill でのみマッチするものは "openspec(legacy)" として集計。

    Returns:
        {plugin_name: total_count} の辞書（降順ソート）
    """
    plugin_counts: Dict[str, int] = {}
    for rec in records:
        skill = rec.get("skill_name", "unknown")
        if skill in _BUILTIN_TOOLS:
            continue
        plugin_name = classify_usage_skill(skill)
        if plugin_name:
            plugin_counts[plugin_name] = plugin_counts.get(plugin_name, 0) + 1
        elif _is_openspec_skill(skill):
            # opsx:* 等の旧スキル名 → openspec として集計
            key = "openspec(legacy)"
            plugin_counts[key] = plugin_counts.get(key, 0) + 1
    return dict(sorted(plugin_counts.items(), key=lambda x: x[1], reverse=True))


def detect_duplicates_simple(artifacts: Dict[str, List[Path]]) -> List[Dict[str, Any]]:
    """簡易的な重複検出（ファイル名ベース）。LLM ベースの意味的類似度判定は別途実行。"""
    seen: Dict[str, List[str]] = {}
    duplicates = []

    for category in ["skills", "rules"]:
        for path in artifacts.get(category, []):
            name = path.stem if category == "rules" else path.parent.name
            key = name.lower().replace("-", "").replace("_", "")
            if key not in seen:
                seen[key] = []
            seen[key].append(str(path))

    for key, paths in seen.items():
        if len(paths) > 1:
            duplicates.append({"name": key, "paths": paths})

    return duplicates


def semantic_similarity_check(
    artifacts: Dict[str, List[Path]], threshold: float = 0.80
) -> List[Dict[str, Any]]:
    """TF-IDF + コサイン類似度による意味的類似度判定。閾値は 80%。

    audit-report spec の Single Source of Truth。
    prune はこの関数の結果を利用する。

    Returns:
        [{"path_a": str, "path_b": str, "similarity": float}, ...]
    """
    from similarity import compute_pairwise_similarity

    # artifacts から skills と rules のパスを辞書に変換（プラグイン由来は除外）
    path_dict: Dict[str, str] = {}
    for path in artifacts.get("skills", []):
        if classify_artifact_origin(path) == "plugin":
            continue
        skill_name = path.parent.name
        path_dict[skill_name] = str(path)

    for path in artifacts.get("rules", []):
        if classify_artifact_origin(path) == "plugin":
            continue
        rule_stem = path.stem
        path_dict[rule_stem] = str(path)

    return compute_pairwise_similarity(path_dict, threshold)


def load_usage_registry() -> Dict[str, List[Dict[str, Any]]]:
    """Usage Registry からデータを読み込む。"""
    registry_file = DATA_DIR / "usage-registry.jsonl"
    if not registry_file.exists():
        return {}

    result: Dict[str, List[Dict[str, Any]]] = {}
    for line in registry_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            skill = rec.get("skill_name", "")
            if skill not in result:
                result[skill] = []
            result[skill].append(rec)
        except json.JSONDecodeError:
            continue
    return result


def scope_advisory(registry: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Scope Advisory: global スキルの使用PJ数と推奨アクションを生成。"""
    advisories = []
    for skill, records in registry.items():
        projects = set(r.get("project_path", "") for r in records)
        latest = max((r.get("timestamp", "") for r in records), default="")
        advisory = {
            "skill": skill,
            "project_count": len(projects),
            "projects": list(projects),
            "last_used": latest,
            "recommendation": "keep global" if len(projects) > 1 else "consider project-scope",
        }
        advisories.append(advisory)
    return advisories


def load_quality_baselines() -> List[Dict[str, Any]]:
    """quality-baselines.jsonl から全レコードを読み込む。"""
    baselines_file = DATA_DIR / "quality-baselines.jsonl"
    if not baselines_file.exists():
        return []
    records = []
    for line in baselines_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def generate_sparkline(scores: List[float]) -> str:
    """スコアリストからスパークライン文字列を生成する。"""
    if not scores:
        return ""
    blocks = " ▁▂▃▄▅▆▇"
    min_s = min(scores)
    max_s = max(scores)
    span = max_s - min_s if max_s > min_s else 1.0
    result = ""
    for s in scores:
        idx = int((s - min_s) / span * (len(blocks) - 1))
        idx = max(0, min(len(blocks) - 1, idx))
        result += blocks[idx]
    return result


def build_quality_trends_section(
    baselines: List[Dict[str, Any]],
    usage: Dict[str, int],
) -> List[str]:
    """品質推移セクションの行リストを生成する。"""
    if not baselines:
        return []

    # 遅延 import（循環参照回避）
    _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))
    from quality_monitor import (
        DEGRADATION_THRESHOLD,
        RESCORE_DAYS_THRESHOLD,
        RESCORE_USAGE_THRESHOLD,
        compute_baseline_score,
        compute_moving_average,
        get_skill_records,
        needs_rescore,
    )

    # スキル名を収集
    skill_names = sorted(set(r.get("skill_name", "") for r in baselines if r.get("skill_name")))
    if not skill_names:
        return []

    lines = ["## Skill Quality Trends", ""]

    for skill_name in skill_names:
        skill_recs = get_skill_records(baselines, skill_name)
        if not skill_recs:
            continue

        scores = [r.get("score", 0.0) for r in skill_recs]
        latest_score = scores[-1] if scores else 0.0

        # スパークライン（2件以上必要）
        if len(scores) >= 2:
            sparkline = generate_sparkline(scores)
        else:
            sparkline = ""

        # 劣化判定
        degraded = False
        if len(skill_recs) >= 2:
            baseline = compute_baseline_score(skill_recs)
            avg = compute_moving_average(skill_recs)
            if baseline > 0:
                decline_rate = (baseline - avg) / baseline
                degraded = decline_rate >= DEGRADATION_THRESHOLD

        # 再スコアリング判定
        current_usage = usage.get(skill_name, 0)
        rescore_needed = needs_rescore(skill_name, current_usage, baselines)

        # 行を組み立て
        parts = [f"- {skill_name}"]
        if sparkline:
            parts.append(f" {sparkline}")
        parts.append(f" {latest_score:.2f}")
        if degraded:
            parts.append(f" DEGRADED → /optimize {skill_name}")
        elif rescore_needed:
            parts.append(" RESCORE NEEDED")
        lines.append("".join(parts))

    lines.append("")
    return lines


# ---------- OpenSpec ワークフロー分析 ----------

# OpenSpec ライフサイクルフェーズの順序
_OPENSPEC_LIFECYCLE = ["propose", "refine", "apply", "verify", "archive"]


def _match_openspec_phase(skill_name: str) -> Optional[str]:
    """スキル名から OpenSpec ライフサイクルフェーズを推定する。

    スキル名に openspec/opsx を含み、かつフェーズ名を含むものを判定。
    """
    name_lower = skill_name.lower()
    for phase in _OPENSPEC_LIFECYCLE:
        if phase in name_lower:
            return phase
    return None


def _is_openspec_skill(skill_name: str) -> bool:
    """スキル名が OpenSpec 関連かどうかを判定する。

    openspec / opsx をキーワードとして判定。
    """
    name_lower = skill_name.lower()
    base = name_lower[6:] if name_lower.startswith("agent:") else name_lower
    return "openspec" in base or base.startswith("opsx:")


def build_openspec_analytics_section(
    records: List[Dict[str, Any]],
) -> List[str]:
    """OpenSpec ワークフロー分析セクションを構築する。

    ファネル（セッション内ライフサイクル完走率）、フェーズ別効率、
    品質トレンド、最適化候補を表示。
    """
    # _load_plugin_skill_map を呼んで prefix キャッシュを初期化
    _load_plugin_skill_map()

    # OpenSpec レコードのみ抽出
    openspec_records = [r for r in records if _is_openspec_skill(r.get("skill_name", ""))]
    if not openspec_records:
        return []

    # フェーズ別集計
    phase_counts: Dict[str, int] = {}
    phase_records: Dict[str, List[Dict[str, Any]]] = {}
    for rec in openspec_records:
        phase = _match_openspec_phase(rec.get("skill_name", ""))
        if phase:
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
            if phase not in phase_records:
                phase_records[phase] = []
            phase_records[phase].append(rec)

    if not phase_counts:
        return []

    lines = ["## OpenSpec Workflow Analytics", ""]

    # ファネル表示
    funnel_parts = []
    for phase in _OPENSPEC_LIFECYCLE:
        count = phase_counts.get(phase, 0)
        if count > 0:
            funnel_parts.append(f"{phase}({count})")
    if funnel_parts:
        lines.append(f"Funnel: {' → '.join(funnel_parts)}")

    # propose → archive 比率
    propose_count = phase_counts.get("propose", 0)
    archive_count = phase_counts.get("archive", 0)
    if propose_count > 0:
        ratio = archive_count / propose_count
        if ratio <= 1.0:
            lines.append(f"Completion rate: {int(ratio * 100)}% ({archive_count}/{propose_count})")
        else:
            lines.append(f"Propose→Archive ratio: {ratio:.1f}x ({archive_count}/{propose_count})")
    lines.append("")

    # フェーズ別効率テーブル
    lines.append("Phase efficiency:")
    for phase in _OPENSPEC_LIFECYCLE:
        recs = phase_records.get(phase, [])
        if not recs:
            continue
        count = len(recs)
        # セッション別グルーピングで平均ステップ数を推定
        sessions: Dict[str, int] = {}
        for r in recs:
            sid = r.get("session_id", "unknown")
            sessions[sid] = sessions.get(sid, 0) + 1
        avg_steps = sum(sessions.values()) / len(sessions) if sessions else 0
        # スキル名のばらつき（一貫性指標）
        skill_names = [r.get("skill_name", "") for r in recs]
        unique_ratio = len(set(skill_names)) / len(skill_names) if skill_names else 1.0
        consistency = 1.0 - unique_ratio  # 名前が統一されているほど高い
        warn = " LOW" if consistency < 0.5 and count >= 5 else ""
        lines.append(f"- {phase}: {count} runs, avg {avg_steps:.1f} steps/session, consistency {consistency:.2f}{warn}")

    lines.append("")

    # 品質トレンド（quality-baselines.jsonl から openspec スキルのみ）
    baselines = load_quality_baselines()
    if baselines:
        openspec_baselines = [b for b in baselines if _is_openspec_skill(b.get("skill_name", ""))]
        if openspec_baselines:
            lines.append("Quality trends:")
            skill_scores: Dict[str, float] = {}
            for b in openspec_baselines:
                skill_scores[b["skill_name"]] = b.get("score", 0.0)
            for name, score in sorted(skill_scores.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {name}: {score:.2f}")
            lines.append("")

    # 最適化候補（一貫性が最も低いフェーズ）
    worst_phase = None
    worst_consistency = 1.0
    for phase in _OPENSPEC_LIFECYCLE:
        recs = phase_records.get(phase, [])
        if len(recs) < 5:
            continue
        skill_names = [r.get("skill_name", "") for r in recs]
        unique_ratio = len(set(skill_names)) / len(skill_names) if skill_names else 1.0
        consistency = 1.0 - unique_ratio
        if consistency < worst_consistency:
            worst_consistency = consistency
            worst_phase = phase
    if worst_phase and worst_consistency < 0.5:
        lines.append(f"Optimization candidate: {worst_phase} (consistency {worst_consistency:.2f})")
        lines.append("")

    return lines


def detect_untagged_reference_candidates(
    artifacts: Dict[str, List[Path]],
    usage: Dict[str, int],
) -> List[Dict[str, Any]]:
    """ゼロ呼び出しだが reference 未設定のスキルを検出する。

    frontmatter に type フィールドがなく、usage もゼロのスキルを警告候補として返す。
    プラグインスキルは除外（プラグイン側で管理すべきため）。
    ユーザーに type: reference タグの付与を促すためのもの。
    """
    from frontmatter import parse_frontmatter

    candidates = []
    for path in artifacts.get("skills", []):
        skill_name = path.parent.name
        if classify_artifact_origin(path) == "plugin":
            continue
        if skill_name in usage and usage[skill_name] > 0:
            continue
        # frontmatter に type がないスキルのみ
        fm = parse_frontmatter(path)
        if not fm.get("type"):
            candidates.append({
                "skill_name": skill_name,
                "file": str(path),
            })
    return candidates


def collect_issues(project_dir: Path) -> List[Dict[str, Any]]:
    """既存の検出関数の結果を統一フォーマットの issue リストとして返す。

    各 issue は {"type": str, "file": str, "detail": dict, "source": str} 形式。
    generate_report() には影響しない。
    """
    artifacts = find_artifacts(project_dir)
    issues: List[Dict[str, Any]] = []

    # violations（行数超過）— CLAUDE.md は warning のみ（violation として扱わない）
    violations = check_line_limits(artifacts)
    for v in violations:
        if v.get("warning_only"):
            continue
        issues.append({
            "type": "line_limit_violation",
            "file": v["file"],
            "detail": {"lines": v["lines"], "limit": v["limit"]},
            "source": "check_line_limits",
        })

    # stale_refs（陳腐化参照）と near_limits（肥大化警告）
    memory_files: List[Tuple[Path, str]] = []
    for path in artifacts.get("memory", []):
        try:
            content = path.read_text(encoding="utf-8")
            memory_files.append((path, content))
        except (OSError, UnicodeDecodeError):
            continue
    for entry in read_auto_memory(str(project_dir)):
        entry_path = Path(entry["path"])
        if not any(p == entry_path for p, _ in memory_files):
            memory_files.append((entry_path, entry["content"]))

    for path, content in memory_files:
        extracted = _extract_paths_outside_codeblocks(content)
        for line_num, ref_path in extracted:
            if ref_path.startswith("/"):
                check_path = Path(ref_path)
            else:
                check_path = project_dir / ref_path
            if not check_path.exists():
                # ファイル位置基準の相対パス解決（参照元ファイルの親ディレクトリ基準）
                if not ref_path.startswith("/"):
                    file_relative = path.parent / ref_path
                    if file_relative.exists():
                        continue
                # トップレベルディレクトリがプロジェクトルートに存在しない場合は除外
                if not ref_path.startswith("/"):
                    top_dir = ref_path.split("/")[0]
                    if top_dir not in KNOWN_DIR_PREFIXES and not (project_dir / top_dir).exists():
                        continue
                issues.append({
                    "type": "stale_ref",
                    "file": str(path),
                    "detail": {"line": line_num, "path": ref_path},
                    "source": "build_memory_health_section",
                })

        line_count = content.count("\n") + 1
        limit = LIMITS["MEMORY.md"] if path.name == "MEMORY.md" else LIMITS["memory"]
        threshold = int(limit * NEAR_LIMIT_RATIO)
        if line_count >= threshold:
            pct = int(line_count / limit * 100)
            issues.append({
                "type": "near_limit",
                "file": str(path),
                "detail": {"lines": line_count, "limit": limit, "pct": pct},
                "source": "build_memory_health_section",
            })

    # duplicates（重複候補）
    duplicates = detect_duplicates_simple(artifacts)
    for d in duplicates:
        issues.append({
            "type": "duplicate",
            "file": d["paths"][0] if d["paths"] else "",
            "detail": {"name": d["name"], "paths": d["paths"]},
            "source": "detect_duplicates_simple",
        })

    # hardcoded values（ハードコード値検出）
    for category in ("skills", "rules"):
        for path in artifacts.get(category, []):
            detections = detect_hardcoded_values(str(path))
            for det in detections:
                issues.append({
                    "type": "hardcoded_value",
                    "file": str(path),
                    "detail": det,
                    "source": "detect_hardcoded_values",
                })

    # レイヤー別診断（Rules / Memory / Hooks / CLAUDE.md）
    try:
        from layer_diagnose import diagnose_all_layers
        existing_stale_refs = [i for i in issues if i["type"] == "stale_ref"]
        layer_results = diagnose_all_layers(
            project_dir,
            existing_stale_refs=existing_stale_refs,
        )
        for layer_issues in layer_results.values():
            issues.extend(layer_issues)
    except Exception:
        pass  # レイヤー診断のエラーは既存機能に影響しない

    # untagged_reference_candidates（reference type 未設定スキル）
    try:
        usage_records = load_usage_data(project_root=project_dir)
        usage = aggregate_usage(usage_records, exclude_plugins=True)
        untagged = detect_untagged_reference_candidates(artifacts, usage)
        for candidate in untagged:
            issues.append({
                "type": "untagged_reference_candidates",
                "file": candidate["file"],
                "detail": {"skill_name": candidate["skill_name"]},
                "source": "detect_untagged_reference_candidates",
            })
    except Exception:
        pass  # untagged 検出のエラーは既存機能に影響しない

    return issues


def _format_constitutional_report(result: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    """Constitutional Score をレポート用にフォーマットする。"""
    if result is None:
        return ["## Constitutional Score", "", "LLM 評価に失敗しました", ""]

    if result.get("overall") is None:
        skip_reason = result.get("skip_reason", "unknown")
        coverage = result.get("coverage_value", "N/A")
        return [
            "## Constitutional Score",
            "",
            f"Skipped: {skip_reason} (coverage={coverage})",
            "",
        ]

    lines = [f"## Constitutional Score: {result['overall']:.2f}", ""]

    # 原則別スコア
    per_principle = result.get("per_principle", [])
    if per_principle:
        lines.append("### Per-Principle Scores")
        for p in per_principle:
            score = p.get("score", 0.0)
            bar_filled = int(score * 20)
            bar_empty = 20 - bar_filled
            bar = "\u2588" * bar_filled + "\u2591" * bar_empty
            lines.append(f"  {p.get('id', '?'):30s} {score:.2f} {bar}")
        lines.append("")

    # コスト情報
    cost = result.get("estimated_cost_usd", 0)
    calls = result.get("llm_calls_count", 0)
    lines.append(f"LLM calls: {calls}, Estimated cost: ${cost:.4f}")
    lines.append("")

    return lines


def generate_report(
    artifacts: Dict[str, List[Path]],
    violations: List[Dict[str, Any]],
    usage: Dict[str, int],
    duplicates: List[Dict[str, Any]],
    advisories: List[Dict[str, Any]],
    quality_baselines: Optional[List[Dict[str, Any]]] = None,
    project_dir: Optional[Path] = None,
    plugin_usage: Optional[Dict[str, int]] = None,
    openspec_analytics: Optional[List[str]] = None,
    untagged_reference_candidates: Optional[List[Dict[str, Any]]] = None,
    hardcoded_values: Optional[List[Dict[str, Any]]] = None,
    coherence_report: Optional[List[str]] = None,
    telemetry_report: Optional[List[str]] = None,
    constitutional_report: Optional[List[str]] = None,
    environment_report: Optional[List[str]] = None,
    pipeline_health_report: Optional[List[str]] = None,
) -> str:
    """1画面レポートを生成する。"""
    lines = ["# Environment Audit Report", ""]

    # セクション順序: Environment Fitness → Constitutional → Coherence → Telemetry → Pipeline Health
    if environment_report:
        lines.extend(environment_report)

    if constitutional_report:
        lines.extend(constitutional_report)

    if coherence_report:
        lines.extend(coherence_report)

    if telemetry_report:
        lines.extend(telemetry_report)

    # Pipeline Health（既存スコアセクションの後に配置）
    if pipeline_health_report:
        lines.extend(pipeline_health_report)

    # サマリ
    total = sum(len(v) for v in artifacts.values())
    lines.append(f"## Summary: {total} artifacts found")
    for category, paths in artifacts.items():
        lines.append(f"- {category}: {len(paths)}")
    lines.append("")

    # 行数超過
    if violations:
        lines.append(f"## Line Limit Violations ({len(violations)})")
        for v in violations:
            lines.append(f"- {v['file']}: {v['lines']}/{v['limit']} lines")
        lines.append("")

    # Memory Health（Line Limit Violations の直後）
    if project_dir is not None:
        memory_health = build_memory_health_section(artifacts, project_dir)
        if memory_health:
            lines.extend(memory_health)

    # 使用状況（PJ 固有のみ）
    if usage:
        lines.append("## Usage (last 30 days)")
        for skill, count in list(usage.items())[:15]:
            lines.append(f"- {skill}: {count} invocations")
        lines.append("")

    # プラグイン利用サマリ
    if plugin_usage:
        summary_parts = [f"{name}({count})" for name, count in plugin_usage.items()]
        lines.append(f"Plugin usage: {' / '.join(summary_parts)}")
        lines.append("")

    # 品質推移
    if quality_baselines is not None:
        trends = build_quality_trends_section(quality_baselines, usage)
        if trends:
            lines.extend(trends)

    # OpenSpec ワークフロー分析
    if openspec_analytics:
        lines.extend(openspec_analytics)

    # 重複候補
    if duplicates:
        lines.append(f"## Potential Duplicates ({len(duplicates)})")
        for d in duplicates:
            lines.append(f"- {d['name']}: {', '.join(d['paths'])}")
        lines.append("")

    # Hardcoded Values 警告
    if hardcoded_values:
        lines.append(f"## Hardcoded Values ({len(hardcoded_values)})")
        for hv in hardcoded_values:
            detail = hv.get("detail", {})
            lines.append(
                f"- {hv['file']}:{detail.get('line', '?')} "
                f"`{detail.get('matched', '?')}` ({detail.get('pattern_type', '?')}, "
                f"confidence={detail.get('confidence_score', 0):.2f})"
            )
        lines.append("")

    # Reference Type 未設定警告
    if untagged_reference_candidates:
        lines.append(f"## Reference Type Warning ({len(untagged_reference_candidates)})")
        lines.append("以下のスキルはゼロ呼び出しかつ `type` 未設定です。参照型スキルの場合は frontmatter に `type: reference` を追加してください。")
        for c in untagged_reference_candidates:
            lines.append(f"- {c['skill_name']}")
        lines.append("")

    # Scope Advisory
    if advisories:
        lines.append("## Scope Advisory")
        for a in advisories:
            lines.append(
                f"- {a['skill']}: {a['project_count']} projects, "
                f"last used {a['last_used'][:10] if a['last_used'] else 'never'} → {a['recommendation']}"
            )
        lines.append("")

    return "\n".join(lines)


_AUDIT_HISTORY_FILE = DATA_DIR / "audit-history.jsonl"
_MAX_AUDIT_HISTORY = 100
_DEGRADATION_THRESHOLD = 0.10  # 10% drop


def _record_audit_completion(
    coherence_report: Optional[List[str]] = None,
    telemetry_report: Optional[List[str]] = None,
    environment_report: Optional[List[str]] = None,
) -> None:
    """audit 完了時: last_audit_timestamp 更新 + audit-history.jsonl 記録 + 劣化検出。"""
    try:
        # Update last_audit_timestamp in evolve-state.json
        state_file = DATA_DIR / "evolve-state.json"
        state = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        now = datetime.now(timezone.utc).isoformat()
        state["last_audit_timestamp"] = now
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Record to audit-history.jsonl
        history_record: Dict[str, Any] = {"timestamp": now}
        # Extract scores from report lines if available
        for report_lines, key in [
            (coherence_report, "coherence_score"),
            (telemetry_report, "telemetry_score"),
            (environment_report, "environment_score"),
        ]:
            if report_lines:
                score = _extract_score_from_report(report_lines)
                if score is not None:
                    history_record[key] = score

        _append_audit_history(history_record)

        # Degradation detection
        _check_degradation(history_record)
    except Exception as e:
        print(f"[rl-anything:audit] history recording error: {e}", file=sys.stderr)


def _extract_score_from_report(lines: List[str]) -> Optional[float]:
    """レポート行からスコア値を抽出する。"""
    import re
    for line in lines:
        # Match patterns like "Score: 0.85" or "Overall: 0.72"
        m = re.search(r'(?:Score|Overall|Total)[:\s]+(\d+\.?\d*)', line)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def _append_audit_history(record: Dict[str, Any]) -> None:
    """audit-history.jsonl にレコードを追記し、pruning する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    if _AUDIT_HISTORY_FILE.exists():
        lines = _AUDIT_HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines()
    lines.append(json.dumps(record, ensure_ascii=False))
    # Pruning
    if len(lines) > _MAX_AUDIT_HISTORY:
        lines = lines[-_MAX_AUDIT_HISTORY:]
    _AUDIT_HISTORY_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _check_degradation(current: Dict[str, Any]) -> None:
    """前回スコアとの比較で 10% 以上低下時に警告を出力する。"""
    if not _AUDIT_HISTORY_FILE.exists():
        return
    lines = _AUDIT_HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) < 2:
        return
    try:
        prev = json.loads(lines[-2])
    except (json.JSONDecodeError, IndexError):
        return

    for key in ("coherence_score", "telemetry_score", "environment_score"):
        prev_val = prev.get(key)
        curr_val = current.get(key)
        if prev_val is not None and curr_val is not None and prev_val > 0:
            drop = (prev_val - curr_val) / prev_val
            if drop >= _DEGRADATION_THRESHOLD:
                label = key.replace("_", " ").title()
                print(
                    f"⚠ {label} が {drop:.0%} 低下しています "
                    f"({prev_val:.2f} → {curr_val:.2f})",
                    file=sys.stderr,
                )


def run_audit(project_dir: Optional[str] = None, skip_rescore: bool = False, coherence_score: bool = False, telemetry_score: bool = False, constitutional_score: bool = False, pipeline_health: bool = False) -> str:
    """Audit を実行してレポートを返す。"""
    proj = Path(project_dir) if project_dir else Path.cwd()
    artifacts = find_artifacts(proj)
    violations = check_line_limits(artifacts)
    usage_records = load_usage_data(project_root=proj)
    usage = aggregate_usage(usage_records, exclude_plugins=True)
    plugin_usage = aggregate_plugin_usage(usage_records)
    duplicates = detect_duplicates_simple(artifacts)
    registry = load_usage_registry()
    advisories = scope_advisory(registry)

    # 品質計測統合
    quality_baselines = None
    if not skip_rescore:
        try:
            _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
            if str(_scripts_dir) not in sys.path:
                sys.path.insert(0, str(_scripts_dir))
            from quality_monitor import run_quality_monitor
            run_quality_monitor()
        except Exception as e:
            print(f"品質計測スキップ: {e}", file=sys.stderr)

    # ベースラインがあればレポートに含める
    baselines = load_quality_baselines()
    if baselines:
        quality_baselines = baselines

    # OpenSpec ワークフロー分析
    openspec_analytics = build_openspec_analytics_section(usage_records)

    # Reference type 未設定警告
    untagged = detect_untagged_reference_candidates(artifacts, usage)

    # Hardcoded values 検出
    hardcoded_values = []
    for category in ("skills", "rules"):
        for path in artifacts.get(category, []):
            detections = detect_hardcoded_values(str(path))
            for det in detections:
                hardcoded_values.append({
                    "type": "hardcoded_value",
                    "file": str(path),
                    "detail": det,
                    "source": "detect_hardcoded_values",
                })

    # Coherence Score
    coherence_report_lines = None
    if coherence_score:
        try:
            _fitness_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "rl"
            if str(_fitness_dir) not in sys.path:
                sys.path.insert(0, str(_fitness_dir))
            from fitness.coherence import compute_coherence_score, format_coherence_report
            result = compute_coherence_score(proj)
            coherence_report_lines = format_coherence_report(result)
        except Exception as e:
            print(f"Coherence Score スキップ: {e}", file=sys.stderr)

    # Telemetry Score
    telemetry_report_lines = None
    if telemetry_score:
        try:
            _fitness_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "rl"
            if str(_fitness_dir) not in sys.path:
                sys.path.insert(0, str(_fitness_dir))
            from fitness.telemetry import compute_telemetry_score, format_telemetry_report
            tel_result = compute_telemetry_score(proj)
            telemetry_report_lines = format_telemetry_report(tel_result)
        except Exception as e:
            print(f"Telemetry Score スキップ: {e}", file=sys.stderr)

    # Constitutional Score
    constitutional_report_lines = None
    if constitutional_score:
        try:
            _fitness_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "rl"
            if str(_fitness_dir) not in sys.path:
                sys.path.insert(0, str(_fitness_dir))
            from fitness.constitutional import compute_constitutional_score
            from fitness.chaos import compute_chaos_score, format_chaos_report
            con_result = compute_constitutional_score(proj)
            constitutional_report_lines = _format_constitutional_report(con_result)
            # Chaos Testing
            try:
                chaos_result = compute_chaos_score(proj)
                chaos_lines = format_chaos_report(chaos_result)
                if constitutional_report_lines is not None:
                    constitutional_report_lines.extend(chaos_lines)
                else:
                    constitutional_report_lines = chaos_lines
            except Exception as e:
                print(f"Chaos Testing スキップ: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Constitutional Score スキップ: {e}", file=sys.stderr)

    # Environment Fitness（複数スコア指定時）
    environment_report_lines = None
    score_count = sum([coherence_score, telemetry_score, constitutional_score])
    if score_count >= 2:
        try:
            from fitness.environment import compute_environment_fitness, format_environment_report
            env_result = compute_environment_fitness(proj)
            environment_report_lines = format_environment_report(env_result)
        except Exception as e:
            print(f"Environment Fitness スキップ: {e}", file=sys.stderr)

    # Pipeline Health（LLM 不使用）
    pipeline_health_report_lines = None
    if pipeline_health:
        try:
            from pipeline_reflector import build_pipeline_health_section
            pipeline_health_report_lines = build_pipeline_health_section()
        except Exception as e:
            print(f"Pipeline Health スキップ: {e}", file=sys.stderr)

    # Record audit completion: update last_audit_timestamp + audit-history.jsonl
    _record_audit_completion(
        coherence_report=coherence_report_lines,
        telemetry_report=telemetry_report_lines,
        environment_report=environment_report_lines,
    )

    return generate_report(
        artifacts, violations, usage, duplicates, advisories,
        quality_baselines, project_dir=proj,
        plugin_usage=plugin_usage if plugin_usage else None,
        openspec_analytics=openspec_analytics if openspec_analytics else None,
        untagged_reference_candidates=untagged if untagged else None,
        hardcoded_values=hardcoded_values if hardcoded_values else None,
        coherence_report=coherence_report_lines,
        telemetry_report=telemetry_report_lines,
        constitutional_report=constitutional_report_lines,
        environment_report=environment_report_lines,
        pipeline_health_report=pipeline_health_report_lines,
    )


if __name__ == "__main__":
    import argparse as _argparse

    _parser = _argparse.ArgumentParser(description="環境の健康診断")
    _parser.add_argument("project", nargs="?", default=None, help="プロジェクトディレクトリ")
    _parser.add_argument("--skip-rescore", action="store_true", help="品質計測をスキップ")
    _parser.add_argument("--memory-context", action="store_true", help="MEMORY 検証コンテキストを JSON 出力")
    _parser.add_argument("--coherence-score", action="store_true", help="Coherence Score セクションを表示")
    _parser.add_argument("--telemetry-score", action="store_true", help="Telemetry Score セクションを表示")
    _parser.add_argument("--constitutional-score", action="store_true", help="Constitutional Score セクションを表示")
    _parser.add_argument("--pipeline-health", action="store_true", help="Pipeline Health セクションを表示")
    _args = _parser.parse_args()
    if _args.memory_context:
        proj = Path(_args.project) if _args.project else Path.cwd()
        ctx = build_memory_verification_context(proj)
        print(json.dumps(ctx, ensure_ascii=False, indent=2))
    else:
        print(run_audit(_args.project, skip_rescore=_args.skip_rescore, coherence_score=_args.coherence_score, telemetry_score=_args.telemetry_score, constitutional_score=_args.constitutional_score, pipeline_health=_args.pipeline_health))
