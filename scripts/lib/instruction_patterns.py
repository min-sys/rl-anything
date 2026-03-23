#!/usr/bin/env python3
"""Instruction Pattern Detector — スキル内の7パターンを自動検出。

detect_patterns() で7パターンを検出し、スコアを算出する。
check_defaults_first() で選択肢×推奨マーカーのヒューリスティクススコアを返す。
analyze_context_efficiency() で普遍的知識・signal/noise・CLAUDE.md重複を検出する。
"""
import re
from typing import Any, Dict, List, Optional, Set

try:
    from similarity import jaccard_coefficient, tokenize
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from similarity import jaccard_coefficient, tokenize

# ── 定数 ──────────────────────────────────────────────

CONTEXT_EFFICIENCY_MIN_LINES = 50
DEFAULTS_FIRST_LLM_THRESHOLD = 0.5

UNIVERSAL_KNOWLEDGE_PATTERNS: List[re.Pattern] = [
    re.compile(r"git\s+(commit|push|pull|clone|checkout)\b"),
    re.compile(r"HTTP\s+(GET|POST|PUT|DELETE|status\s+code)"),
    re.compile(r"REST\s*API\s*(is|are|means)"),
    re.compile(r"JSON\s+(is|format|stands\s+for)"),
    re.compile(r"pip\s+install\b.*#.*install"),
    re.compile(r"npm\s+(install|run)\b.*#.*install"),
    re.compile(r"docker\s+(run|build|pull)\b.*#.*basic"),
    re.compile(r"(what|how)\s+.*\b(variable|function|class)\b.*\bis\b"),
]

# ── Gotchas セクション ────────────────────────────────
_GOTCHAS_RE = re.compile(r"^#+\s*(Gotchas|Pitfalls|注意点)\s*$", re.MULTILINE)

# ── Output Template: コードブロック ────────────────────
_CODEBLOCK_RE = re.compile(r"```\w*\n[\s\S]*?```")

# ── Checklist: 番号付き手順 ───────────────────────────
_NUMBERED_STEP_RE = re.compile(r"^\d+\.\s+", re.MULTILINE)

# ── Validation Loop ───────────────────────────────────
_VALIDATE_RE = re.compile(r"(?:\b(?:validate|check|verify)\b|(?:validate|check|verify))", re.IGNORECASE)
_FIX_RE = re.compile(r"(?:\b(?:fix)\b|修正)", re.IGNORECASE)

# ── Plan-Validate-Execute ─────────────────────────────
_PLAN_RE = re.compile(r"(?:\b(?:plan)\b|確認)", re.IGNORECASE)
_EXECUTE_RE = re.compile(r"(?:\b(?:execute)\b|実行)", re.IGNORECASE)

# ── Progressive Disclosure ────────────────────────────
_REFERENCES_RE = re.compile(r"\breferences/\S+")
_READ_IF_RE = re.compile(r"\bRead\b.*\bif\b", re.IGNORECASE)

# ── Defaults-First: 選択肢パターン ────────────────────
_CHOICE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bor\b", re.IGNORECASE),
    re.compile(r"\beither\b", re.IGNORECASE),
    re.compile(r"\bchoose\b", re.IGNORECASE),
    re.compile(r"\boption\s+[A-Z]\b", re.IGNORECASE),
    re.compile(r"方法\d"),
    re.compile(r"^[A-Z]\)\s+", re.MULTILINE),
]

# ── Defaults-First: 推奨マーカー ──────────────────────
_RECOMMENDATION_PATTERNS: List[re.Pattern] = [
    re.compile(r"推奨"),
    re.compile(r"デフォルト"),
    re.compile(r"通常は"),
    re.compile(r"\brecommended\b", re.IGNORECASE),
    re.compile(r"\bdefault\b", re.IGNORECASE),
    re.compile(r"\bprefer\b", re.IGNORECASE),
]

# ── Signal 検出（インラインコード / ファイルパス） ─────
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_FILE_PATH_RE = re.compile(r"[./][a-zA-Z0-9_/-]+\.[a-z]{2,4}")

_TOTAL_PATTERNS = 7


# ── Public API ────────────────────────────────────────


