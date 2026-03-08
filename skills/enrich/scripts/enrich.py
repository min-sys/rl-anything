#!/usr/bin/env python3
"""Enrich フェーズスクリプト。

.. deprecated::
    discover.py に _enrich_patterns() として統合済み。
    このファイルは後方互換のためのみ残存。新規利用は discover.py を使用すること。

Discover の出力（error_patterns, rejection_patterns, behavior_patterns）を受け取り、
既存スキルと Jaccard 係数によるキーワードマッチングで関連付ける。
LLM 呼び出しなし（Type A パターン）。
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

from audit import classify_artifact_origin, find_artifacts, load_usage_data
from similarity import jaccard_coefficient, tokenize


def load_skill_tokens(skill_path: Path) -> Set[str]:
    """SKILL.md の先頭 50 行 + スキル名からトークン集合を生成する。"""
    tokens: Set[str] = set()

    # スキル名（ディレクトリ名）をトークン化
    skill_name = skill_path.parent.name
    tokens |= tokenize(skill_name)

    # SKILL.md の先頭 50 行を読み込み
    try:
        lines = skill_path.read_text(encoding="utf-8").splitlines()[:50]
        for line in lines:
            tokens |= tokenize(line)
    except OSError:
        pass

    return tokens


def match_patterns_to_skills(
    patterns: List[Dict[str, Any]],
    artifacts: Dict[str, List[Path]],
    max_matches: int = 3,
) -> List[Dict[str, Any]]:
    """パターンをスキルに Jaccard 係数でマッチングする。

    プラグイン由来のスキルは除外する。
    Jaccard >= 0.15 のマッチのみ保持し、上位 max_matches 件を返す。
    """
    # 非プラグインスキルのトークンを事前計算
    skill_info: List[Dict[str, Any]] = []
    for skill_path in artifacts.get("skills", []):
        origin = classify_artifact_origin(skill_path)
        if origin == "plugin":
            continue
        tokens = load_skill_tokens(skill_path)
        skill_info.append({
            "path": skill_path,
            "name": skill_path.parent.name,
            "tokens": tokens,
        })

    matches: List[Dict[str, Any]] = []

    for pattern in patterns:
        pattern_text = pattern.get("pattern", "")
        pattern_type = pattern.get("type", "unknown")
        pattern_tokens = tokenize(pattern_text)

        if not pattern_tokens:
            continue

        # 各スキルとの Jaccard を計算
        scored: List[Dict[str, Any]] = []
        for info in skill_info:
            score = jaccard_coefficient(pattern_tokens, info["tokens"])
            if score >= 0.15:
                scored.append({
                    "pattern_type": pattern_type,
                    "pattern": pattern_text,
                    "matched_skill": info["name"],
                    "skill_path": str(info["path"]),
                    "jaccard_score": round(score, 4),
                })

        # スコア降順で上位 max_matches 件
        scored.sort(key=lambda x: x["jaccard_score"], reverse=True)
        matches.extend(scored[:max_matches])

    return matches


def run_enrich(
    discover_result: Dict[str, Any],
    project_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Enrich を実行して enrichment 結果を返す。

    Args:
        discover_result: Discover の出力（error_patterns, rejection_patterns, behavior_patterns）
        project_dir: プロジェクトディレクトリ（省略時は cwd）

    Returns:
        enrichments, unmatched_patterns, total_enrichments, total_unmatched を含む辞書
    """
    proj = Path(project_dir) if project_dir else Path.cwd()
    artifacts = find_artifacts(proj)

    error_patterns = discover_result.get("error_patterns", [])
    rejection_patterns = discover_result.get("rejection_patterns", [])
    behavior_patterns = discover_result.get("behavior_patterns", [])

    # 使用するパターンを決定
    if error_patterns or rejection_patterns:
        active_patterns = error_patterns + rejection_patterns
    elif behavior_patterns:
        active_patterns = behavior_patterns
    else:
        return {
            "enrichments": [],
            "unmatched_patterns": [],
            "total_enrichments": 0,
            "total_unmatched": 0,
            "skipped_reason": "no_patterns_available",
        }

    # マッチング実行
    enrichments = match_patterns_to_skills(active_patterns, artifacts)

    # マッチしたパターンを追跡
    matched_pattern_texts = set(e["pattern"] for e in enrichments)

    # 未マッチパターンを収集
    unmatched_patterns: List[Dict[str, Any]] = []
    for pattern in active_patterns:
        pattern_text = pattern.get("pattern", "")
        if pattern_text not in matched_pattern_texts:
            suggestion = pattern.get("suggestion", "skill_candidate")
            unmatched_patterns.append({
                "pattern_type": pattern.get("type", "unknown"),
                "pattern": pattern_text,
                "suggestion": suggestion,
            })

    return {
        "enrichments": enrichments,
        "unmatched_patterns": unmatched_patterns,
        "total_enrichments": len(enrichments),
        "total_unmatched": len(unmatched_patterns),
    }


if __name__ == "__main__":
    # Discover の出力を stdin から受け取る
    import sys as _sys

    if len(_sys.argv) > 1:
        discover_input = json.loads(Path(_sys.argv[1]).read_text(encoding="utf-8"))
    else:
        discover_input = json.loads(_sys.stdin.read())

    project = _sys.argv[2] if len(_sys.argv) > 2 else None
    result = run_enrich(discover_input, project)
    print(json.dumps(result, ensure_ascii=False, indent=2))
