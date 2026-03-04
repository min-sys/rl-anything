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

from reflect_utils import read_auto_memory

# 行数制限
LIMITS = {
    "CLAUDE.md": 200,
    "rules": 3,
    "SKILL.md": 500,
    "MEMORY.md": 200,
    "memory": 120,
}

DATA_DIR = Path.home() / ".claude" / "rl-anything"

# 肥大化早期警告の閾値（行数上限に対する比率）
NEAR_LIMIT_RATIO = 0.8


# キャッシュ: プラグインがインストールしたスキル名のセット
_plugin_skill_names_cache: Optional[frozenset] = None


def _load_plugin_skill_names() -> frozenset:
    """installed_plugins.json を読み込み、各プラグインの installPath/.claude/skills/
    配下のスキルディレクトリ名を収集して返す。

    結果はモジュールレベルでキャッシュされ、2回目以降は再読み込みしない。
    ファイルが存在しない・不正な場合は空の frozenset を返す。
    """
    global _plugin_skill_names_cache
    if _plugin_skill_names_cache is not None:
        return _plugin_skill_names_cache

    names: set = set()
    installed_plugins_path = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(installed_plugins_path.read_text(encoding="utf-8"))
        plugins = data.get("plugins", {})
        for _key, entries in plugins.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                install_path = entry.get("installPath")
                if not install_path:
                    continue
                skills_dir = Path(install_path) / ".claude" / "skills"
                if skills_dir.is_dir():
                    for child in skills_dir.iterdir():
                        if child.is_dir():
                            names.add(child.name)
    except (OSError, json.JSONDecodeError, TypeError, KeyError):
        pass

    _plugin_skill_names_cache = frozenset(names)
    return _plugin_skill_names_cache


def classify_artifact_origin(path: Path) -> str:
    """スキル/ルールの出自を分類する。

    Returns:
        "plugin" — ~/.claude/plugins/cache/ 配下（または CLAUDE_PLUGINS_DIR）、
                    もしくは .claude/skills/ 配下でプラグインがインストールしたスキル名に一致
        "global" — ~/.claude/skills/ 配下
        "custom" — その他（プロジェクトローカル等）
    """
    resolved = path.expanduser().resolve()
    resolved_str = str(resolved)

    # プラグインキャッシュパス（環境変数でオーバーライド可能）
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

    # プロジェクトの .claude/skills/ 配下にあるスキルが
    # プラグインによりインストールされたものかチェック
    if "/.claude/skills/" in resolved_str:
        parts = resolved.parts
        try:
            skills_idx = len(parts) - 1 - list(reversed(parts)).index("skills")
            if skills_idx + 1 < len(parts):
                skill_dir_name = parts[skills_idx + 1]
                plugin_skill_names = _load_plugin_skill_names()
                if skill_dir_name in plugin_skill_names:
                    return "plugin"
        except ValueError:
            pass

    return "custom"


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
    """行数制限の超過を検出する。"""
    violations = []

    for path in artifacts.get("claude_md", []):
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        if lines > LIMITS["CLAUDE.md"]:
            violations.append({"file": str(path), "lines": lines, "limit": LIMITS["CLAUDE.md"]})

    for path in artifacts.get("rules", []):
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        if lines > LIMITS["rules"]:
            violations.append({"file": str(path), "lines": lines, "limit": LIMITS["rules"]})

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
            results.append((i + 1, path_str))
    return results


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


def load_usage_data(days: int = 30) -> List[Dict[str, Any]]:
    """usage.jsonl から直近N日のデータを読み込む。"""
    usage_file = DATA_DIR / "usage.jsonl"
    if not usage_file.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = []
    for line in usage_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "")
            if ts and ts >= cutoff.isoformat():
                records.append(rec)
        except json.JSONDecodeError:
            continue
    return records


_BUILTIN_TOOLS = {
    "Agent:Explore",
    "Agent:general-purpose",
    "Agent:Plan",
    "commit",
}


def aggregate_usage(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """スキル使用回数を集計する。基本ツールはノイズのため除外。"""
    counts: Dict[str, int] = {}
    for rec in records:
        skill = rec.get("skill_name", "unknown")
        if skill in _BUILTIN_TOOLS:
            continue
        counts[skill] = counts.get(skill, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


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


def generate_report(
    artifacts: Dict[str, List[Path]],
    violations: List[Dict[str, Any]],
    usage: Dict[str, int],
    duplicates: List[Dict[str, Any]],
    advisories: List[Dict[str, Any]],
    quality_baselines: Optional[List[Dict[str, Any]]] = None,
    project_dir: Optional[Path] = None,
) -> str:
    """1画面レポートを生成する。"""
    lines = ["# Environment Audit Report", ""]

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

    # 使用状況
    if usage:
        lines.append("## Usage (last 30 days)")
        for skill, count in list(usage.items())[:15]:
            lines.append(f"- {skill}: {count} invocations")
        lines.append("")

    # 品質推移
    if quality_baselines is not None:
        trends = build_quality_trends_section(quality_baselines, usage)
        if trends:
            lines.extend(trends)

    # 重複候補
    if duplicates:
        lines.append(f"## Potential Duplicates ({len(duplicates)})")
        for d in duplicates:
            lines.append(f"- {d['name']}: {', '.join(d['paths'])}")
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


def run_audit(project_dir: Optional[str] = None, skip_rescore: bool = False) -> str:
    """Audit を実行してレポートを返す。"""
    proj = Path(project_dir) if project_dir else Path.cwd()
    artifacts = find_artifacts(proj)
    violations = check_line_limits(artifacts)
    usage_records = load_usage_data()
    usage = aggregate_usage(usage_records)
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

    return generate_report(artifacts, violations, usage, duplicates, advisories, quality_baselines, project_dir=proj)


if __name__ == "__main__":
    import argparse as _argparse

    _parser = _argparse.ArgumentParser(description="環境の健康診断")
    _parser.add_argument("project", nargs="?", default=None, help="プロジェクトディレクトリ")
    _parser.add_argument("--skip-rescore", action="store_true", help="品質計測をスキップ")
    _args = _parser.parse_args()
    print(run_audit(_args.project, skip_rescore=_args.skip_rescore))
