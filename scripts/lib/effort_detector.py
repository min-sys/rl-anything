"""effort frontmatter 検出・推定モジュール。

スキルの SKILL.md に effort frontmatter が未設定の場合を検出し、
スキル特性に基づいて適切な effort レベル（low/medium/high）を推定する。

audit → evolve → remediation パイプラインで利用。
"""
import re
from pathlib import Path
from typing import Any, Dict, List

from frontmatter import count_content_lines, parse_frontmatter

# ── 閾値定数 ─────────────────────────────────────────────

LOW_LINE_THRESHOLD = 80
"""コンテンツ行数がこれ未満のスキルは low と推定。"""

HIGH_LINE_THRESHOLD = 300
"""コンテンツ行数がこれ以上のスキルは high と推定。"""

HIGH_KEYWORDS = re.compile(
    r"\b(orchestrat|pipeline|parallel|multi.?phase|multi.?step"
    r"|ThreadPoolExecutor|subagent|concurrent)\b",
    re.IGNORECASE,
)
"""本文にこれらのキーワードが含まれるスキルは high 候補。"""

HIGH_KEYWORD_MIN_MATCHES = 2
"""high キーワードの最低マッチ数。"""

BASE_CONFIDENCE = 0.75
"""推定の基本 confidence。"""

STRONG_SIGNAL_CONFIDENCE = 0.90
"""強いシグナル（disable-model-invocation, Agent in allowed-tools）の confidence。"""


def infer_effort_level(skill_path: Path) -> Dict[str, Any]:
    """スキルの特性から effort レベルを推定する。

    推定ロジック（優先順位順）:
    1. disable-model-invocation: true → low (STRONG_SIGNAL_CONFIDENCE)
    2. allowed-tools に Agent を含む → high (STRONG_SIGNAL_CONFIDENCE)
    3. コンテンツ行数 < LOW_LINE_THRESHOLD → low
    4. コンテンツ行数 >= HIGH_LINE_THRESHOLD → high
    5. パイプライン系キーワード >= HIGH_KEYWORD_MIN_MATCHES → high
    6. それ以外 → medium

    Returns:
        {"level": "low"|"medium"|"high", "confidence": float, "reason": str}
    """
    fm = parse_frontmatter(skill_path)

    # 1. disable-model-invocation: true → low
    if fm.get("disable-model-invocation") is True:
        return {
            "level": "low",
            "confidence": STRONG_SIGNAL_CONFIDENCE,
            "reason": "disable-model-invocation: true",
        }

    # 2. allowed-tools に Agent を含む → high
    allowed_tools = fm.get("allowed-tools", "")
    if isinstance(allowed_tools, str) and "Agent" in allowed_tools:
        return {
            "level": "high",
            "confidence": STRONG_SIGNAL_CONFIDENCE,
            "reason": "allowed-tools includes Agent",
        }

    # コンテンツ読み込み
    try:
        content = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"level": "medium", "confidence": 0.5, "reason": "read_error"}

    line_count = count_content_lines(content)

    # 3. 短いスキル → low
    if line_count < LOW_LINE_THRESHOLD:
        return {
            "level": "low",
            "confidence": BASE_CONFIDENCE,
            "reason": f"content_lines={line_count} < {LOW_LINE_THRESHOLD}",
        }

    # 4. 長いスキル → high
    if line_count >= HIGH_LINE_THRESHOLD:
        return {
            "level": "high",
            "confidence": BASE_CONFIDENCE,
            "reason": f"content_lines={line_count} >= {HIGH_LINE_THRESHOLD}",
        }

    # 5. パイプライン系キーワード → high
    keyword_matches = len(HIGH_KEYWORDS.findall(content))
    if keyword_matches >= HIGH_KEYWORD_MIN_MATCHES:
        return {
            "level": "high",
            "confidence": BASE_CONFIDENCE,
            "reason": f"pipeline_keywords={keyword_matches}",
        }

    # 6. デフォルト → medium
    return {
        "level": "medium",
        "confidence": BASE_CONFIDENCE,
        "reason": f"content_lines={line_count}, default",
    }


def detect_missing_effort_frontmatter(project_dir: Path) -> Dict[str, Any]:
    """プロジェクト内のスキルから effort 未設定のものを検出する。

    Args:
        project_dir: プロジェクトルート

    Returns:
        {
            "applicable": bool,
            "evidence": [{"skill_name": str, "skill_path": str,
                          "proposed_effort": str, "confidence": float}],
            "confidence": float,
        }
    """
    skills_dir = project_dir / ".claude" / "skills"
    if not skills_dir.is_dir():
        return {"applicable": False, "evidence": [], "confidence": 0.0}

    missing: List[Dict[str, Any]] = []
    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        fm = parse_frontmatter(skill_md)
        if fm.get("effort"):
            continue

        proposal = infer_effort_level(skill_md)
        missing.append({
            "skill_name": skill_md.parent.name,
            "skill_path": str(skill_md),
            "proposed_effort": proposal["level"],
            "confidence": proposal["confidence"],
            "reason": proposal["reason"],
        })

    if not missing:
        return {"applicable": False, "evidence": [], "confidence": 0.0}

    avg_confidence = sum(e["confidence"] for e in missing) / len(missing)
    return {
        "applicable": True,
        "evidence": missing,
        "confidence": avg_confidence,
    }
