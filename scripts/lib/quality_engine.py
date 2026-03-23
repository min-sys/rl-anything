"""Skill Quality Engine — パターン認識ベースの品質エンジン。

ExecutionTraceAnalyzer（混乱度測定）、PatternRecommender（ドメイン別推奨）、
スコアボード記録を提供する。
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import telemetry_query
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import telemetry_query

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

MIN_SESSION_SAMPLES = 5
CONFUSION_TOOL_RATIO_THRESHOLD = 2.5
CONFUSION_READ_EDIT_CYCLE_MIN = 3

OVERALL_WEIGHTS = {
    "pattern_score": 0.35,
    "inverse_confusion": 0.25,
    "context_efficiency": 0.20,
    "defaults_first": 0.20,
}

# ドメイン推定キーワード
DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "deploy": ["deploy", "ship", "release", "push"],
    "investigation": ["debug", "investigate", "diagnose", "fix"],
    "generation": ["generate", "create", "build", "scaffold"],
    "workflow": ["workflow", "pipeline", "flow", "step"],
    "reference": ["reference", "guide", "doc", "lookup"],
}

# ドメイン別パターン推奨
DOMAIN_PATTERN_MAP: Dict[str, Dict[str, List[str]]] = {
    "deploy": {
        "required": ["plan_validate_execute", "checklist"],
        "recommended": ["gotchas"],
    },
    "investigation": {
        "required": ["validation_loop"],
        "recommended": ["progressive_disclosure"],
    },
    "generation": {
        "required": ["output_template"],
        "recommended": ["validation_loop"],
    },
    "workflow": {
        "required": ["checklist"],
        "recommended": ["gotchas", "defaults_first"],
    },
    "reference": {
        "required": ["progressive_disclosure"],
        "recommended": [],
    },
    "default": {
        "required": [],
        "recommended": ["gotchas", "defaults_first"],
    },
}


# ---------------------------------------------------------------------------
# analyze_traces — ExecutionTraceAnalyzer
# ---------------------------------------------------------------------------

def analyze_traces(
    skill_name: str,
    *,
    project: Optional[str] = None,
    usage_file: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """セッショントレースからスキルの混乱度を測定する。

    Args:
        skill_name: 対象スキル名。
        project: プロジェクトフィルタ。
        usage_file: usage.jsonl のパス（テスト用）。

    Returns:
        混乱度スコアと各コンポーネント。MIN_SESSION_SAMPLES 未満なら None。
    """
    kwargs: Dict[str, Any] = {"project": project}
    if usage_file is not None:
        kwargs["usage_file"] = usage_file

    sessions = telemetry_query.query_usage_by_skill_session(skill_name, **kwargs)

    if len(sessions) < MIN_SESSION_SAMPLES:
        return None

    # tool_ratio_score: 平均ツール呼び出し数 / 閾値（v1: 絶対値判定）
    avg_tool_calls = sum(s["tool_calls"] for s in sessions) / len(sessions)
    tool_ratio = avg_tool_calls / CONFUSION_TOOL_RATIO_THRESHOLD
    tool_ratio_score = min(1.0, max(0.0, tool_ratio / CONFUSION_TOOL_RATIO_THRESHOLD))

    # read_edit_score: CONFUSION_READ_EDIT_CYCLE_MIN 以上のセッション比率
    high_re_sessions = sum(
        1 for s in sessions
        if s["read_edit_cycles"] >= CONFUSION_READ_EDIT_CYCLE_MIN
    )
    read_edit_score = high_re_sessions / len(sessions)

    # error_score: エラーありセッション比率
    error_sessions = sum(1 for s in sessions if s["errors"] > 0)
    error_score = error_sessions / len(sessions)

    # confusion_score: 3 コンポーネントの平均
    confusion_score = min(1.0, max(0.0,
        (tool_ratio_score + read_edit_score + error_score) / 3.0
    ))

    return {
        "confusion_score": confusion_score,
        "tool_ratio_score": tool_ratio_score,
        "read_edit_score": read_edit_score,
        "error_score": error_score,
        "sample_count": len(sessions),
    }


# ---------------------------------------------------------------------------
# recommend_patterns — PatternRecommender
# ---------------------------------------------------------------------------

def _detect_domain(content: str) -> str:
    """スキル内容からドメインを推定する（キーワードベース）。"""
    content_lower = content.lower()
    best_domain = "default"
    best_count = 0

    for domain, keywords in DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", content_lower))
        if count > best_count:
            best_count = count
            best_domain = domain

    return best_domain


def recommend_patterns(
    detected_patterns: Dict[str, Any],
    skill_content: str,
) -> Dict[str, Any]:
    """スキルのドメインに基づいて不足パターンを推奨する。

    Args:
        detected_patterns: 検出済みパターン情報（used_patterns キー）。
        skill_content: スキルのテキスト内容。

    Returns:
        {"domain": str, "required_missing": [str], "recommended_missing": [str]}
    """
    domain = _detect_domain(skill_content)
    patterns = DOMAIN_PATTERN_MAP.get(domain, DOMAIN_PATTERN_MAP["default"])

    used = set(detected_patterns.get("used_patterns", []))

    required_missing = [p for p in patterns["required"] if p not in used]
    recommended_missing = [p for p in patterns["recommended"] if p not in used]

    return {
        "domain": domain,
        "required_missing": required_missing,
        "recommended_missing": recommended_missing,
    }


# ---------------------------------------------------------------------------
# compute_overall_score
# ---------------------------------------------------------------------------

def compute_overall_score(
    pattern_score: float,
    confusion_score: Optional[float],
    context_efficiency: float,
    defaults_first_score: float,
) -> float:
    """全軸の重み付き平均でオーバーオールスコアを計算する。

    confusion_score が None の場合、inverse_confusion の weight を除外し、
    残りの weight を再正規化して計算する。
    結果は 0.0-1.0 にクランプされる。
    """
    scores = {
        "pattern_score": pattern_score,
        "context_efficiency": context_efficiency,
        "defaults_first": defaults_first_score,
    }

    if confusion_score is not None:
        scores["inverse_confusion"] = 1.0 - confusion_score

    # 使用する weight のみ抽出
    active_weights = {k: OVERALL_WEIGHTS[k] for k in scores}
    total_weight = sum(active_weights.values())

    if total_weight <= 0:
        return 0.0

    # 再正規化して重み付き平均
    result = sum(
        (w / total_weight) * scores[k]
        for k, w in active_weights.items()
    )

    return min(1.0, max(0.0, result))


# ---------------------------------------------------------------------------
# record_quality_score — スコアボード
# ---------------------------------------------------------------------------

def record_quality_score(
    skill_name: str,
    scores: Dict[str, Any],
    *,
    data_dir: Optional[Path] = None,
) -> None:
    """quality-scores.jsonl にスキルのスコアを追記する。

    Args:
        skill_name: スキル名。
        scores: スコア辞書（pattern_score, confusion_score, overall 等）。
        data_dir: 出力ディレクトリ（テスト用）。
    """
    if data_dir is None:
        from hooks.common import DATA_DIR
        data_dir = DATA_DIR

    data_dir.mkdir(parents=True, exist_ok=True)
    filepath = data_dir / "quality-scores.jsonl"

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill": skill_name,
        **scores,
    }

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
