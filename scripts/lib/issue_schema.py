"""Issue スキーマ定数 — モジュール間のデータ受け渡し契約。

tool_usage_analyzer / skill_evolve（生成）→ evolve（変換）→ remediation（消費）
の3層で共有するフィールド名を定数化し、文字列リテラルの不一致を防止する。
"""
from typing import Any, Dict, List

# ── Issue Type 定数 ─────────────────────────────────

TOOL_USAGE_RULE_CANDIDATE = "tool_usage_rule_candidate"
TOOL_USAGE_HOOK_CANDIDATE = "tool_usage_hook_candidate"
SKILL_EVOLVE_CANDIDATE = "skill_evolve_candidate"

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
