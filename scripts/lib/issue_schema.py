"""Issue スキーマ定数 — モジュール間のデータ受け渡し契約。

tool_usage_analyzer / skill_evolve（生成）→ evolve（変換）→ remediation（消費）
の3層で共有するフィールド名を定数化し、文字列リテラルの不一致を防止する。
"""
from typing import Any, Dict, List

# ── Issue Type 定数 ─────────────────────────────────

TOOL_USAGE_RULE_CANDIDATE = "tool_usage_rule_candidate"
TOOL_USAGE_HOOK_CANDIDATE = "tool_usage_hook_candidate"
SKILL_EVOLVE_CANDIDATE = "skill_evolve_candidate"
VERIFICATION_RULE_CANDIDATE = "verification_rule_candidate"
SPLIT_CANDIDATE = "split_candidate"

# ── skill_triage 定数 ──────────────────────────────

SKILL_TRIAGE_CREATE = "skill_triage_create"
SKILL_TRIAGE_UPDATE = "skill_triage_update"
SKILL_TRIAGE_SPLIT = "skill_triage_split"
SKILL_TRIAGE_MERGE = "skill_triage_merge"

# ── split_candidate 定数 ────────────────────────────

SPLIT_CANDIDATE_CONFIDENCE = 0.70

# ── tool_usage_rule_candidate detail フィールド ─────

RULE_FILENAME = "filename"
RULE_CONTENT = "content"
RULE_TARGET_COMMANDS = "target_commands"
RULE_ALTERNATIVE_TOOLS = "alternative_tools"
RULE_TOTAL_COUNT = "total_count"

# ── tool_usage_hook_candidate detail フィールド ─────

HOOK_SCRIPT_PATH = "script_path"
HOOK_SCRIPT_CONTENT = "script_content"
HOOK_SETTINGS_DIFF = "settings_diff"
HOOK_TARGET_COMMANDS = "target_commands"
HOOK_TOTAL_COUNT = "total_count"

# ── verification_rule_candidate detail フィールド ──

VRC_CATALOG_ID = "catalog_id"
VRC_RULE_FILENAME = "rule_filename"
VRC_RULE_TEMPLATE = "rule_template"
VRC_DESCRIPTION = "description"
VRC_EVIDENCE = "evidence"
VRC_DETECTION_CONFIDENCE = "detection_confidence"

# ── skill_evolve_candidate detail フィールド ────────

SE_SKILL_NAME = "skill_name"
SE_SKILL_DIR = "skill_dir"
SE_SUITABILITY = "suitability"
SE_TOTAL_SCORE = "total_score"
SE_SCORES = "scores"
SE_ANTI_PATTERNS = "anti_patterns"
SE_RECOMMENDATION = "recommendation"


# ── Factory 関数 ────────────────────────────────────


def make_rule_candidate_issue(
    rc: Dict[str, Any],
    *,
    rules_dir_str: str = "",
) -> Dict[str, Any]:
    """tool_usage_analyzer の rule_candidate 出力 → issue dict 変換。"""
    filename = rc.get(RULE_FILENAME, "")
    file_path = f"{rules_dir_str}/{filename}" if rules_dir_str else filename
    return {
        "type": TOOL_USAGE_RULE_CANDIDATE,
        "file": file_path,
        "detail": {
            RULE_FILENAME: filename,
            RULE_CONTENT: rc.get(RULE_CONTENT, ""),
            RULE_TARGET_COMMANDS: rc.get(RULE_TARGET_COMMANDS, []),
            RULE_ALTERNATIVE_TOOLS: rc.get(RULE_ALTERNATIVE_TOOLS, []),
            RULE_TOTAL_COUNT: rc.get(RULE_TOTAL_COUNT, 0),
        },
        "source": "discover_tool_usage",
    }


def make_hook_candidate_issue(
    hook_candidate: Dict[str, Any],
    total_count: int,
) -> Dict[str, Any]:
    """tool_usage_analyzer の hook_candidate 出力 → issue dict 変換。"""
    return {
        "type": TOOL_USAGE_HOOK_CANDIDATE,
        "file": hook_candidate.get(HOOK_SCRIPT_PATH, ""),
        "detail": {
            HOOK_SCRIPT_PATH: hook_candidate.get(HOOK_SCRIPT_PATH, ""),
            HOOK_SCRIPT_CONTENT: hook_candidate.get(HOOK_SCRIPT_CONTENT, ""),
            HOOK_SETTINGS_DIFF: hook_candidate.get(HOOK_SETTINGS_DIFF, ""),
            HOOK_TARGET_COMMANDS: hook_candidate.get(HOOK_TARGET_COMMANDS, []),
            HOOK_TOTAL_COUNT: total_count,
        },
        "source": "discover_tool_usage",
    }


