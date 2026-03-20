#!/usr/bin/env python3
"""Remediation エンジン。

audit の検出結果を受け取り、confidence_score / impact_scope ベースで
auto_fixable / proposable / manual_required に動的分類し、
修正アクション生成・検証・テレメトリ記録を行う。
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
from skill_origin import (  # noqa: E402
    is_protected_skill,
    suggest_local_alternative,
    generate_protection_warning,
)
from issue_schema import (  # noqa: E402
    TOOL_USAGE_RULE_CANDIDATE,
    TOOL_USAGE_HOOK_CANDIDATE,
    SKILL_EVOLVE_CANDIDATE,
    VERIFICATION_RULE_CANDIDATE,
    RULE_FILENAME,
    RULE_CONTENT,
    RULE_TARGET_COMMANDS,
    RULE_ALTERNATIVE_TOOLS,
    RULE_TOTAL_COUNT,
    HOOK_SCRIPT_PATH,
    HOOK_SCRIPT_CONTENT,
    HOOK_SETTINGS_DIFF,
    HOOK_TOTAL_COUNT,
    SE_SKILL_NAME,
    SE_SKILL_DIR,
    SE_SUITABILITY,
    SE_TOTAL_SCORE,
    SE_SCORES,
    VRC_CATALOG_ID,
    VRC_RULE_FILENAME,
    VRC_RULE_TEMPLATE,
    VRC_DESCRIPTION,
    VRC_EVIDENCE,
    VRC_DETECTION_CONFIDENCE,
    WORKFLOW_CHECKPOINT_CANDIDATE,
    WCC_SKILL_NAME,
    WCC_CATEGORY,
    WCC_EVIDENCE_COUNT,
    WCC_CONFIDENCE,
    WCC_TEMPLATE,
    WCC_DESCRIPTION,
    MISSING_EFFORT_CANDIDATE,
    MEC_SKILL_NAME,
    MEC_SKILL_PATH,
    MEC_PROPOSED_EFFORT,
    MEC_CONFIDENCE,
    MEC_REASON,
)

# 分類閾値
AUTO_FIX_CONFIDENCE = 0.9
PROPOSABLE_CONFIDENCE = 0.5
MAJOR_EXCESS_RATIO = 1.6  # 行数が制限値の160%以上 → manual_required
DUPLICATE_PROPOSABLE_SIMILARITY = 0.75  # duplicate の proposable 昇格閾値
DUPLICATE_PROPOSABLE_CONFIDENCE = 0.60  # similarity >= 閾値時の confidence

# impact_scope の判定に使うパス
_GLOBAL_SCOPE_PATTERNS = {"CLAUDE.md"}
_PROJECT_SCOPE_PATTERNS = {".claude/"}

DATA_DIR = Path.home() / ".claude" / "rl-anything"


# ---------- confidence_score / impact_scope 算出 ----------

def compute_impact_scope(file_path: str) -> str:
    """ファイルパスから impact_scope を判定する。

    Returns:
        "file", "project", or "global"
    """
    basename = Path(file_path).name
    if basename in _GLOBAL_SCOPE_PATTERNS:
        return "project"  # CLAUDE.md は全会話に影響するが project scope

    # CLAUDE.md 直下でないが .claude/ 内 → file scope
    # グローバル設定（~/.claude/ 直下の rules 等）→ global
    home_claude = str(Path.home() / ".claude")
    if file_path.startswith(home_claude) and "memory" not in file_path:
        # ~/.claude/rules/ や ~/.claude/skills/ → global
        return "global"

    return "file"


def _load_calibration_overrides() -> Dict[str, float]:
    """confidence-calibration.json から active なキャリブレーション値を読み込む。"""
    cal_file = DATA_DIR / "confidence-calibration.json"
    if not cal_file.exists():
        return {}
    try:
        data = json.loads(cal_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    overrides: Dict[str, float] = {}
    for it, cal in data.get("calibrations", {}).items():
        if isinstance(cal, dict) and cal.get("status") == "active":
            overrides[it] = cal.get("calibrated", cal.get("current", 0.5))
    return overrides


def compute_confidence_score(issue: Dict[str, Any]) -> float:
    """問題タイプと詳細から confidence_score を算出する。

    confidence-calibration.json に active なキャリブレーション値があればそちらを使用。

    Returns:
        0.0 〜 1.0
    """
    issue_type = issue["type"]
    detail = issue.get("detail", {})

    # Check calibration overrides first
    overrides = _load_calibration_overrides()
    if issue_type in overrides:
        return overrides[issue_type]

    if issue_type == "stale_ref":
        # 陳腐化参照は削除の確実性が高い
        return 0.95

    if issue_type == "line_limit_violation":
        lines = detail.get("lines", 0)
        limit = detail.get("limit", 1)
        excess = lines - limit if limit > 0 else lines
        ratio = lines / limit if limit > 0 else 999
        if ratio >= MAJOR_EXCESS_RATIO:
            # 大幅超過 → 自動修正困難
            return 0.3
        elif excess == 1:
            # 1行超過 → LLM 圧縮で対応可能
            return 0.95
        elif excess <= 2 and ratio <= 1.02:
            # 2行以内かつ2%以内 → 高めの信頼度だが auto_fixable にはしない
            return 0.7
        elif ratio <= 1.10:
            # 10% 以内の超過 → 高めの信頼度
            return 0.7
        else:
            return 0.5

    if issue_type == "near_limit":
        pct = detail.get("pct", 0)
        if pct >= 95:
            return 0.6
        return 0.7

    if issue_type == "duplicate":
        similarity = detail.get("similarity", 0.0)
        if similarity >= DUPLICATE_PROPOSABLE_SIMILARITY:
            return DUPLICATE_PROPOSABLE_CONFIDENCE
        return 0.4  # 低similarity重複の統合は複雑

    if issue_type == "hardcoded_value":
        # 検出結果自体の confidence_score を使用
        return detail.get("confidence_score", 0.5)

    # レイヤー別診断の新 issue type
    if issue_type == "orphan_rule":
        return 0.5  # 孤立判定は不確実性がある

    if issue_type == "stale_rule":
        return 0.95  # ファイル不存在は確実

    if issue_type == "stale_memory":
        return 0.6  # セマンティックパターン検出の不確実性

    if issue_type == "memory_duplicate":
        similarity = detail.get("similarity", 0.5)
        return min(0.8, max(0.6, similarity))  # 類似度に依存

    if issue_type == "hooks_unconfigured":
        return 0.4  # 意図的な場合もある

    if issue_type == "claudemd_phantom_ref":
        return 0.9  # スキル/ルールの実在確認は確実性が高い

    if issue_type == "claudemd_missing_section":
        return 0.95  # セクション有無は確実に判定可能

    if issue_type == TOOL_USAGE_RULE_CANDIDATE:
        return 0.85  # パターンマッチは確実だが global 影響

    if issue_type == TOOL_USAGE_HOOK_CANDIDATE:
        return 0.75  # hook テンプレートの汎用性にバリエーション

    if issue_type == "cap_exceeded":
        return 0.90  # Active 超過は明確に判定可能

    if issue_type == "line_guard":
        return 0.90  # 行数超過は明確に判定可能

    if issue_type == "split_candidate":
        return 0.70  # 分割判断にはドメイン知識が必要

    if issue_type == "preflight_scriptification":
        return 0.70  # スクリプト化候補は proposable

    if issue_type == "untagged_reference_candidates":
        return 0.90  # audit のフィルタ済み候補のため高信頼

    if issue_type == SKILL_EVOLVE_CANDIDATE:
        suitability = detail.get(SE_SUITABILITY, "low")
        if suitability == "high":
            return 0.85
        elif suitability == "medium":
            return 0.60
        return 0.3  # low → 対象外

    if issue_type == VERIFICATION_RULE_CANDIDATE:
        # 検出関数の confidence を使用（regex のみなので proposable 止まり）
        return min(0.85, detail.get(VRC_DETECTION_CONFIDENCE, 0.5))

    if issue_type == WORKFLOW_CHECKPOINT_CANDIDATE:
        # ギャップ検出の confidence をそのまま使用（上限 0.85 = proposable）
        return min(0.85, detail.get(WCC_CONFIDENCE, 0.5))

    return 0.5


# ---------- 分類 ----------

def classify_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    """単一の issue を分類し、メタデータを付与する。

    Returns:
        元の issue に confidence_score, impact_scope, category を追加した dict
    """
    confidence = compute_confidence_score(issue)
    scope = compute_impact_scope(issue["file"])

    # 保護スキルへの書込チェック: 保護対象は proposable に降格 + 警告
    file_path = Path(issue["file"])
    protection_warning = None
    if is_protected_skill(file_path):
        skill_name = file_path.parent.name if file_path.name != file_path.parent.name else file_path.stem
        # スキルディレクトリ名を推定
        parts = file_path.parts
        try:
            skills_idx = len(parts) - 1 - list(reversed(parts)).index("skills")
            if skills_idx + 1 < len(parts):
                skill_name = parts[skills_idx + 1]
        except ValueError:
            pass
        project_root = Path.cwd()
        alt_path, _ = suggest_local_alternative(skill_name, project_root)
        protection_warning = generate_protection_warning(skill_name, alt_path)

    # 動的分類
    if protection_warning:
        # 保護スキルへの修正は proposable に降格（ユーザー承認必須）
        category = "proposable"
    elif confidence >= AUTO_FIX_CONFIDENCE and scope in ("file", "project"):
        category = "auto_fixable"
    elif scope == "global" and confidence >= PROPOSABLE_CONFIDENCE:
        # global scope は auto_fixable にせず proposable に留める（ユーザー承認必須）
        category = "proposable"
    elif confidence < PROPOSABLE_CONFIDENCE:
        category = "manual_required"
    else:
        category = "proposable"

    result = {
        **issue,
        "confidence_score": confidence,
        "impact_scope": scope,
        "category": category,
    }
    if protection_warning:
        result["protection_warning"] = protection_warning
    return result


def classify_issues(issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """issue リストを3カテゴリに分類する。

    Returns:
        {"auto_fixable": [...], "proposable": [...], "manual_required": [...]}
    """
    result: Dict[str, List[Dict[str, Any]]] = {
        "auto_fixable": [],
        "proposable": [],
        "manual_required": [],
    }

    for issue in issues:
        classified = classify_issue(issue)
        result[classified["category"]].append(classified)

    return result


# ---------- rationale 生成 ----------

_RATIONALE_TEMPLATES = {
    "stale_ref": "ディスク上に存在しないパス参照「{path}」を削除します。",
    "line_limit_violation_auto": "行数が制限を {excess} 行超過しています。空行除去等で制限内に収めます。",
    "line_limit_violation_propose": "行数が制限値の {pct}% ({lines}/{limit}) です。reference ファイルへの切り出しを提案します。",
    "line_limit_violation_manual": "行数が制限値の {pct}% ({lines}/{limit}) と大幅に超過しています。手動でのリファクタリングが必要です。",
    "near_limit": "行数が制限の {pct}% ({lines}/{limit}) に達しています。トピック別ファイルへの分割を提案します。",
    "duplicate": "名前が類似するアーティファクト「{name}」が {count} 箇所にあります。統合を検討してください。",
    "hardcoded_value": "ハードコード値 `{matched}` ({pattern_type}) が検出されました。プレースホルダへの置換を検討してください。",
    "orphan_rule": "ルール「{name}」はどのスキル・CLAUDE.md からも参照されていません。",
    "stale_rule": "ルール内で参照されている「{path}」が存在しません。参照の更新または削除を検討してください。",
    "stale_memory": "MEMORY.md 内の「{path}」への言及は実体が見つかりません。エントリの更新または削除を検討してください。",
    "memory_duplicate": "MEMORY.md のセクション「{section_a}」と「{section_b}」は内容が重複しています（類似度: {similarity}）。統合を検討してください。",
    "hooks_unconfigured": "hooks 設定が見つかりません。observe hooks の設定を検討してください。",
    "claudemd_phantom_ref": "CLAUDE.md 内で言及された{ref_type}「{name}」が存在しません。",
    "claudemd_missing_section": "CLAUDE.md に {section} セクションがありませんが、{skill_count} 個のスキルが存在します。セクションの追加を検討してください。",
    TOOL_USAGE_RULE_CANDIDATE: "Bash で {commands} が計 {count} 回使用されています。{alternatives} ツールで代替可能です。global rule の追加を提案します。",
    TOOL_USAGE_HOOK_CANDIDATE: "Bash での Built-in 代替可能コマンド使用（{count} 回検出）を自動検出する PreToolUse hook の追加を提案します。",
    "untagged_reference_candidates": "スキル「{skill_name}」は呼び出し実績がなく reference type が未設定です。frontmatter に `type: reference` を追加します。",
    SKILL_EVOLVE_CANDIDATE: "スキル「{skill_name}」の自己進化適性: {suitability}（{total_score}/15点）。自己進化パターン（Pre-flight Check, pitfalls.md, Failure-triggered Learning）の組み込みを提案します。",
    VERIFICATION_RULE_CANDIDATE: "{description}が {evidence_count} 箇所検出されました（confidence: {confidence}）。ルールの追加を提案します。",
    "cap_exceeded": "Active pitfall が {active_count}/{cap} 件で上限を超過しています。Cold 層（Graduated/Candidate/New）から優先順にアーカイブします。",
    "line_guard": "pitfalls.md が {line_count}/{max_lines} 行で上限を超過しています。Cold 層から優先順にアーカイブします。",
    "split_candidate": "スキル「{skill_name}」({line_count}/{threshold}行) が分割閾値を超過しています。references/ への切り出しを提案します。",
    "preflight_scriptification": "pitfall「{pitfall_title}」(カテゴリ: {category}) のPre-flightスクリプト化を提案します。",
}


def generate_rationale(issue: Dict[str, Any], category: str) -> str:
    """修正アクションに対する修正理由テキストを生成する。"""
    issue_type = issue["type"]
    detail = issue.get("detail", {})

    if issue_type == "stale_ref":
        return _RATIONALE_TEMPLATES["stale_ref"].format(
            path=detail.get("path", "unknown"),
        )

    if issue_type == "line_limit_violation":
        lines = detail.get("lines", 0)
        limit = detail.get("limit", 1)
        pct = int(lines / limit * 100) if limit > 0 else 0
        excess = lines - limit

        if category == "auto_fixable":
            return _RATIONALE_TEMPLATES["line_limit_violation_auto"].format(excess=excess)
        elif category == "proposable":
            return _RATIONALE_TEMPLATES["line_limit_violation_propose"].format(
                pct=pct, lines=lines, limit=limit,
            )
        else:
            return _RATIONALE_TEMPLATES["line_limit_violation_manual"].format(
                pct=pct, lines=lines, limit=limit,
            )

    if issue_type == "near_limit":
        return _RATIONALE_TEMPLATES["near_limit"].format(
            pct=detail.get("pct", 0),
            lines=detail.get("lines", 0),
            limit=detail.get("limit", 0),
        )

    if issue_type == "duplicate":
        return _RATIONALE_TEMPLATES["duplicate"].format(
            name=detail.get("name", "unknown"),
            count=len(detail.get("paths", [])),
        )

    if issue_type == "hardcoded_value":
        return _RATIONALE_TEMPLATES["hardcoded_value"].format(
            matched=detail.get("matched", "unknown"),
            pattern_type=detail.get("pattern_type", "unknown"),
        )

    if issue_type == "orphan_rule":
        return _RATIONALE_TEMPLATES["orphan_rule"].format(
            name=detail.get("name", "unknown"),
        )

    if issue_type == "stale_rule":
        return _RATIONALE_TEMPLATES["stale_rule"].format(
            path=detail.get("path", "unknown"),
        )

    if issue_type == "stale_memory":
        return _RATIONALE_TEMPLATES["stale_memory"].format(
            path=detail.get("path", "unknown"),
        )

    if issue_type == "memory_duplicate":
        sections = detail.get("sections", ["unknown", "unknown"])
        return _RATIONALE_TEMPLATES["memory_duplicate"].format(
            section_a=sections[0] if len(sections) > 0 else "unknown",
            section_b=sections[1] if len(sections) > 1 else "unknown",
            similarity=detail.get("similarity", 0.0),
        )

    if issue_type == "hooks_unconfigured":
        return _RATIONALE_TEMPLATES["hooks_unconfigured"]

    if issue_type == "claudemd_phantom_ref":
        return _RATIONALE_TEMPLATES["claudemd_phantom_ref"].format(
            ref_type=detail.get("ref_type", "skill"),
            name=detail.get("name", "unknown"),
        )

    if issue_type == "claudemd_missing_section":
        return _RATIONALE_TEMPLATES["claudemd_missing_section"].format(
            section=detail.get("section", "skills"),
            skill_count=detail.get("skill_count", 0),
        )

    if issue_type == TOOL_USAGE_RULE_CANDIDATE:
        return _RATIONALE_TEMPLATES[TOOL_USAGE_RULE_CANDIDATE].format(
            commands=", ".join(detail.get(RULE_TARGET_COMMANDS, ["unknown"])),
            count=detail.get(RULE_TOTAL_COUNT, 0),
            alternatives=", ".join(detail.get(RULE_ALTERNATIVE_TOOLS, ["unknown"])),
        )

    if issue_type == TOOL_USAGE_HOOK_CANDIDATE:
        return _RATIONALE_TEMPLATES[TOOL_USAGE_HOOK_CANDIDATE].format(
            count=detail.get(HOOK_TOTAL_COUNT, 0),
        )

    if issue_type == "untagged_reference_candidates":
        return _RATIONALE_TEMPLATES["untagged_reference_candidates"].format(
            skill_name=detail.get("skill_name", "unknown"),
        )

    if issue_type == SKILL_EVOLVE_CANDIDATE:
        return _RATIONALE_TEMPLATES[SKILL_EVOLVE_CANDIDATE].format(
            skill_name=detail.get(SE_SKILL_NAME, "unknown"),
            suitability=detail.get(SE_SUITABILITY, "unknown"),
            total_score=detail.get(SE_TOTAL_SCORE, 0),
        )

    if issue_type == VERIFICATION_RULE_CANDIDATE:
        return _RATIONALE_TEMPLATES[VERIFICATION_RULE_CANDIDATE].format(
            evidence_count=len(detail.get(VRC_EVIDENCE, [])),
            confidence=detail.get(VRC_DETECTION_CONFIDENCE, 0.0),
            description=detail.get(VRC_DESCRIPTION, "unknown"),
        )

    if issue_type == "cap_exceeded":
        return _RATIONALE_TEMPLATES["cap_exceeded"].format(
            active_count=detail.get("active_count", 0),
            cap=detail.get("cap", 10),
        )

    if issue_type == "line_guard":
        return _RATIONALE_TEMPLATES["line_guard"].format(
            line_count=detail.get("line_count", 0),
            max_lines=detail.get("max_lines", 500),
        )

    if issue_type == "split_candidate":
        return _RATIONALE_TEMPLATES["split_candidate"].format(
            skill_name=detail.get("skill_name", "unknown"),
            line_count=detail.get("line_count", 0),
            threshold=detail.get("threshold", 300),
        )

    if issue_type == "preflight_scriptification":
        return _RATIONALE_TEMPLATES["preflight_scriptification"].format(
            pitfall_title=detail.get("pitfall_title", "unknown"),
            category=detail.get("category", "unknown"),
        )

    return f"問題タイプ「{issue_type}」が検出されました。"


# ---------- 修正アクション ----------

def fix_stale_references(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """陳腐化参照の行を削除する。修正前の内容を保持する（ロールバック用）。

    Returns:
        [{"issue": ..., "original_content": str, "fixed": bool, "error": str|None}, ...]
    """
    # ファイル別にグルーピング
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        if issue["type"] != "stale_ref":
            continue
        f = issue["file"]
        if f not in by_file:
            by_file[f] = []
        by_file[f].append(issue)

    results = []
    for file_path, file_issues in by_file.items():
        path = Path(file_path)
        try:
            original_content = path.read_text(encoding="utf-8")
        except OSError as e:
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": "",
                    "fixed": False,
                    "error": str(e),
                })
            continue

        lines = original_content.splitlines(keepends=True)
        # 削除対象行（1-indexed → 0-indexed）
        lines_to_remove = set()
        for issue in file_issues:
            line_num = issue.get("detail", {}).get("line", 0)
            if 0 < line_num <= len(lines):
                lines_to_remove.add(line_num - 1)

        new_lines = [l for i, l in enumerate(lines) if i not in lines_to_remove]
        new_content = "".join(new_lines)

        try:
            path.write_text(new_content, encoding="utf-8")
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": original_content,
                    "fixed": True,
                    "error": None,
                })
        except OSError as e:
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": original_content,
                    "fixed": False,
                    "error": str(e),
                })

    return results


def fix_stale_rules(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """ルール内の不存在パス参照行を削除する。

    Returns:
        [{"issue": ..., "original_content": str, "fixed": bool, "error": str|None}, ...]
    """
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        if issue["type"] != "stale_rule":
            continue
        f = issue["file"]
        if f not in by_file:
            by_file[f] = []
        by_file[f].append(issue)

    results = []
    for file_path, file_issues in by_file.items():
        path = Path(file_path)
        try:
            original_content = path.read_text(encoding="utf-8")
        except OSError as e:
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": "",
                    "fixed": False,
                    "error": str(e),
                })
            continue

        lines = original_content.splitlines(keepends=True)
        lines_to_remove = set()
        for issue in file_issues:
            line_num = issue.get("detail", {}).get("line", 0)
            if 0 < line_num <= len(lines):
                lines_to_remove.add(line_num - 1)

        new_lines = [l for i, l in enumerate(lines) if i not in lines_to_remove]
        new_content = "".join(new_lines)

        try:
            path.write_text(new_content, encoding="utf-8")
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": original_content,
                    "fixed": True,
                    "error": None,
                })
        except OSError as e:
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": original_content,
                    "fixed": False,
                    "error": str(e),
                })

    return results


def fix_claudemd_phantom_refs(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """CLAUDE.md 内の phantom_ref 行を削除し、連続空行を正規化する。

    Returns:
        [{"issue": ..., "original_content": str, "fixed": bool, "error": str|None}, ...]
    """
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        if issue["type"] != "claudemd_phantom_ref":
            continue
        f = issue["file"]
        if f not in by_file:
            by_file[f] = []
        by_file[f].append(issue)

    results = []
    for file_path, file_issues in by_file.items():
        path = Path(file_path)
        try:
            original_content = path.read_text(encoding="utf-8")
        except OSError as e:
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": "",
                    "fixed": False,
                    "error": str(e),
                })
            continue

        lines = original_content.splitlines(keepends=True)
        lines_to_remove = set()
        for issue in file_issues:
            line_num = issue.get("detail", {}).get("line", 0)
            if 0 < line_num <= len(lines):
                lines_to_remove.add(line_num - 1)

        new_lines = [l for i, l in enumerate(lines) if i not in lines_to_remove]
        new_content = "".join(new_lines)
        # 連続空行の正規化（3行以上の空行 → 2行に）
        new_content = re.sub(r"\n{3,}", "\n\n", new_content)

        try:
            path.write_text(new_content, encoding="utf-8")
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": original_content,
                    "fixed": True,
                    "error": None,
                })
        except OSError as e:
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": original_content,
                    "fixed": False,
                    "error": str(e),
                })

    return results


def fix_claudemd_missing_section(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """CLAUDE.md に Skills セクションヘッダを追加する。

    Returns:
        [{"issue": ..., "original_content": str, "fixed": bool, "error": str|None}, ...]
    """
    results = []
    seen_files: set = set()
    for issue in issues:
        if issue["type"] != "claudemd_missing_section":
            continue
        file_path = issue["file"]
        if file_path in seen_files:
            continue
        seen_files.add(file_path)

        path = Path(file_path)
        try:
            original_content = path.read_text(encoding="utf-8")
        except OSError as e:
            results.append({
                "issue": issue,
                "original_content": "",
                "fixed": False,
                "error": str(e),
            })
            continue

        section_header = "\n\n## Skills\n\n<!-- スキル一覧をここに追加 -->\n"
        new_content = original_content.rstrip() + section_header

        try:
            path.write_text(new_content, encoding="utf-8")
            results.append({
                "issue": issue,
                "original_content": original_content,
                "fixed": True,
                "error": None,
            })
        except OSError as e:
            results.append({
                "issue": issue,
                "original_content": original_content,
                "fixed": False,
                "error": str(e),
            })

    return results


# ---------- FIX_DISPATCH ----------

def fix_global_rule(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """global rule ファイルを書き込む。

    issue["detail"] に {"filename": str, "content": str} が含まれる前提。
    """
    results = []
    for issue in issues:
        if issue["type"] != TOOL_USAGE_RULE_CANDIDATE:
            continue
        detail = issue.get("detail", {})
        filename = detail.get(RULE_FILENAME, "")
        content = detail.get(RULE_CONTENT, "")
        if not filename or not content:
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": "filename or content missing",
            })
            continue

        rules_dir = Path.home() / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        path = rules_dir / filename

        try:
            original = path.read_text(encoding="utf-8") if path.exists() else ""
        except OSError:
            original = ""

        try:
            path.write_text(content, encoding="utf-8")
            results.append({
                "issue": issue, "original_content": original, "fixed": True,
                "error": None,
            })
        except OSError as e:
            results.append({
                "issue": issue, "original_content": original, "fixed": False,
                "error": str(e),
            })
    return results


def fix_hook_scaffold(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """hook スクリプトを生成する。settings.json は書き換えない。

    issue["detail"] に {"script_path": str, "script_content": str, "settings_diff": str} が含まれる前提。
    """
    results = []
    for issue in issues:
        if issue["type"] != TOOL_USAGE_HOOK_CANDIDATE:
            continue
        detail = issue.get("detail", {})
        script_path = detail.get(HOOK_SCRIPT_PATH, "")
        script_content = detail.get(HOOK_SCRIPT_CONTENT, "")
        if not script_path or not script_content:
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": "script_path or script_content missing",
            })
            continue

        path = Path(script_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            original = path.read_text(encoding="utf-8") if path.exists() else ""
        except OSError:
            original = ""

        try:
            path.write_text(script_content, encoding="utf-8")
            path.chmod(0o755)
            results.append({
                "issue": issue, "original_content": original, "fixed": True,
                "error": None,
                "settings_diff": detail.get(HOOK_SETTINGS_DIFF, ""),
            })
        except OSError as e:
            results.append({
                "issue": issue, "original_content": original, "fixed": False,
                "error": str(e),
            })
    return results


def fix_untagged_reference(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """untagged_reference_candidates の frontmatter に type: reference を追加する。

    Returns:
        [{"issue": ..., "original_content": str, "fixed": bool, "error": str|None}, ...]
    """
    import sys
    _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
    from frontmatter import update_frontmatter

    results = []
    for issue in issues:
        if issue["type"] != "untagged_reference_candidates":
            continue

        file_path = issue["file"]
        path = Path(file_path)

        try:
            original_content = path.read_text(encoding="utf-8")
        except OSError as e:
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": str(e),
            })
            continue

        success, error = update_frontmatter(path, {"type": "reference"})
        results.append({
            "issue": issue,
            "original_content": original_content,
            "fixed": success,
            "error": error if error else None,
        })

    return results


def _is_rule_file(file_path: str) -> bool:
    """rule ファイルかどうかを判定する。"""
    return ".claude/rules/" in file_path


def _fix_rule_by_separation(
    issue: Dict[str, Any],
    path: Path,
    original_content: str,
    limit: int,
) -> Dict[str, Any]:
    """rule ファイルの行数超過を references への分離で修正する。"""
    import subprocess
    import sys

    _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
    from line_limit import suggest_separation

    proposal = suggest_separation(str(path), original_content)
    if not proposal:
        return {
            "issue": issue, "original_content": original_content,
            "fixed": False, "error": "separation_not_applicable",
        }

    prompt = (
        f"以下の rule ファイルの内容を {limit} 行以内の要約+参照リンクに書き換えてください。\n"
        f"詳細は別ファイルに分離されるので、rule には核心の1行ルールと参照リンクのみ残してください。\n"
        f"参照リンク: `{proposal.reference_path}`\n"
        f"出力は書き換え後の rule 内容のみ（説明不要）。\n\n"
        f"```\n{original_content}```"
    )

    try:
        result_proc = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True, text=True, timeout=60,
        )
        if result_proc.returncode != 0:
            issue["category"] = "proposable"
            return {
                "issue": issue, "original_content": original_content,
                "fixed": False, "error": f"llm_error: exit code {result_proc.returncode}",
            }

        summary = result_proc.stdout.strip()
        if summary.startswith("```") and summary.endswith("```"):
            lines = summary.split("\n")
            summary = "\n".join(lines[1:-1])

        summary_lines = summary.count("\n") + (1 if summary and not summary.endswith("\n") else 0)
        if summary_lines > limit:
            issue["category"] = "proposable"
            return {
                "issue": issue, "original_content": original_content,
                "fixed": False, "error": "separation_summary_too_long",
            }

        if not summary.endswith("\n"):
            summary += "\n"

        # 分離先ディレクトリ作成 + 詳細内容書き出し
        ref_path = Path(proposal.reference_path)
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_text(original_content, encoding="utf-8")

        # rule を要約+参照リンクに書き換え
        path.write_text(summary, encoding="utf-8")

        return {
            "issue": issue, "original_content": original_content,
            "fixed": True, "error": None,
            "separation": {
                "reference_path": str(ref_path),
                "summary": summary,
            },
        }

    except subprocess.TimeoutExpired:
        issue["category"] = "proposable"
        return {
            "issue": issue, "original_content": original_content,
            "fixed": False, "error": "llm_timeout",
        }
    except OSError as e:
        issue["category"] = "proposable"
        return {
            "issue": issue, "original_content": original_content,
            "fixed": False, "error": str(e),
        }


def fix_line_limit_violation(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """行数制限違反を修正する。

    rule ファイル: references への分離（要約+参照リンク書き換え + 詳細ファイル生成）。
    その他: LLM 1パス圧縮。

    auto_fixable な line_limit_violation のみ対象。
    LLM 失敗時は proposable に降格しエラーを記録する。

    Returns:
        [{"issue": ..., "original_content": str, "fixed": bool, "error": str|None}, ...]
    """
    import subprocess

    results = []
    for issue in issues:
        if issue["type"] != "line_limit_violation":
            continue

        file_path = issue["file"]
        detail = issue.get("detail", {})
        limit = detail.get("limit", 3)
        path = Path(file_path)

        try:
            original_content = path.read_text(encoding="utf-8")
        except OSError as e:
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": str(e),
            })
            continue

        # rule ファイルは分離モードで修正
        if _is_rule_file(file_path):
            results.append(_fix_rule_by_separation(issue, path, original_content, limit))
            continue

        prompt = (
            f"以下のファイル内容を {limit} 行以内に圧縮してください。"
            f"意味と構造を保ちつつ、冗長な表現を削除して簡潔にしてください。"
            f"出力は圧縮後のファイル内容のみ（説明不要）。\n\n"
            f"```\n{original_content}```"
        )

        try:
            result_proc = subprocess.run(
                ["claude", "--print", "-p", prompt],
                capture_output=True, text=True, timeout=60,
            )
            if result_proc.returncode != 0:
                issue["category"] = "proposable"
                results.append({
                    "issue": issue, "original_content": original_content,
                    "fixed": False, "error": f"llm_error: exit code {result_proc.returncode}",
                })
                continue

            compressed = result_proc.stdout.strip()
            # コードブロック除去
            if compressed.startswith("```") and compressed.endswith("```"):
                lines = compressed.split("\n")
                compressed = "\n".join(lines[1:-1])

            compressed_lines = compressed.count("\n") + (1 if compressed and not compressed.endswith("\n") else 0)
            if compressed_lines > limit:
                issue["category"] = "proposable"
                results.append({
                    "issue": issue, "original_content": original_content,
                    "fixed": False, "error": "compression_insufficient",
                })
                continue

            # 末尾改行を保証
            if not compressed.endswith("\n"):
                compressed += "\n"
            path.write_text(compressed, encoding="utf-8")
            results.append({
                "issue": issue, "original_content": original_content,
                "fixed": True, "error": None,
            })

        except subprocess.TimeoutExpired:
            issue["category"] = "proposable"
            results.append({
                "issue": issue, "original_content": original_content,
                "fixed": False, "error": "llm_timeout",
            })
        except OSError as e:
            issue["category"] = "proposable"
            results.append({
                "issue": issue, "original_content": original_content,
                "fixed": False, "error": str(e),
            })

    return results


def fix_skill_evolve(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """スキルに自己進化パターンを適用する。

    Returns:
        [{"issue": ..., "original_content": str, "fixed": bool, "error": str|None}, ...]
    """
    import sys
    _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
    from skill_evolve import evolve_skill_proposal, apply_evolve_proposal

    results = []
    for issue in issues:
        if issue["type"] != SKILL_EVOLVE_CANDIDATE:
            continue
        detail = issue.get("detail", {})
        skill_name = detail.get(SE_SKILL_NAME, "")
        skill_dir = Path(detail.get(SE_SKILL_DIR, ""))

        if not skill_dir.exists():
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": f"skill_dir not found: {skill_dir}",
            })
            continue

        proposal = evolve_skill_proposal(skill_name, skill_dir)
        if proposal.get("error"):
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": proposal["error"],
            })
            continue

        # 変更前の内容を記録（remediation の original_content 互換）
        skill_md = Path(proposal["skill_md_path"])
        try:
            original_content = skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""
        except OSError:
            original_content = ""

        apply_result = apply_evolve_proposal(proposal)
        results.append({
            "issue": issue, "original_content": original_content,
            "fixed": apply_result["applied"], "error": apply_result["error"],
        })

    return results


def fix_verification_rule(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """検証知見ルールをプロジェクトに作成する。"""
    results = []
    for issue in issues:
        if issue["type"] != VERIFICATION_RULE_CANDIDATE:
            continue
        detail = issue.get("detail", {})
        rule_filename = detail.get(VRC_RULE_FILENAME, "")
        rule_template = detail.get(VRC_RULE_TEMPLATE, "")
        if not rule_filename or not rule_template:
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": "missing rule_filename or rule_template",
            })
            continue

        # issue["file"] からプロジェクトの rules ディレクトリを特定
        file_path = Path(issue["file"])
        rules_dir = file_path.parent
        rules_dir.mkdir(parents=True, exist_ok=True)

        try:
            original_content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        except OSError:
            original_content = ""

        try:
            content = rule_template
            if not content.endswith("\n"):
                content += "\n"
            file_path.write_text(content, encoding="utf-8")
            results.append({
                "issue": issue, "original_content": original_content,
                "fixed": True, "error": None,
            })
        except OSError as e:
            results.append({
                "issue": issue, "original_content": original_content,
                "fixed": False, "error": str(e),
            })

    return results


def fix_stale_memory(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """MEMORY.md からstaleエントリのポインタ行を削除する。

    detail.path に一致する行を MEMORY.md から削除。
    参照先の個別メモリファイルが存在しない場合のみ対象。

    Returns:
        [{"issue": ..., "original_content": str, "fixed": bool, "error": str|None}, ...]
    """
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        if issue["type"] != "stale_memory":
            continue
        f = issue["file"]
        if f not in by_file:
            by_file[f] = []
        by_file[f].append(issue)

    results = []
    for file_path, file_issues in by_file.items():
        path = Path(file_path)
        try:
            original_content = path.read_text(encoding="utf-8")
        except OSError as e:
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": "",
                    "fixed": False,
                    "error": str(e),
                })
            continue

        lines = original_content.splitlines(keepends=True)
        lines_to_remove = set()
        for issue in file_issues:
            ref_path = issue.get("detail", {}).get("path", "")
            if not ref_path:
                continue
            for i, line in enumerate(lines):
                if ref_path in line:
                    lines_to_remove.add(i)

        new_lines = [l for i, l in enumerate(lines) if i not in lines_to_remove]
        new_content = "".join(new_lines)
        # 連続空行の正規化
        new_content = re.sub(r"\n{3,}", "\n\n", new_content)

        try:
            path.write_text(new_content, encoding="utf-8")
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": original_content,
                    "fixed": True,
                    "error": None,
                })
        except OSError as e:
            for issue in file_issues:
                results.append({
                    "issue": issue,
                    "original_content": original_content,
                    "fixed": False,
                    "error": str(e),
                })

    return results


def fix_pitfall_archive(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """pitfall Cold層（Graduated/Candidate/New）を pitfalls-archive.md にアーカイブする。

    cap_exceeded: Active超過分をCold層から優先順にアーカイブ
    line_guard: 行数が閾値以下になるまでCold層からアーカイブ

    Returns:
        [{"issue": ..., "original_content": str, "fixed": bool, "error": str|None}, ...]
    """
    from pitfall_manager import (
        parse_pitfalls,
        render_pitfalls,
        ACTIVE_PITFALL_CAP,
        PITFALL_MAX_LINES,
    )

    results = []
    for issue in issues:
        if issue["type"] not in ("cap_exceeded", "line_guard"):
            continue

        detail = issue.get("detail", {})
        pitfalls_path = Path(issue["file"])

        if not pitfalls_path.exists():
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": "pitfalls.md not found",
            })
            continue

        try:
            original_content = pitfalls_path.read_text(encoding="utf-8")
        except OSError as e:
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": str(e),
            })
            continue

        sections = parse_pitfalls(original_content)

        # Cold層をアーカイブ優先順に収集: Graduated > Candidate > New
        cold_items: List[Dict[str, Any]] = []
        for item in sections.get("graduated", []):
            cold_items.append({"item": item, "section": "graduated", "priority": 0})
        for item in sections.get("candidate", []):
            cold_items.append({"item": item, "section": "candidate", "priority": 1})
        for item in sections.get("active", []):
            if item["fields"].get("Status") == "New":
                cold_items.append({"item": item, "section": "active", "priority": 2})
        cold_items.sort(key=lambda x: x["priority"])

        if not cold_items:
            results.append({
                "issue": issue, "original_content": original_content, "fixed": False,
                "remaining": "Cold層にアーカイブ対象がありません。Active pitfallの手動レビューが必要です",
                "error": None,
            })
            continue

        # アーカイブ対象を選択
        to_archive: List[Dict[str, Any]] = []
        if issue["type"] == "cap_exceeded":
            active_count = detail.get("active_count", 0)
            cap = detail.get("cap", ACTIVE_PITFALL_CAP)
            need = active_count - cap
            for ci in cold_items:
                if len(to_archive) >= need:
                    break
                to_archive.append(ci)
        else:  # line_guard
            current_lines = len(original_content.splitlines())
            target = PITFALL_MAX_LINES
            removed_lines = 0
            for ci in cold_items:
                if current_lines - removed_lines <= target:
                    break
                raw_lines = len(ci["item"].get("raw", "").splitlines())
                to_archive.append(ci)
                removed_lines += raw_lines

        if not to_archive:
            results.append({
                "issue": issue, "original_content": original_content, "fixed": False,
                "error": None, "remaining": "アーカイブ対象が不足しています",
            })
            continue

        # archive ファイルに追記
        archive_path = pitfalls_path.parent / "pitfalls-archive.md"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        archive_entries = []
        for ci in to_archive:
            archive_entries.append(
                f"\n{ci['item']['raw']}\n- **Archived-date**: {now}\n"
            )

        archive_content = ""
        if archive_path.exists():
            archive_content = archive_path.read_text(encoding="utf-8")
        if not archive_content.strip():
            archive_content = "# Pitfalls Archive\n"
        archive_content += "\n".join(archive_entries)
        archive_path.write_text(archive_content, encoding="utf-8")

        # pitfalls.md から削除
        titles = [ci["item"]["title"] for ci in to_archive]
        for ci in to_archive:
            section_key = ci["section"]
            sections[section_key] = [
                item for item in sections[section_key]
                if item["title"] != ci["item"]["title"]
            ]

        pitfalls_path.write_text(render_pitfalls(sections), encoding="utf-8")

        results.append({
            "issue": issue, "original_content": original_content,
            "fixed": True, "error": None,
            "archived_titles": titles,
        })

    return results


def fix_split_candidate(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """スキル分割案をLLMで生成して提案テキストを表示する（ファイル変更なし）。

    Returns:
        [{"issue": ..., "original_content": "", "fixed": True, "error": None, "proposal_text": str}, ...]
    """
    import subprocess

    results = []
    for issue in issues:
        if issue["type"] != "split_candidate":
            continue
        detail = issue.get("detail", {})
        skill_name = detail.get("skill_name", "unknown")
        file_path = issue["file"]
        path = Path(file_path)

        if not path.exists():
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": f"SKILL.md not found: {file_path}",
            })
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            results.append({
                "issue": issue, "original_content": "", "fixed": False,
                "error": str(e),
            })
            continue

        line_count = detail.get("line_count", len(content.splitlines()))
        threshold = detail.get("threshold", 300)

        prompt = (
            f"以下のスキル SKILL.md ({line_count}行、閾値{threshold}行) を分析し、"
            f"references/ に切り出すべきセクションを特定してください。\n"
            f"出力形式:\n"
            f"- 分割先ファイル名と各ファイルの概要\n"
            f"- 推定削減行数\n"
            f"- SKILL.md に残す内容の概要\n\n"
            f"```\n{content[:3000]}```"
        )

        try:
            result_proc = subprocess.run(
                ["claude", "--print", "-p", prompt],
                capture_output=True, text=True, timeout=60,
            )
            if result_proc.returncode != 0:
                proposal_text = (
                    f"スキル「{skill_name}」({line_count}行) の分割を検討してください。"
                    f"references/ にセクションを切り出し、SKILL.md を {threshold}行以下に削減することを推奨します。"
                )
            else:
                proposal_text = result_proc.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            proposal_text = (
                f"スキル「{skill_name}」({line_count}行) の分割を検討してください。"
                f"references/ にセクションを切り出し、SKILL.md を {threshold}行以下に削減することを推奨します。"
            )

        results.append({
            "issue": issue, "original_content": "", "fixed": True,
            "error": None, "proposal_text": proposal_text,
        })

    return results


def fix_preflight_scriptification(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Pre-flightスクリプト化提案をテンプレート付きで表示する（ファイル変更なし）。

    Returns:
        [{"issue": ..., "original_content": "", "fixed": True, "error": None, "proposal_text": str}, ...]
    """
    results = []
    for issue in issues:
        if issue["type"] != "preflight_scriptification":
            continue
        detail = issue.get("detail", {})
        pitfall_title = detail.get("pitfall_title", "unknown")
        category = detail.get("category", "generic")
        template_path = detail.get("template_path", "")

        template_content = ""
        if template_path:
            tp = Path(template_path)
            if tp.exists():
                try:
                    template_content = tp.read_text(encoding="utf-8")
                except OSError:
                    pass

        proposal_text = (
            f"pitfall「{pitfall_title}」のPre-flightスクリプト化を提案します。\n"
            f"カテゴリ: {category}\n"
        )
        if template_content:
            proposal_text += f"テンプレート ({Path(template_path).name}):\n```bash\n{template_content}```\n"

        results.append({
            "issue": issue, "original_content": "", "fixed": True,
            "error": None, "proposal_text": proposal_text,
        })

    return results


