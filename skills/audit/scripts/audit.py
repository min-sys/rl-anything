#!/usr/bin/env python3
"""環境の健康診断スクリプト。

全 skills / rules / memory の棚卸し + 行数チェック + 使用状況集計を行い、
1画面レポートを出力する。
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 行数制限
LIMITS = {
    "CLAUDE.md": 200,
    "rules": 3,
    "SKILL.md": 500,
    "MEMORY.md": 200,
    "memory": 120,
}

DATA_DIR = Path.home() / ".claude" / "rl-anything"


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


def aggregate_usage(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """スキル使用回数を集計する。"""
    counts: Dict[str, int] = {}
    for rec in records:
        skill = rec.get("skill_name", "unknown")
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
    """LLM ベースの意味的類似度判定。閾値は 80%。

    audit-report spec の Single Source of Truth。
    prune はこの関数の結果を利用する。

    Note: 実際の LLM 呼び出しは別途 Claude CLI で実行。
    ここでは呼び出しインターフェースのみ定義。
    """
    # LLM 呼び出しのスタブ — 実行時は Claude CLI を使用
    candidates = []
    all_paths = []
    for category in ["skills", "rules"]:
        all_paths.extend(artifacts.get(category, []))

    # ペアワイズ比較のための候補リストを生成
    for i in range(len(all_paths)):
        for j in range(i + 1, len(all_paths)):
            candidates.append({
                "path_a": str(all_paths[i]),
                "path_b": str(all_paths[j]),
                "threshold": threshold,
            })

    return candidates


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


def generate_report(
    artifacts: Dict[str, List[Path]],
    violations: List[Dict[str, Any]],
    usage: Dict[str, int],
    duplicates: List[Dict[str, Any]],
    advisories: List[Dict[str, Any]],
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

    # 使用状況
    if usage:
        lines.append("## Usage (last 30 days)")
        for skill, count in list(usage.items())[:15]:
            lines.append(f"- {skill}: {count} invocations")
        lines.append("")

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


def run_audit(project_dir: Optional[str] = None) -> str:
    """Audit を実行してレポートを返す。"""
    proj = Path(project_dir) if project_dir else Path.cwd()
    artifacts = find_artifacts(proj)
    violations = check_line_limits(artifacts)
    usage_records = load_usage_data()
    usage = aggregate_usage(usage_records)
    duplicates = detect_duplicates_simple(artifacts)
    registry = load_usage_registry()
    advisories = scope_advisory(registry)
    return generate_report(artifacts, violations, usage, duplicates, advisories)


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else None
    print(run_audit(project))
