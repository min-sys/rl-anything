#!/usr/bin/env python3
"""Remediation エンジン。

audit の検出結果を受け取り、confidence_score / impact_scope ベースで
auto_fixable / proposable / manual_required に動的分類し、
修正アクション生成・検証・テレメトリ記録を行う。
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 分類閾値
AUTO_FIX_CONFIDENCE = 0.9
PROPOSABLE_CONFIDENCE = 0.5
MAJOR_EXCESS_RATIO = 1.6  # 行数が制限値の160%以上 → manual_required

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


def compute_confidence_score(issue: Dict[str, Any]) -> float:
    """問題タイプと詳細から confidence_score を算出する。

    Returns:
        0.0 〜 1.0
    """
    issue_type = issue["type"]
    detail = issue.get("detail", {})

    if issue_type == "stale_ref":
        # 陳腐化参照は削除の確実性が高い
        return 0.95

    if issue_type == "line_limit_violation":
        lines = detail.get("lines", 0)
        limit = detail.get("limit", 1)
        ratio = lines / limit if limit > 0 else 999
        if ratio >= MAJOR_EXCESS_RATIO:
            # 大幅超過 → 自動修正困難
            return 0.3
        elif ratio <= 1.02:
            # 1〜2% 超過 → 空行除去等で対応可能
            return 0.95
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
        return 0.4  # 重複の統合は複雑

    return 0.5


# ---------- 分類 ----------

def classify_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    """単一の issue を分類し、メタデータを付与する。

    Returns:
        元の issue に confidence_score, impact_scope, category を追加した dict
    """
    confidence = compute_confidence_score(issue)
    scope = compute_impact_scope(issue["file"])

    # 動的分類
    if confidence >= AUTO_FIX_CONFIDENCE and scope == "file":
        category = "auto_fixable"
    elif confidence < PROPOSABLE_CONFIDENCE or scope == "global":
        category = "manual_required"
    else:
        category = "proposable"

    return {
        **issue,
        "confidence_score": confidence,
        "impact_scope": scope,
        "category": category,
    }


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
        else:
            proposal = f"{issue['type']} に対する修正案を検討してください。"

        proposals.append({
            "issue": issue,
            "proposal": proposal,
            "rationale": rationale,
        })

    return proposals


# ---------- 検証エンジン ----------

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

    if issue_type == "stale_ref":
        # 元のパス参照がまだ存在するかチェック
        import sys
        _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
        from audit import _extract_paths_outside_codeblocks

        content = path.read_text(encoding="utf-8")
        extracted = _extract_paths_outside_codeblocks(content)
        ref_path = detail.get("path", "")
        for _, found_path in extracted:
            if found_path == ref_path:
                return {"resolved": False, "remaining": f"参照「{ref_path}」がまだ存在します"}
        return {"resolved": True, "remaining": None}

    if issue_type == "line_limit_violation":
        content = path.read_text(encoding="utf-8")
        current_lines = content.count("\n") + 1
        limit = detail.get("limit", 0)
        if current_lines > limit:
            return {
                "resolved": False,
                "remaining": f"行数 {current_lines}/{limit} — まだ超過しています",
            }
        return {"resolved": True, "remaining": None}

    return {"resolved": True, "remaining": None}


def check_regression(fixed_file: str, original_content: str) -> Dict[str, Any]:
    """修正が副作用を起こしていないか検証する。

    検証項目:
    - 見出し構造の保持
    - Markdown フォーマットの整合性

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
) -> Optional[Dict[str, Any]]:
    """修正結果を remediation-outcomes.jsonl に記録する。

    dry_run=True の場合は記録しない。

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

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outcomes_file = DATA_DIR / "remediation-outcomes.jsonl"
    with open(outcomes_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record