def make_verification_rule_issue(
    entry: Dict[str, Any],
    detection_result: Dict[str, Any],
    *,
    project_dir_str: str = "",
) -> Dict[str, Any]:
    """verification_catalog のエントリ + 検出結果 → issue dict 変換。"""
    rule_filename = entry.get("rule_filename", "")
    file_path = f"{project_dir_str}/.claude/rules/{rule_filename}" if project_dir_str else rule_filename
    return {
        "type": VERIFICATION_RULE_CANDIDATE,
        "file": file_path,
        "detail": {
            VRC_CATALOG_ID: entry.get("id", ""),
            VRC_RULE_FILENAME: rule_filename,
            VRC_RULE_TEMPLATE: entry.get("rule_template", ""),
            VRC_DESCRIPTION: entry.get("description", ""),
            VRC_EVIDENCE: detection_result.get("evidence", []),
            VRC_DETECTION_CONFIDENCE: detection_result.get("confidence", 0.0),
        },
        "source": "verification_catalog",
    }


def make_split_candidate_issue(
    split_candidate: Dict[str, Any],
) -> Dict[str, Any]:
    """reorganize の split_candidate → issue dict 変換。"""
    skill_name = split_candidate.get("skill_name", "")
    return {
        "type": SPLIT_CANDIDATE,
        "file": f".claude/skills/{skill_name}/SKILL.md",
        "detail": {
            "skill_name": skill_name,
            "line_count": split_candidate.get("line_count", 0),
            "threshold": split_candidate.get("threshold", 300),
        },
        "source": "reorganize",
    }


# ── skill_triage detail フィールド ─────────────────

ST_ACTION = "action"
ST_SKILL = "skill"
ST_SKILLS = "skills"
ST_CONFIDENCE = "confidence"
ST_EVIDENCE = "evidence"
ST_SUGGESTION = "suggestion"
ST_EVAL_SET_PATH = "eval_set_path"


def make_skill_triage_issue(
    triage_result: Dict[str, Any],
) -> Dict[str, Any]:
    """skill_triage の判定結果 → issue dict 変換。

    CREATE/UPDATE/SPLIT/MERGE の各アクションに対応する issue type にマッピングする。
    """
    action = triage_result.get(ST_ACTION, "")
    action_to_type = {
        "CREATE": SKILL_TRIAGE_CREATE,
        "UPDATE": SKILL_TRIAGE_UPDATE,
        "SPLIT": SKILL_TRIAGE_SPLIT,
        "MERGE": SKILL_TRIAGE_MERGE,
    }
    issue_type = action_to_type.get(action, "")
    if not issue_type:
        return {}

    skill = triage_result.get(ST_SKILL, "") or ""
    skills = triage_result.get(ST_SKILLS, [])
    file_path = f".claude/skills/{skill}/SKILL.md" if skill else ""

    return {
        "type": issue_type,
        "file": file_path,
        "detail": {
            ST_ACTION: action,
            ST_SKILL: skill,
            ST_SKILLS: skills,
            ST_CONFIDENCE: triage_result.get(ST_CONFIDENCE, 0.0),
            ST_EVIDENCE: triage_result.get(ST_EVIDENCE, {}),
            ST_SUGGESTION: triage_result.get(ST_SUGGESTION, ""),
            ST_EVAL_SET_PATH: triage_result.get(ST_EVAL_SET_PATH, ""),
        },
        "source": "skill_triage",
    }


def make_skill_evolve_issue(
    assessment: Dict[str, Any],
    skill_md_path: str,
) -> Dict[str, Any]:
    """skill_evolve の assessment → issue dict 変換。"""
    return {
        "type": SKILL_EVOLVE_CANDIDATE,
        "file": skill_md_path,
        "detail": {
            SE_SKILL_NAME: assessment.get(SE_SKILL_NAME, ""),
            SE_SKILL_DIR: assessment.get(SE_SKILL_DIR, ""),
            SE_SUITABILITY: assessment.get(SE_SUITABILITY, "low"),
            SE_TOTAL_SCORE: assessment.get(SE_TOTAL_SCORE, 0),
            SE_SCORES: assessment.get(SE_SCORES, {}),
            SE_ANTI_PATTERNS: assessment.get(SE_ANTI_PATTERNS, []),
            SE_RECOMMENDATION: assessment.get(SE_RECOMMENDATION, ""),
        },
        "source": "skill_evolve_assessment",
    }
