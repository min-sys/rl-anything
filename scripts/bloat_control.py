#!/usr/bin/env python3
"""肥大化制御スクリプト。

サイズバリデーション、bloat check、Scope Advisor、Plugin Bundling 提案を提供する。
既存の _regression_gate() ロジックを共通ユーティリティとして抽出し再利用。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_this_dir = Path(__file__).resolve().parent
_plugin_root = _this_dir.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))

from audit import DATA_DIR, find_artifacts, load_usage_registry

# 行数制限
LIMITS = {
    "SKILL.md": 500,
    "rules": 3,
    "memory": 120,
    "CLAUDE.md": 200,
    "MEMORY.md": 200,
}

# Bloat check 警告閾値
BLOAT_THRESHOLDS = {
    "claude_md_lines": 150,
    "memory_md_lines": 150,
    "rules_count": 100,
    "skills_count": 30,
}

# 禁止パターン（_regression_gate から抽出）
FORBIDDEN_PATTERNS = ["TODO", "FIXME", "HACK", "XXX"]


def validate_artifact(
    content: str,
    artifact_type: str,
    forbidden_patterns: Optional[List[str]] = None,
) -> Tuple[bool, Optional[str]]:
    """アーティファクトのサイズバリデーション。

    全パイプライン（evolve / optimize / discover）で再利用する共通ユーティリティ。
    既存の GeneticOptimizer._regression_gate() から抽出。

    Args:
        content: アーティファクトの内容
        artifact_type: "SKILL.md", "rules", "memory", "CLAUDE.md", "MEMORY.md"
        forbidden_patterns: 追加の禁止パターン

    Returns:
        (passed, reason) のタプル
    """
    if not content or not content.strip():
        return False, "empty"

    max_lines = LIMITS.get(artifact_type)
    if max_lines is not None:
        lines = content.count("\n") + 1
        if lines > max_lines:
            return False, f"line_limit_exceeded({lines}/{max_lines})"

    patterns = FORBIDDEN_PATTERNS + (forbidden_patterns or [])
    for pattern in patterns:
        if pattern in content:
            return False, f"forbidden_pattern({pattern})"

    return True, None


def suggest_split(content: str, artifact_type: str) -> Optional[Dict[str, Any]]:
    """超過時に分割を提案する（MUST）。"""
    lines = content.count("\n") + 1
    max_lines = LIMITS.get(artifact_type, 999999)

    if lines <= max_lines:
        return None

    return {
        "current_lines": lines,
        "limit": max_lines,
        "action": "split",
        "message": f"{artifact_type} が {lines}/{max_lines} 行で超過。分割を提案します。",
    }


def bloat_check(project_dir: Optional[str] = None) -> Dict[str, Any]:
    """evolve 実行時の bloat check。"""
    proj = Path(project_dir) if project_dir else Path.cwd()
    artifacts = find_artifacts(proj)
    warnings = []

    # CLAUDE.md 行数チェック
    for path in artifacts.get("claude_md", []):
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        if lines > BLOAT_THRESHOLDS["claude_md_lines"]:
            warnings.append({
                "type": "claude_md",
                "file": str(path),
                "lines": lines,
                "threshold": BLOAT_THRESHOLDS["claude_md_lines"],
                "action": "分割または不要セクション削除を推奨",
            })

    # rules 数チェック
    rules_count = len(artifacts.get("rules", []))
    if rules_count > BLOAT_THRESHOLDS["rules_count"]:
        warnings.append({
            "type": "rules_count",
            "count": rules_count,
            "threshold": BLOAT_THRESHOLDS["rules_count"],
            "action": "統合またはアーカイブを推奨",
        })

    # skills 数チェック
    skills_count = len(artifacts.get("skills", []))
    if skills_count > BLOAT_THRESHOLDS["skills_count"]:
        warnings.append({
            "type": "skills_count",
            "count": skills_count,
            "threshold": BLOAT_THRESHOLDS["skills_count"],
            "action": "統合またはアーカイブを推奨",
        })

    # memory チェック
    for path in artifacts.get("memory", []):
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        limit = BLOAT_THRESHOLDS["memory_md_lines"]
        if lines > limit:
            warnings.append({
                "type": "memory",
                "file": str(path),
                "lines": lines,
                "threshold": limit,
                "action": "トピック別ファイルへの分割を推奨",
            })

    return {
        "warnings": warnings,
        "warning_count": len(warnings),
        "artifacts_summary": {
            "rules": rules_count,
            "skills": skills_count,
            "memory": len(artifacts.get("memory", [])),
        },
    }


def scope_advisor() -> List[Dict[str, Any]]:
    """Usage Registry ベースのスコープ最適化提案。"""
    registry = load_usage_registry()
    proposals = []

    for skill, records in registry.items():
        projects = set(r.get("project_path", "") for r in records)

        if len(projects) == 0:
            proposals.append({
                "skill": skill,
                "current_scope": "global",
                "recommendation": "archive",
                "reason": "どのプロジェクトでも使用されていません",
            })
        elif len(projects) == 1:
            proposals.append({
                "skill": skill,
                "current_scope": "global",
                "recommendation": "demote_to_project",
                "reason": f"1プロジェクトのみで使用: {list(projects)[0]}",
            })

    return proposals


def detect_plugin_bundles() -> List[Dict[str, Any]]:
    """Plugin Bundling 提案: 常に一緒に使われるスキル群を検出。"""
    registry = load_usage_registry()
    bundles = []

    # プロジェクト別のスキルセットを構築
    project_skills: Dict[str, set] = defaultdict(set)
    for skill, records in registry.items():
        for rec in records:
            proj = rec.get("project_path", "")
            if proj:
                project_skills[proj].add(skill)

    # 3つ以上のスキルが同じプロジェクト群で使われているパターンを検出
    if len(project_skills) < 2:
        return bundles

    # 各スキルが使用されるプロジェクトセットを構築
    skill_projects: Dict[str, frozenset] = {}
    for skill in registry:
        projects = frozenset(
            r.get("project_path", "") for r in registry[skill] if r.get("project_path")
        )
        skill_projects[skill] = projects

    # 同じプロジェクトセットを持つスキルグループを検出
    groups: Dict[frozenset, List[str]] = defaultdict(list)
    for skill, projects in skill_projects.items():
        if len(projects) >= 2:
            groups[projects].append(skill)

    for projects, skills in groups.items():
        if len(skills) >= 3:
            bundles.append({
                "skills": skills,
                "projects": list(projects),
                "recommendation": "これらのスキルを plugin としてバンドル化することを推奨",
            })

    return bundles


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else None
    result = bloat_check(project)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    proposals = scope_advisor()
    if proposals:
        print("\n## Scope Advisor")
        print(json.dumps(proposals, ensure_ascii=False, indent=2))

    bundles = detect_plugin_bundles()
    if bundles:
        print("\n## Plugin Bundling")
        print(json.dumps(bundles, ensure_ascii=False, indent=2))
