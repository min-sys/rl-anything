#!/usr/bin/env python3
"""統合 Environment Fitness スコア。

Coherence Score（構造品質）、Telemetry Score（行動実績）、
Constitutional Score（原則遵守）、Skill Quality Score をブレンドする。
利用可能な軸に応じて BASE_WEIGHTS を動的正規化。
"""
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
_fitness_dir = Path(__file__).resolve().parent

try:
    from .config import BASE_WEIGHTS
except ImportError:
    try:
        # importlib 経由でロードされた場合のフォールバック
        _cfg_path = _fitness_dir / "config.py"
        _cfg_spec = importlib.util.spec_from_file_location("fitness_config", _cfg_path)
        _cfg_mod = importlib.util.module_from_spec(_cfg_spec)
        _cfg_spec.loader.exec_module(_cfg_mod)
        BASE_WEIGHTS = _cfg_mod.BASE_WEIGHTS
    except Exception:
        # 完全フォールバック — config.py が壊れても動作
        BASE_WEIGHTS = {
            "coherence": 0.23,
            "telemetry": 0.43,
            "constitutional": 0.29,
            "skill_quality": 0.05,
        }


def _ensure_paths():
    paths = [
        str(_plugin_root / "scripts" / "rl"),
        str(_plugin_root / "scripts" / "lib"),
        str(_plugin_root / "scripts"),
        str(_plugin_root / "skills" / "audit" / "scripts"),
    ]
    for p in paths:
        if p not in sys.path:
            sys.path.insert(0, p)


def _load_sibling(name: str):
    """同ディレクトリのモジュールを importlib で安全にロードする。"""
    path = _fitness_dir / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"fitness_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _normalize_weights(available_axes: list) -> Dict[str, float]:
    """利用可能な軸のみで BASE_WEIGHTS を正規化（合計=1.0）。"""
    raw = {k: v for k, v in BASE_WEIGHTS.items() if k in available_axes}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {k: round(v / total, 6) for k, v in raw.items()}


def compute_environment_fitness(project_dir: Path, days: int = 30) -> Dict[str, Any]:
    """利用可能な軸を動的に判定し、正規化重みでブレンドした統合 Environment Fitness を算出する。"""
    _ensure_paths()
    project_dir = Path(project_dir).resolve()

    # --- 各軸の算出 ---
    axis_scores: Dict[str, float] = {}
    axis_results: Dict[str, Any] = {}

    # Coherence
    try:
        coherence_mod = _load_sibling("coherence")
        coherence_result = coherence_mod.compute_coherence_score(project_dir)
        axis_scores["coherence"] = coherence_result["overall"]
        axis_results["coherence"] = coherence_result
    except Exception:
        pass

    # Telemetry
    try:
        telemetry_mod = _load_sibling("telemetry")
        telemetry_result = telemetry_mod.compute_telemetry_score(project_dir, days)
        if telemetry_result.get("data_sufficiency"):
            axis_scores["telemetry"] = telemetry_result["overall"]
        axis_results["telemetry"] = telemetry_result
    except Exception:
        pass

    # Constitutional
    try:
        constitutional_mod = _load_sibling("constitutional")
        constitutional_result = constitutional_mod.compute_constitutional_score(project_dir)
        if constitutional_result and constitutional_result.get("overall") is not None:
            axis_scores["constitutional"] = constitutional_result["overall"]
            axis_results["constitutional"] = constitutional_result
        else:
            axis_results["constitutional"] = constitutional_result
    except Exception:
        pass

    # Skill Quality
    try:
        sq_mod = _load_sibling("skill_quality")
        # skill_quality は stdin/stdout スクリプト形式のため、
        # ここでは project_dir 配下のスキルを直接走査して平均スコアを算出
        skills_dir = project_dir / ".claude" / "skills"
        if skills_dir.is_dir():
            sq_scores = []
            for skill_dir in skills_dir.iterdir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.is_file():
                    try:
                        content = skill_md.read_text(encoding="utf-8")
                        score_result = sq_mod.evaluate_skill_quality(content, str(skill_dir))
                        if score_result and "overall" in score_result:
                            sq_scores.append(score_result["overall"])
                    except Exception:
                        continue
            if sq_scores:
                avg_sq = sum(sq_scores) / len(sq_scores)
                axis_scores["skill_quality"] = avg_sq
                axis_results["skill_quality"] = {
                    "overall": avg_sq,
                    "skills_evaluated": len(sq_scores),
                }
    except Exception:
        pass

    # --- 動的正規化 ---
    sources = list(axis_scores.keys())
    weights_used = _normalize_weights(sources)

    if weights_used:
        overall = sum(
            axis_scores[axis] * weights_used[axis]
            for axis in weights_used
        )
    else:
        overall = 0.0

    result: Dict[str, Any] = {
        "overall": round(overall, 4),
        "sources": sources,
        "weights": weights_used,
    }
    for axis_name, axis_result in axis_results.items():
        if axis_result is not None:
            result[axis_name] = axis_result

    return result


def format_environment_report(result: Dict[str, Any]) -> List[str]:
    """Environment Fitness を audit レポート用にフォーマットする。"""
    lines = [f"## Environment Fitness: {result['overall']:.2f}", ""]
    lines.append(f"Sources: {', '.join(result['sources']) if result['sources'] else 'none'}")

    weights = result.get("weights", {})
    if "coherence" in result and isinstance(result["coherence"], dict):
        w = weights.get("coherence", 0)
        lines.append(f"  Coherence:      {result['coherence']['overall']:.2f} (weight {w:.2f})")
    if "telemetry" in result and isinstance(result["telemetry"], dict):
        tel = result["telemetry"]
        w = weights.get("telemetry", 0)
        lines.append(f"  Telemetry:      {tel['overall']:.2f} (weight {w:.2f})")
        if not tel.get("data_sufficiency", True):
            lines.append("  (Telemetry data insufficient — using coherence only)")
    if "constitutional" in result and isinstance(result["constitutional"], dict):
        con = result["constitutional"]
        if con and con.get("overall") is not None:
            w = weights.get("constitutional", 0)
            lines.append(f"  Constitutional: {con['overall']:.2f} (weight {w:.2f})")
        elif con and con.get("skip_reason"):
            lines.append(f"  Constitutional: skipped ({con['skip_reason']})")
    if "skill_quality" in result and isinstance(result["skill_quality"], dict):
        sq = result["skill_quality"]
        w = weights.get("skill_quality", 0)
        lines.append(f"  Skill Quality:  {sq['overall']:.2f} (weight {w:.2f})")

    lines.append("")
    return lines


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Environment Fitness 算出")
    parser.add_argument("project_dir", help="プロジェクトディレクトリ")
    parser.add_argument("--days", type=int, default=30, help="集計期間（日）")
    args = parser.parse_args()

    result = compute_environment_fitness(Path(args.project_dir), args.days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