def detect_patterns(skill_content: str) -> Dict[str, Any]:
    """7パターンを検出し、スコアを算出する。

    Returns:
        {
            "used_patterns": [str, ...],
            "pattern_details": {pattern_name: bool/float},
            "score": float,
        }
    """
    details: Dict[str, Any] = {}

    # 1. Gotchas
    details["gotchas"] = bool(_GOTCHAS_RE.search(skill_content))

    # 2. Output Template
    details["output_template"] = bool(_CODEBLOCK_RE.search(skill_content))

    # 3. Checklist (3+ numbered steps)
    numbered = _NUMBERED_STEP_RE.findall(skill_content)
    details["checklist"] = len(numbered) >= 3

    # 4. Validation Loop (validate/check/verify AND fix/修正)
    has_validate = bool(_VALIDATE_RE.search(skill_content))
    has_fix = bool(_FIX_RE.search(skill_content))
    details["validation_loop"] = has_validate and has_fix

    # 5. Plan-Validate-Execute (plan/確認 AND execute/実行)
    has_plan = bool(_PLAN_RE.search(skill_content))
    has_execute = bool(_EXECUTE_RE.search(skill_content))
    details["plan_validate_execute"] = has_plan and has_execute

    # 6. Progressive Disclosure
    has_refs = bool(_REFERENCES_RE.search(skill_content))
    has_read_if = bool(_READ_IF_RE.search(skill_content))
    details["progressive_disclosure"] = has_refs or has_read_if

    # 7. Defaults-First
    details["defaults_first"] = check_defaults_first(skill_content)

    # Compute used_patterns
    used: List[str] = []
    has_content = bool(skill_content.strip())
    for name, value in details.items():
        if isinstance(value, bool) and value:
            used.append(name)
        elif isinstance(value, float) and value > 0.5 and has_content:
            used.append(name)

    # Score = detected / 7
    detected_count = len(used)
    score = detected_count / _TOTAL_PATTERNS

    return {
        "used_patterns": used,
        "pattern_details": details,
        "score": score,
    }


def check_defaults_first(skill_content: str) -> float:
    """選択肢×推奨マーカーのヒューリスティクススコアを返す。

    - 選択肢なし → 1.0（メニューなし = 良い）
    - 選択肢あり + 推奨マーカーあり → 0.5-1.0（比率ベース）
    - 選択肢あり + 推奨マーカーなし → 0.0-0.3
    """
    choice_count = 0
    for pat in _CHOICE_PATTERNS:
        choice_count += len(pat.findall(skill_content))

    if choice_count == 0:
        return 1.0

    rec_count = 0
    for pat in _RECOMMENDATION_PATTERNS:
        rec_count += len(pat.findall(skill_content))

    if rec_count == 0:
        # 選択肢あり、推奨なし → 0.0-0.3
        # 選択肢が多いほど低い
        return max(0.0, 0.3 - (choice_count - 1) * 0.05)

    # 選択肢あり + 推奨あり → 0.5-1.0
    ratio = min(rec_count / choice_count, 1.0)
    return 0.5 + ratio * 0.5


def analyze_context_efficiency(
    skill_content: str,
    claude_md_content: Optional[str] = None,
) -> Dict[str, Any]:
    """普遍的知識・signal/noise・CLAUDE.md 重複を検出する。

    Returns:
        {
            "universal_knowledge_matches": int,
            "signal_noise_ratio": float,
            "claude_md_overlap": float | None,
            "efficiency_score": float,
        }
    """
    lines = [l for l in skill_content.splitlines() if l.strip()]
    total_lines = len(lines) if lines else 1

    # 1. Universal knowledge matches
    uk_matches = 0
    for line in lines:
        for pat in UNIVERSAL_KNOWLEDGE_PATTERNS:
            if pat.search(line):
                uk_matches += 1
                break  # one match per line

    # 2. Signal-to-noise ratio
    signal_count = 0
    for line in lines:
        if _INLINE_CODE_RE.search(line) or _FILE_PATH_RE.search(line):
            signal_count += 1
    snr = signal_count / total_lines if total_lines > 0 else 0.0

    # 3. CLAUDE.md overlap (Jaccard)
    claude_md_overlap: Optional[float] = None
    if claude_md_content is not None and len(lines) >= CONTEXT_EFFICIENCY_MIN_LINES:
        skill_tokens: Set[str] = tokenize(skill_content)
        claude_tokens: Set[str] = tokenize(claude_md_content)
        claude_md_overlap = jaccard_coefficient(skill_tokens, claude_tokens)

    # 4. Efficiency score
    # Base: 1.0 - (universal_matches / total_lines * 0.5)
    uk_penalty = uk_matches / total_lines * 0.5 if total_lines > 0 else 0.0
    base_score = max(0.0, 1.0 - uk_penalty)
    # SNR correction: penalize low signal ratio, but don't penalize no-UK content
    snr_adjustment = (snr - 0.5) * 0.2  # range: -0.1 to +0.1
    efficiency_score = base_score + snr_adjustment
    # Clamp
    efficiency_score = max(0.0, min(1.0, efficiency_score))

    return {
        "universal_knowledge_matches": uk_matches,
        "signal_noise_ratio": snr,
        "claude_md_overlap": claude_md_overlap,
        "efficiency_score": efficiency_score,
    }
