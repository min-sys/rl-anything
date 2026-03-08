#!/usr/bin/env python3
"""環境全体の構造的整合性を測る Coherence Score。

4軸（Coverage / Consistency / Completeness / Efficiency）で
LLM コストゼロの静的分析スコア（0.0〜1.0）を算出する。
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent


def _ensure_paths():
    """遅延パス追加。テスト時のパス衝突を防ぐ。"""
    paths = [
        str(_plugin_root / "scripts" / "lib"),
        str(_plugin_root / "scripts"),
        str(_plugin_root / "skills" / "audit" / "scripts"),
    ]
    for p in paths:
        if p not in sys.path:
            sys.path.insert(0, p)

THRESHOLDS = {
    "skill_min_lines": 50,
    "rule_max_lines": 3,
    "claude_md_max_lines": 200,
    "near_limit_pct": 0.80,
    "unused_skill_days": 30,
    "advice_threshold": 0.7,
}

WEIGHTS = {
    "coverage": 0.25,
    "consistency": 0.30,
    "completeness": 0.25,
    "efficiency": 0.20,
}

# Coverage チェック項目
_COVERAGE_ITEMS = [
    "claude_md",
    "rules",
    "skills",
    "memory",
    "hooks",
    "skills_section",
]


def _find_project_artifacts(project_dir: Path) -> Dict[str, Any]:
    """プロジェクト内のアーティファクトを探索する。"""
    claude_dir = project_dir / ".claude"
    result: Dict[str, Any] = {
        "claude_md": None,
        "rules": [],
        "skills": [],
        "memory": [],
        "hooks": False,
        "skills_section": False,
        "claude_dir_exists": claude_dir.exists(),
    }

    # CLAUDE.md
    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists():
        result["claude_md"] = claude_md

    # Rules
    rules_dir = claude_dir / "rules"
    if rules_dir.exists():
        result["rules"] = list(rules_dir.glob("*.md"))

    # Skills
    skills_dir = claude_dir / "skills"
    if skills_dir.exists():
        result["skills"] = list(skills_dir.rglob("SKILL.md"))

    # Memory
    memory_dir = claude_dir / "memory"
    if memory_dir.exists():
        result["memory"] = list(memory_dir.glob("*.md"))

    # Hooks (settings.json に hooks 設定があるか)
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            result["hooks"] = bool(settings.get("hooks"))
        except (json.JSONDecodeError, OSError):
            pass

    # CLAUDE.md に Skills セクションがあるか
    if result["claude_md"]:
        try:
            content = result["claude_md"].read_text(encoding="utf-8")
            result["skills_section"] = bool(
                re.search(r"^#{1,3}\s+[Ss]kills?\b", content, re.MULTILINE)
            )
        except (OSError, UnicodeDecodeError):
            pass

    return result


def _find_artifacts_local(project_dir: Path) -> Dict[str, List[Path]]:
    """プロジェクト限定のアーティファクト探索（audit互換形式、グローバル除外）。"""
    claude_dir = project_dir / ".claude"
    result: Dict[str, List[Path]] = {
        "skills": [],
        "rules": [],
        "memory": [],
        "claude_md": [],
    }
    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists():
        result["claude_md"].append(claude_md)
    skills_dir = claude_dir / "skills"
    if skills_dir.exists():
        result["skills"] = list(skills_dir.rglob("SKILL.md"))
    rules_dir = claude_dir / "rules"
    if rules_dir.exists():
        result["rules"] = list(rules_dir.glob("*.md"))
    # ローカル .claude/memory/
    memory_dir = claude_dir / "memory"
    if memory_dir.exists():
        result["memory"] = list(memory_dir.glob("*.md"))
    # グローバル auto-memory: ~/.claude/projects/<encoded-path>/memory/
    if not result["memory"]:
        resolved = str(project_dir.resolve())
        encoded = resolved.replace("/", "-")
        home = Path.home()
        for candidate in [encoded, encoded.lstrip("-")]:
            auto_mem_dir = home / ".claude" / "projects" / candidate / "memory"
            if auto_mem_dir.is_dir():
                result["memory"] = list(auto_mem_dir.glob("*.md"))
                break
    return result


# ---------- Coverage ----------

def score_coverage(project_dir: Path) -> Tuple[float, Dict[str, Any]]:
    """環境の各レイヤーが最低限存在するかチェックする。

    Returns:
        (score, details) — score は 0.0〜1.0、details は各項目の pass/fail。
    """
    artifacts = _find_project_artifacts(project_dir)

    if not artifacts["claude_dir_exists"] and not artifacts["claude_md"]:
        return 0.0, {item: False for item in _COVERAGE_ITEMS}

    checks = {
        "claude_md": artifacts["claude_md"] is not None,
        "rules": len(artifacts["rules"]) > 0,
        "skills": len(artifacts["skills"]) > 0,
        "memory": len(artifacts["memory"]) > 0,
        "hooks": artifacts["hooks"],
        "skills_section": artifacts["skills_section"],
    }

    passed = sum(1 for v in checks.values() if v)
    score = passed / len(checks)
    return round(score, 4), checks


# ---------- Consistency ----------

def score_consistency(project_dir: Path) -> Tuple[float, Dict[str, Any]]:
    """レイヤー間の矛盾や断絶がないかチェックする。

    チェック項目:
    1. CLAUDE.md で言及された Skill の実在チェック
    2. MEMORY.md 内のファイルパス参照の実在チェック
    3. トリガーワード重複チェック

    Returns:
        (score, details)
    """
    details: Dict[str, Any] = {
        "skill_existence": {"pass": True, "missing": []},
        "memory_paths": {"pass": True, "stale": []},
        "trigger_duplicates": {"pass": True, "duplicates": []},
    }

    checks_total = 0
    checks_passed = 0

    # 1. CLAUDE.md で言及された Skill の実在チェック
    claude_md = project_dir / "CLAUDE.md"
    skills_dir = project_dir / ".claude" / "skills"
    if claude_md.exists():
        checks_total += 1
        mentioned = _extract_mentioned_skills(claude_md)
        missing = []
        for skill_name in mentioned:
            skill_path = skills_dir / skill_name
            if not skill_path.exists():
                # SKILL.md があるサブディレクトリを確認
                if not (skill_path / "SKILL.md").exists() and not skill_path.is_dir():
                    missing.append(skill_name)
        if missing:
            details["skill_existence"] = {"pass": False, "missing": missing}
        else:
            checks_passed += 1

    # 2. MEMORY.md 内のファイルパス参照の実在チェック
    memory_dir = project_dir / ".claude" / "memory"
    if memory_dir.exists():
        memory_md = memory_dir / "MEMORY.md"
        # 他の memory ファイルも含む
        memory_files = list(memory_dir.glob("*.md"))
        stale_paths: List[str] = []
        for mf in memory_files:
            try:
                content = mf.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            stale_paths.extend(_check_memory_paths(content, project_dir))

        if memory_files:
            checks_total += 1
            if stale_paths:
                details["memory_paths"] = {"pass": False, "stale": stale_paths}
            else:
                checks_passed += 1

    # 3. トリガーワード重複チェック
    _ensure_paths()
    from skill_triggers import extract_skill_triggers
    triggers_data = extract_skill_triggers(project_root=project_dir)
    if triggers_data:
        checks_total += 1
        trigger_map: Dict[str, List[str]] = {}
        for entry in triggers_data:
            for trigger in entry["triggers"]:
                t_lower = trigger.lower()
                if t_lower not in trigger_map:
                    trigger_map[t_lower] = []
                trigger_map[t_lower].append(entry["skill"])
        duplicates = {
            t: skills for t, skills in trigger_map.items() if len(skills) > 1
        }
        if duplicates:
            details["trigger_duplicates"] = {
                "pass": False,
                "duplicates": [
                    {"trigger": t, "skills": s} for t, s in duplicates.items()
                ],
            }
        else:
            checks_passed += 1

    score = checks_passed / checks_total if checks_total > 0 else 1.0
    return round(score, 4), details


def _extract_mentioned_skills(claude_md: Path) -> List[str]:
    """CLAUDE.md の Skills セクションから言及されたスキル名を抽出する。"""
    try:
        content = claude_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    lines = content.splitlines()
    in_skills = False
    skills = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{1,3}\s+[Ss]kills?\b", stripped):
            in_skills = True
            continue
        if in_skills and re.match(r"^#{1,3}\s+", stripped) and not re.match(
            r"^#{1,3}\s+[Ss]kills?\b", stripped
        ):
            break
        if not in_skills:
            continue
        # `- skill-name: ...` or `- /plugin:skill-name: ...`
        m = re.match(r"^-\s+/?([a-zA-Z0-9_:-]+)\s*[:：]", stripped)
        if m:
            name = m.group(1)
            # plugin:skill → skill
            if ":" in name:
                name = name.split(":", 1)[1]
            skills.append(name)
    return skills


_PATH_PATTERN = re.compile(
    r"(?:^|\s)([a-zA-Z_.][a-zA-Z0-9_./\-]*(?:\.(?:py|md|json|jsonl|yaml|yml|toml|sh|ts|js)|/))"
)


def _check_memory_paths(content: str, project_dir: Path) -> List[str]:
    """MEMORY.md 内のファイルパス参照が実在するかチェックする。"""
    stale = []
    in_code_block = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for m in _PATH_PATTERN.finditer(line):
            path_str = m.group(1).rstrip("/")
            # 短すぎるパスやよくある誤検出を除外
            if len(path_str) < 5 or path_str.startswith("http"):
                continue
            # セグメントが2つ以上あるパスのみ（e.g. scripts/lib/foo.py）
            if "/" not in path_str:
                continue
            check = project_dir / path_str
            if not check.exists():
                stale.append(path_str)
    return stale


# ---------- Completeness ----------

def score_completeness(project_dir: Path) -> Tuple[float, Dict[str, Any]]:
    """定義されたものが動くレベルで完成しているかチェックする。

    チェック項目:
    1. Skill 行数（最低50行）と必須セクション（Usage, Steps）
    2. Rule 行数制約（3行以内）
    3. CLAUDE.md 行数（200行以内）
    4. ハードコード値検出

    Returns:
        (score, details)
    """
    details: Dict[str, Any] = {
        "skill_quality": {"pass": True, "issues": []},
        "rule_compliance": {"pass": True, "issues": []},
        "claude_md_size": {"pass": True},
        "hardcoded_values": {"pass": True, "count": 0},
    }

    checks_total = 0
    checks_passed = 0

    artifacts = _find_project_artifacts(project_dir)

    # 1. Skill 行数と必須セクション
    if artifacts["skills"]:
        checks_total += 1
        skill_issues = []
        for skill_path in artifacts["skills"]:
            try:
                content = skill_path.read_text(encoding="utf-8")
                lines = content.count("\n") + 1
            except (OSError, UnicodeDecodeError):
                continue
            issues_for_skill: List[str] = []
            if lines < THRESHOLDS["skill_min_lines"]:
                issues_for_skill.append(f"{lines} lines (min {THRESHOLDS['skill_min_lines']})")
            # 必須セクション（## Usage, **Usage** 等のバリエーション対応）
            for section in ("Usage", "Steps"):
                if not re.search(
                    rf"^#{{1,4}}\s+\*?\*?{section}\*?\*?|^\*\*{section}\*\*",
                    content,
                    re.MULTILINE | re.IGNORECASE,
                ):
                    issues_for_skill.append(f"missing section: {section}")
            if issues_for_skill:
                skill_issues.append({
                    "file": str(skill_path),
                    "issues": issues_for_skill,
                })
        if skill_issues:
            details["skill_quality"] = {"pass": False, "issues": skill_issues}
        else:
            checks_passed += 1

    # 2. Rule 行数制約
    if artifacts["rules"]:
        checks_total += 1
        rule_issues = []
        for rule_path in artifacts["rules"]:
            try:
                content = rule_path.read_text(encoding="utf-8")
                # 空行と見出し行を除いた実質行数
                meaningful_lines = [
                    l for l in content.splitlines()
                    if l.strip() and not l.strip().startswith("#")
                ]
                if len(meaningful_lines) > THRESHOLDS["rule_max_lines"]:
                    rule_issues.append({
                        "file": str(rule_path),
                        "lines": len(meaningful_lines),
                    })
            except (OSError, UnicodeDecodeError):
                continue
        if rule_issues:
            details["rule_compliance"] = {"pass": False, "issues": rule_issues}
        else:
            checks_passed += 1

    # 3. CLAUDE.md 行数
    if artifacts["claude_md"]:
        checks_total += 1
        try:
            content = artifacts["claude_md"].read_text(encoding="utf-8")
            lines = content.count("\n") + 1
            if lines > THRESHOLDS["claude_md_max_lines"]:
                details["claude_md_size"] = {
                    "pass": False,
                    "lines": lines,
                    "limit": THRESHOLDS["claude_md_max_lines"],
                }
            else:
                checks_passed += 1
        except (OSError, UnicodeDecodeError):
            checks_passed += 1

    # 4. ハードコード値検出
    _ensure_paths()
    from hardcoded_detector import detect_hardcoded_values
    all_files = list(artifacts["skills"]) + list(artifacts["rules"])
    if all_files:
        checks_total += 1
        hardcoded_count = 0
        for f in all_files:
            detections = detect_hardcoded_values(str(f))
            hardcoded_count += len(detections)
        if hardcoded_count > 0:
            details["hardcoded_values"] = {"pass": False, "count": hardcoded_count}
        else:
            checks_passed += 1

    score = checks_passed / checks_total if checks_total > 0 else 1.0
    return round(score, 4), details


# ---------- Efficiency ----------

def score_efficiency(project_dir: Path, *, data_dir: Optional[Path] = None) -> Tuple[float, Dict[str, Any]]:
    """冗長さや肥大化がないかチェックする。

    チェック項目:
    1. 意味的重複 Skill
    2. near-limit（80% 超え）
    3. 未使用 Skill（30日以上ゼロ invoke）
    4. 孤立 Rule（CLAUDE.md で参照されていない）

    Returns:
        (score, details)
    """
    details: Dict[str, Any] = {
        "duplicate_skills": {"pass": True, "pairs": []},
        "near_limit": {"pass": True, "files": []},
        "unused_skills": {"pass": True, "skills": [], "skipped": False},
        "orphan_rules": {"pass": True, "rules": []},
    }

    checks: List[bool] = []

    _ensure_paths()
    from audit import detect_duplicates_simple, LIMITS, NEAR_LIMIT_RATIO

    # プロジェクト限定のアーティファクト探索（グローバル ~/.claude/ を含めない）
    artifacts = _find_artifacts_local(project_dir)

    # 1. 意味的重複 Skill
    duplicates = detect_duplicates_simple(artifacts)
    if duplicates:
        details["duplicate_skills"] = {
            "pass": False,
            "pairs": [{"name": d["name"], "paths": d["paths"]} for d in duplicates],
        }
        checks.append(False)
    else:
        checks.append(True)

    # 2. near-limit
    near_limit_files = []
    for category, limit_key in [("skills", "SKILL.md"), ("rules", "rules"), ("claude_md", "CLAUDE.md")]:
        for path in artifacts.get(category, []):
            try:
                content = path.read_text(encoding="utf-8")
                lines = content.count("\n") + 1
                limit = LIMITS.get(limit_key, 500)
                if lines >= int(limit * NEAR_LIMIT_RATIO):
                    near_limit_files.append({
                        "file": str(path),
                        "lines": lines,
                        "limit": limit,
                    })
            except (OSError, UnicodeDecodeError):
                continue
    if near_limit_files:
        details["near_limit"] = {"pass": False, "files": near_limit_files}
        checks.append(False)
    else:
        checks.append(True)

    # 3. 未使用 Skill（usage.jsonl ベース）
    if data_dir is None:
        data_dir = Path.home() / ".claude" / "rl-anything"
    usage_file = data_dir / "usage.jsonl"
    if usage_file.exists():
        skill_names = set()
        for path in artifacts.get("skills", []):
            skill_names.add(path.parent.name)

        used_skills = _get_used_skills(usage_file, THRESHOLDS["unused_skill_days"])
        unused = [s for s in skill_names if s not in used_skills]
        if unused:
            details["unused_skills"] = {"pass": False, "skills": unused, "skipped": False}
            checks.append(False)
        else:
            checks.append(True)
    else:
        details["unused_skills"]["skipped"] = True
        # skip: スコアに含めない

    # 4. 孤立 Rule
    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists() and artifacts.get("rules"):
        try:
            claude_content = claude_md.read_text(encoding="utf-8").lower()
        except (OSError, UnicodeDecodeError):
            claude_content = ""
        orphan_rules = []
        for rule_path in artifacts["rules"]:
            rule_name = rule_path.stem.lower()
            # CLAUDE.md で rule 名が言及されているか
            if rule_name not in claude_content:
                orphan_rules.append(str(rule_path))
        if orphan_rules:
            details["orphan_rules"] = {"pass": False, "rules": orphan_rules}
            checks.append(False)
        else:
            checks.append(True)

    score = sum(1 for c in checks if c) / len(checks) if checks else 1.0
    return round(score, 4), details


def _get_used_skills(usage_file: Path, days: int) -> set:
    """usage.jsonl から直近 N 日間で使用されたスキル名を返す。"""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    used = set()
    try:
        with open(usage_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = record.get("timestamp", "")
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt < cutoff:
                        continue
                except (ValueError, AttributeError):
                    continue
                skill = record.get("skill", "")
                if skill:
                    used.add(skill)
    except (OSError, UnicodeDecodeError):
        pass
    return used


# ---------- 統合スコア ----------

def compute_coherence_score(project_dir: Path) -> Dict[str, Any]:
    """4軸の重み付き平均で統合 Coherence Score を算出する。

    Returns:
        {
            "overall": float,
            "coverage": float,
            "consistency": float,
            "completeness": float,
            "efficiency": float,
            "details": {
                "coverage": {...},
                "consistency": {...},
                "completeness": {...},
                "efficiency": {...},
            },
        }
    """
    project_dir = Path(project_dir)

    cov_score, cov_details = score_coverage(project_dir)
    con_score, con_details = score_consistency(project_dir)
    com_score, com_details = score_completeness(project_dir)
    eff_score, eff_details = score_efficiency(project_dir)

    overall = (
        WEIGHTS["coverage"] * cov_score
        + WEIGHTS["consistency"] * con_score
        + WEIGHTS["completeness"] * com_score
        + WEIGHTS["efficiency"] * eff_score
    )

    return {
        "overall": round(overall, 4),
        "coverage": cov_score,
        "consistency": con_score,
        "completeness": com_score,
        "efficiency": eff_score,
        "details": {
            "coverage": cov_details,
            "consistency": con_details,
            "completeness": com_details,
            "efficiency": eff_details,
        },
    }


def format_coherence_report(result: Dict[str, Any]) -> List[str]:
    """Coherence Score を audit レポート用にフォーマットする。"""
    lines = [f"## Environment Coherence Score: {result['overall']:.2f}", ""]

    for axis in ("coverage", "consistency", "completeness", "efficiency"):
        score = result[axis]
        bar_filled = int(score * 20)
        bar_empty = 20 - bar_filled
        bar = "\u2588" * bar_filled + "\u2591" * bar_empty

        # 低スコア軸への注釈
        annotation = ""
        if score < THRESHOLDS["advice_threshold"]:
            axis_details = result["details"].get(axis, {})
            issues = _summarize_issues(axis, axis_details)
            if issues:
                annotation = f" \u2190 {issues}"

        lines.append(
            f"{axis.capitalize():14s} {score:.2f} {bar}{annotation}"
        )

    # advice_threshold 未満の軸の詳細
    low_axes = [
        a for a in ("coverage", "consistency", "completeness", "efficiency")
        if result[a] < THRESHOLDS["advice_threshold"]
    ]
    if low_axes:
        lines.append("")
        lines.append("### Improvement Advice")
        for axis in low_axes:
            axis_details = result["details"].get(axis, {})
            advice = _build_advice(axis, axis_details)
            if advice:
                lines.append(f"**{axis.capitalize()}:**")
                for item in advice:
                    lines.append(f"  - {item}")

    lines.append("")
    return lines


def _summarize_issues(axis: str, details: Dict[str, Any]) -> str:
    """低スコア軸の概要を1行で返す。"""
    summaries = []
    for key, val in details.items():
        if isinstance(val, dict) and not val.get("pass", True):
            summaries.append(key.replace("_", " "))
    return ", ".join(summaries) if summaries else ""


def _build_advice(axis: str, details: Dict[str, Any]) -> List[str]:
    """低スコア軸の改善アドバイスを返す。"""
    advice = []
    for key, val in details.items():
        if not isinstance(val, dict) or val.get("pass", True):
            continue
        if key == "skill_existence":
            missing = val.get("missing", [])
            advice.append(f"CLAUDE.md で言及されているが実在しない Skill: {', '.join(missing)}")
        elif key == "memory_paths":
            stale = val.get("stale", [])
            advice.append(f"MEMORY.md 内の存在しないパス参照: {len(stale)} 件")
        elif key == "trigger_duplicates":
            dups = val.get("duplicates", [])
            for d in dups:
                advice.append(f"トリガー '{d['trigger']}' が {', '.join(d['skills'])} で重複")
        elif key == "skill_quality":
            issues = val.get("issues", [])
            advice.append(f"品質基準を満たさない Skill: {len(issues)} 件")
        elif key == "rule_compliance":
            issues = val.get("issues", [])
            advice.append(f"行数制約を超える Rule: {len(issues)} 件")
        elif key == "claude_md_size":
            advice.append(f"CLAUDE.md が {val.get('lines', '?')}/{val.get('limit', '?')} 行")
        elif key == "hardcoded_values":
            advice.append(f"ハードコード値: {val.get('count', 0)} 件")
        elif key == "duplicate_skills":
            advice.append(f"重複 Skill: {len(val.get('pairs', []))} 件")
        elif key == "near_limit":
            advice.append(f"肥大化警告: {len(val.get('files', []))} ファイル")
        elif key == "unused_skills":
            skills = val.get("skills", [])
            advice.append(f"未使用 Skill: {', '.join(skills)}")
        elif key == "orphan_rules":
            rules = val.get("rules", [])
            advice.append(f"孤立 Rule: {len(rules)} 件")
    return advice