def fix_workflow_checkpoint(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """ワークフロースキルにチェックポイントステップを追記する proposable 提案。

    実際の SKILL.md 編集は行わず、提案テキストを返す（人間承認必須）。
    """
    results = []
    for issue in issues:
        detail = issue.get("detail", {})
        skill_name = detail.get(WCC_SKILL_NAME, "")
        category = detail.get(WCC_CATEGORY, "")
        template = detail.get(WCC_TEMPLATE, "")

        proposal_text = (
            f"スキル「{skill_name}」にチェックポイント「{category}」の追加を提案します。\n\n"
            f"追加ステップ:\n{template}\n"
        )

        results.append({
            "issue": issue,
            "original_content": "",
            "fixed": True,
            "error": None,
            "proposal_text": proposal_text,
        })

    return results


def fix_missing_effort(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """effort frontmatter が未設定のスキルに追加提案を行う。

    update_frontmatter() で effort フィールドを書き込む。
    """
    from frontmatter import update_frontmatter

    results = []
    for issue in issues:
        if issue["type"] != MISSING_EFFORT_CANDIDATE:
            continue
        detail = issue.get("detail", {})
        skill_path = Path(detail.get(MEC_SKILL_PATH, ""))
        proposed = detail.get(MEC_PROPOSED_EFFORT, "medium")
        reason = detail.get(MEC_REASON, "")

        if not skill_path.is_file():
            results.append({
                "issue": issue,
                "fixed": False,
                "error": f"file not found: {skill_path}",
            })
            continue

        success, err = update_frontmatter(skill_path, {"effort": proposed})
        results.append({
            "issue": issue,
            "fixed": success,
            "error": err if not success else None,
            "changed_files": [str(skill_path)] if success else [],
            "proposal_text": (
                f"effort: {proposed} を {detail.get(MEC_SKILL_NAME, '')} に追加"
                f" (reason: {reason})"
            ),
        })

    return results


def _verify_missing_effort(result: Dict[str, Any]) -> Tuple[bool, str]:
    """effort frontmatter が正しく追加されたか検証する。"""
    from frontmatter import parse_frontmatter

    changed = result.get("changed_files", [])
    if not changed:
        return False, "no changed files"
    path = Path(changed[0])
    if not path.is_file():
        return False, f"file not found: {path}"
    fm = parse_frontmatter(path)
    if fm.get("effort"):
        return True, ""
    return False, "effort not found in frontmatter after fix"


FIX_DISPATCH: Dict[str, Any] = {
    "stale_ref": fix_stale_references,
    "stale_memory": fix_stale_memory,
    "cap_exceeded": fix_pitfall_archive,
    "line_guard": fix_pitfall_archive,
    "split_candidate": fix_split_candidate,
    "preflight_scriptification": fix_preflight_scriptification,
    "stale_rule": fix_stale_rules,
    "line_limit_violation": fix_line_limit_violation,
    "untagged_reference_candidates": fix_untagged_reference,
    "claudemd_phantom_ref": fix_claudemd_phantom_refs,
    "claudemd_missing_section": fix_claudemd_missing_section,
    TOOL_USAGE_RULE_CANDIDATE: fix_global_rule,
    TOOL_USAGE_HOOK_CANDIDATE: fix_hook_scaffold,
    SKILL_EVOLVE_CANDIDATE: fix_skill_evolve,
    VERIFICATION_RULE_CANDIDATE: fix_verification_rule,
    WORKFLOW_CHECKPOINT_CANDIDATE: fix_workflow_checkpoint,
    MISSING_EFFORT_CANDIDATE: fix_missing_effort,
}


def generate_proposals(
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """行数制限違反や肥大化警告に対する修正案を rationale 付きで生成する。

    Returns:
        [{"issue": ..., "proposal": str, "rationale": str}, ...]
    """
    proposals = []
    for issue in issues:
        category = issue.get("category", "proposable")
        rationale = generate_rationale(issue, category)

        if issue["type"] == "line_limit_violation":
            detail = issue.get("detail", {})
            lines = detail.get("lines", 0)
            limit = detail.get("limit", 1)
            proposal = (
                f"ファイル {issue['file']} ({lines}/{limit} 行) を分析し、"
                f"最も行数の多いセクションを references/ に切り出す提案です。"
            )
        elif issue["type"] == "near_limit":
            detail = issue.get("detail", {})
            proposal = (
                f"ファイル {issue['file']} ({detail.get('pct', 0)}%) を"
                f"トピック別ファイルに分割する提案です。"
            )
        elif issue["type"] == "orphan_rule":
            detail = issue.get("detail", {})
            name = detail.get("name", Path(issue["file"]).stem)
            proposal = f"ルール「{name}」の削除"
        elif issue["type"] == "stale_memory":
            detail = issue.get("detail", {})
            path = detail.get("path", "unknown")
            proposal = f"MEMORY.md の「{path}」エントリの更新/削除"
        elif issue["type"] == "memory_duplicate":
            detail = issue.get("detail", {})
            sections = detail.get("sections", ["unknown", "unknown"])
            a = sections[0] if len(sections) > 0 else "unknown"
            b = sections[1] if len(sections) > 1 else "unknown"
            proposal = f"セクション「{a}」と「{b}」の統合"
        elif issue["type"] == TOOL_USAGE_RULE_CANDIDATE:
            detail = issue.get("detail", {})
            cmds = ", ".join(detail.get(RULE_TARGET_COMMANDS, []))
            proposal = f"~/.claude/rules/{detail.get(RULE_FILENAME, 'avoid-bash-builtin.md')} に Bash {cmds} 禁止ルールを作成"
        elif issue["type"] == TOOL_USAGE_HOOK_CANDIDATE:
            detail = issue.get("detail", {})
            proposal = f"{detail.get(HOOK_SCRIPT_PATH, '~/.claude/hooks/check-bash-builtin.py')} に PreToolUse hook を生成"
        elif issue["type"] == "untagged_reference_candidates":
            detail = issue.get("detail", {})
            skill_name = detail.get("skill_name", "unknown")
            proposal = f"スキル「{skill_name}」の frontmatter に `type: reference` を追加"
        elif issue["type"] == SKILL_EVOLVE_CANDIDATE:
            detail = issue.get("detail", {})
            skill_name = detail.get(SE_SKILL_NAME, "unknown")
            score = detail.get(SE_TOTAL_SCORE, 0)
            proposal = f"スキル「{skill_name}」({score}/15点) に自己進化パターンを組み込み"
        elif issue["type"] == VERIFICATION_RULE_CANDIDATE:
            detail = issue.get("detail", {})
            filename = detail.get(VRC_RULE_FILENAME, "unknown")
            proposal = f".claude/rules/{filename} に検証ルール「{detail.get(VRC_DESCRIPTION, '')}」を作成"
        elif issue["type"] == "cap_exceeded":
            detail = issue.get("detail", {})
            proposal = f"Active pitfall ({detail.get('active_count', 0)}件) の超過分をCold層からアーカイブ"
        elif issue["type"] == "line_guard":
            detail = issue.get("detail", {})
            proposal = f"pitfalls.md ({detail.get('line_count', 0)}行) のCold層をアーカイブして閾値以下に削減"
        elif issue["type"] == "split_candidate":
            detail = issue.get("detail", {})
            skill_name = detail.get("skill_name", "unknown")
            proposal = f"スキル「{skill_name}」({detail.get('line_count', 0)}行) の references/ 分割提案"
        elif issue["type"] == "preflight_scriptification":
            detail = issue.get("detail", {})
            proposal = f"pitfall「{detail.get('pitfall_title', 'unknown')}」のPre-flightスクリプト化提案"
        elif issue["type"] == "duplicate":
            detail = issue.get("detail", {})
            proposal = f"アーティファクト「{detail.get('name', 'unknown')}」の統合提案"
        else:
            proposal = f"{issue['type']} に対する修正案を検討してください。"

        entry = {
            "issue": issue,
            "proposal": proposal,
            "rationale": rationale,
        }

        # rule_candidate 系 issue に paths_suggestion を付加
        if issue["type"] in (TOOL_USAGE_RULE_CANDIDATE, VERIFICATION_RULE_CANDIDATE):
            detail = issue.get("detail", {})
            # detail に evidence テキストがあればパスパターンを検出
            evidence = detail.get(VRC_EVIDENCE, "") or detail.get("evidence", "")
            if evidence:
                try:
                    from reflect_utils import suggest_paths_frontmatter
                    ps = suggest_paths_frontmatter(evidence, Path.cwd())
                    if ps is not None:
                        entry["paths_suggestion"] = {
                            "patterns": ps.patterns,
                            "confidence": ps.confidence,
                        }
                except ImportError:
                    pass

        proposals.append(entry)

    return proposals


# ---------- 検証エンジン ----------

def _verify_stale_ref(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """stale_ref の検証。"""
    import sys
    _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
    from audit import _extract_paths_outside_codeblocks

    content = Path(fixed_file).read_text(encoding="utf-8")
    extracted = _extract_paths_outside_codeblocks(content)
    ref_path = detail.get("path", "")
    for _, found_path in extracted:
        if found_path == ref_path:
            return {"resolved": False, "remaining": f"参照「{ref_path}」がまだ存在します"}
    return {"resolved": True, "remaining": None}


def _verify_line_limit_violation(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """line_limit_violation の検証。分離モードの場合は分離先ファイルの存在も確認する。"""
    content = Path(fixed_file).read_text(encoding="utf-8")
    current_lines = content.count("\n") + 1
    limit = detail.get("limit", 0)
    if current_lines > limit:
        return {
            "resolved": False,
            "remaining": f"行数 {current_lines}/{limit} — まだ超過しています",
        }
    # 分離先ファイルの存在確認（rule ファイルの場合）
    if _is_rule_file(fixed_file):
        import sys
        _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
        from line_limit import _resolve_reference_path
        ref_path = _resolve_reference_path(Path(fixed_file))
        if not ref_path.exists():
            return {
                "resolved": False,
                "remaining": f"分離先ファイル {ref_path} が存在しません",
            }
    return {"resolved": True, "remaining": None}


def _verify_stale_rule(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """stale_rule の検証: 参照パスが消えているか。"""
    content = Path(fixed_file).read_text(encoding="utf-8")
    ref_path = detail.get("path", "")
    if ref_path and ref_path in content:
        return {"resolved": False, "remaining": f"参照「{ref_path}」がまだ存在します"}
    return {"resolved": True, "remaining": None}


def _verify_claudemd_phantom_ref(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """claudemd_phantom_ref の検証: 当該スキル/ルール名が消えているか。"""
    content = Path(fixed_file).read_text(encoding="utf-8")
    name = detail.get("name", "")
    if not name:
        return {"resolved": True, "remaining": None}
    # リスト項目内での言及をチェック
    for line in content.splitlines():
        if name in line and line.strip().startswith("-"):
            return {"resolved": False, "remaining": f"「{name}」のリスト項目がまだ存在します"}
    return {"resolved": True, "remaining": None}


def _verify_claudemd_missing_section(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """claudemd_missing_section の検証: Skills セクションが存在するか。"""
    content = Path(fixed_file).read_text(encoding="utf-8")
    if re.search(r"^##\s+Skills", content, re.MULTILINE):
        return {"resolved": True, "remaining": None}
    return {"resolved": False, "remaining": "Skills セクションが追加されていません"}


def _verify_stale_memory(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """stale_memory の検証: 当該モジュール参照が消えているか。"""
    content = Path(fixed_file).read_text(encoding="utf-8")
    path = detail.get("path", "")
    if path and path in content:
        return {"resolved": False, "remaining": f"「{path}」への参照がまだ存在します"}
    return {"resolved": True, "remaining": None}


# ---------- VERIFY_DISPATCH ----------

def _verify_global_rule(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """global rule ファイルの存在確認 + 行数検証。"""
    path = Path(fixed_file)
    if not path.exists():
        return {"resolved": False, "remaining": "rule ファイルが存在しません"}
    content = path.read_text(encoding="utf-8")
    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    if lines > 3:
        return {"resolved": False, "remaining": f"rule が3行制限を超過しています ({lines}行)"}
    return {"resolved": True, "remaining": None}


def _verify_hook_scaffold(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """hook スクリプトの存在確認。"""
    script_path = detail.get(HOOK_SCRIPT_PATH, fixed_file)
    path = Path(script_path)
    if not path.exists():
        return {"resolved": False, "remaining": "hook スクリプトが存在しません"}
    return {"resolved": True, "remaining": None}


def _verify_untagged_reference(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """untagged_reference_candidates の検証: type: reference が frontmatter に存在するか。"""
    import sys
    _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
    from frontmatter import parse_frontmatter

    fm = parse_frontmatter(Path(fixed_file))
    if fm.get("type") == "reference":
        return {"resolved": True, "remaining": None}
    return {"resolved": False, "remaining": "frontmatter に type: reference が存在しません"}


def _verify_skill_evolve(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """skill_evolve_candidate の検証。"""
    skill_dir = Path(detail.get("skill_dir", Path(fixed_file).parent))

    # 1. references/pitfalls.md が存在するか
    pitfalls = skill_dir / "references" / "pitfalls.md"
    if not pitfalls.exists():
        return {"resolved": False, "remaining": "references/pitfalls.md が存在しません"}

    # 2. SKILL.md に自己更新セクションが存在するか
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {"resolved": False, "remaining": "SKILL.md が存在しません"}

    content = skill_md.read_text(encoding="utf-8")
    missing = []
    if not re.search(r"(?i)failure[- ]triggered\s+learning", content):
        missing.append("Failure-triggered Learning")
    if not re.search(r"(?i)pre[- ]flight", content):
        missing.append("Pre-flight Check")
    if missing:
        return {"resolved": False, "remaining": f"セクション欠落: {', '.join(missing)}"}

    return {"resolved": True, "remaining": None}


def _verify_verification_rule(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """verification_rule_candidate の検証: ルールファイルが存在するか。"""
    path = Path(fixed_file)
    if not path.exists():
        return {"resolved": False, "remaining": "ルールファイルが存在しません"}
    content = path.read_text(encoding="utf-8")
    if len(content.strip()) == 0:
        return {"resolved": False, "remaining": "ルールファイルが空です"}
    return {"resolved": True, "remaining": None}


def _verify_pitfall_archive(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """pitfall archive の検証: Active件数/行数が閾値以下か + archive先の存在確認。"""
    from pitfall_manager import parse_pitfalls, ACTIVE_PITFALL_CAP, PITFALL_MAX_LINES

    path = Path(fixed_file)
    if not path.exists():
        return {"resolved": False, "remaining": "pitfalls.md が存在しません"}

    content = path.read_text(encoding="utf-8")
    sections = parse_pitfalls(content)

    # archive ファイルの存在確認
    archive_path = path.parent / "pitfalls-archive.md"
    if not archive_path.exists():
        return {"resolved": False, "remaining": "pitfalls-archive.md が存在しません"}

    # cap_exceeded の場合: Active件数チェック
    active_count = sum(
        1 for item in sections.get("active", [])
        if item["fields"].get("Status") == "Active"
    )
    cap = detail.get("cap", ACTIVE_PITFALL_CAP)
    if active_count > cap:
        return {"resolved": False, "remaining": f"Active pitfall ({active_count}) がまだ cap ({cap}) を超過しています"}

    # line_guard の場合: 行数チェック
    line_count = len(content.splitlines())
    if line_count > PITFALL_MAX_LINES:
        return {"resolved": False, "remaining": f"行数 ({line_count}) がまだ閾値 ({PITFALL_MAX_LINES}) を超過しています"}

    return {"resolved": True, "remaining": None}


def _verify_split_candidate(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """split_candidate の検証: 提案テキストが生成されたことを確認（常にresolved=true）。"""
    return {"resolved": True, "remaining": None}


def _verify_preflight_scriptification(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """preflight_scriptification の検証: 提案テキストが生成されたことを確認（常にresolved=true）。"""
    return {"resolved": True, "remaining": None}


def _verify_workflow_checkpoint(fixed_file: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """workflow_checkpoint の検証: proposable 提案が生成されたことを確認（常にresolved=true）。"""
    return {"resolved": True, "remaining": None}


VERIFY_DISPATCH: Dict[str, Any] = {
    "stale_ref": _verify_stale_ref,
    "line_limit_violation": _verify_line_limit_violation,
    "stale_rule": _verify_stale_rule,
    "claudemd_phantom_ref": _verify_claudemd_phantom_ref,
    "claudemd_missing_section": _verify_claudemd_missing_section,
    "stale_memory": _verify_stale_memory,
    "untagged_reference_candidates": _verify_untagged_reference,
    "cap_exceeded": _verify_pitfall_archive,
    "line_guard": _verify_pitfall_archive,
    "split_candidate": _verify_split_candidate,
    "preflight_scriptification": _verify_preflight_scriptification,
    TOOL_USAGE_RULE_CANDIDATE: _verify_global_rule,
    TOOL_USAGE_HOOK_CANDIDATE: _verify_hook_scaffold,
    SKILL_EVOLVE_CANDIDATE: _verify_skill_evolve,
    VERIFICATION_RULE_CANDIDATE: _verify_verification_rule,
    WORKFLOW_CHECKPOINT_CANDIDATE: _verify_workflow_checkpoint,
    MISSING_EFFORT_CANDIDATE: _verify_missing_effort,
}


def verify_fix(fixed_file: str, original_issue: Dict[str, Any]) -> Dict[str, Any]:
    """修正されたファイルに対して該当する検出関数を再実行し、元の問題の解消を確認する。

    Returns:
        {"resolved": bool, "remaining": str|None}
    """
    path = Path(fixed_file)
    if not path.exists():
        return {"resolved": False, "remaining": "ファイルが存在しません"}

    issue_type = original_issue["type"]
    detail = original_issue.get("detail", {})

    verify_fn = VERIFY_DISPATCH.get(issue_type)
    if verify_fn is not None:
        return verify_fn(fixed_file, detail)

    # 未登録 type はスキップ（warning）
    import sys
    print(f"  [warn] verify_fix: 未登録の issue type「{issue_type}」をスキップ", file=sys.stderr)
    return {"resolved": True, "remaining": None}


def check_regression(fixed_file: str, original_content: str) -> Dict[str, Any]:
    """修正が副作用を起こしていないか検証する。

    検証項目:
    - 見出し構造の保持
    - Markdown フォーマットの整合性
    - Rules ファイルの行数制限

    Returns:
        {"passed": bool, "issues": [str, ...]}
    """
    path = Path(fixed_file)
    if not path.exists():
        return {"passed": False, "issues": ["ファイルが存在しません"]}

    new_content = path.read_text(encoding="utf-8")
    issues = []

    # 見出し構造チェック
    original_headings = re.findall(r"^(#{1,6}\s+.+)$", original_content, re.MULTILINE)
    new_headings = re.findall(r"^(#{1,6}\s+.+)$", new_content, re.MULTILINE)
    if original_headings != new_headings:
        # 削除された行に見出しが含まれていないか確認
        removed_headings = set(original_headings) - set(new_headings)
        if removed_headings:
            issues.append(f"見出しが削除されました: {', '.join(removed_headings)}")

    # コードブロックの対応チェック
    original_fences = original_content.count("```")
    new_fences = new_content.count("```")
    if new_fences % 2 != 0:
        issues.append("コードブロックの開始/終了が不対応です")

    # 空ファイルチェック
    if not new_content.strip():
        issues.append("ファイルが空になりました")

    # Rules ファイルの行数制限チェック
    if ".claude/rules/" in fixed_file:
        import sys
        _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
        from line_limit import MAX_RULE_LINES

        line_count = new_content.count("\n") + (1 if new_content and not new_content.endswith("\n") else 0)
        if line_count > MAX_RULE_LINES:
            issues.append(
                f"Rules ファイルが行数制限を超過しています ({line_count}行)"
            )

    return {
        "passed": len(issues) == 0,
        "issues": issues,
    }


def rollback_fix(fixed_file: str, original_content: str) -> bool:
    """修正前の内容に復元する。

    Returns:
        True if rollback succeeded
    """
    try:
        Path(fixed_file).write_text(original_content, encoding="utf-8")
        return True
    except OSError:
        return False


# ---------- テレメトリ ----------

def record_outcome(
    issue: Dict[str, Any],
    category: str,
    action: str,
    result: str,
    user_decision: str,
    rationale: str,
    *,
    dry_run: bool = False,
    fix_detail: Optional[Dict[str, Any]] = None,
    verify_result: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """修正結果を remediation-outcomes.jsonl に記録する。

    dry_run=True の場合は記録しない。

    Args:
        fix_detail: 修正の詳細。以下のキーを含む dict:
            - changed_files (List[str]): 変更されたファイルパスのリスト（MUST）
            - lines_removed (int): 削除行数
            - lines_added (int): 追加行数
        verify_result: 検証結果 (resolved, remaining)
        duration_ms: 修正にかかった時間（ミリ秒）

    Returns:
        記録したレコード、または dry_run 時は None
    """
    if dry_run:
        return None

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "issue_type": issue.get("type", "unknown"),
        "category": category,
        "confidence_score": issue.get("confidence_score", 0.0),
        "impact_scope": issue.get("impact_scope", "unknown"),
        "action": action,
        "result": result,
        "user_decision": user_decision,
        "rationale": rationale,
        "file": issue.get("file", ""),
    }

    if fix_detail is not None:
        record["fix_detail"] = fix_detail
    if verify_result is not None:
        record["verify_result"] = verify_result
    if duration_ms is not None:
        record["duration_ms"] = duration_ms

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outcomes_file = DATA_DIR / "remediation-outcomes.jsonl"
    with open(outcomes_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record
