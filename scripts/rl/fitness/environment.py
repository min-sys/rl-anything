#!/usr/bin/env python3
"""統合 Environment Fitness スコア。

Coherence Score（構造品質）と Telemetry Score（行動実績）をブレンドする。
"""
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
_fitness_dir = Path(__file__).resolve().parent


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


WEIGHTS = {
    "coherence": 0.4,
    "telemetry": 0.6,
}

# Constitutional 利用可能時の 3層ブレンド重み
WEIGHTS_3LAYER = {
    "coherence": 0.25,
    "telemetry": 0.45,
    "constitutional": 0.30,
}

# テレメトリ不足・Constitutional 可時の 2層重み
WEIGHTS_COHERENCE_CONSTITUTIONAL = {
    "coherence": 0.45,
    "constitutional": 0.55,
}


def compute_environment_fitness(project_dir: Path, days: int = 30) -> Dict[str, Any]:
    """Coherence + Telemetry + Constitutional をブレンドした統合 Environment Fitness を算出する。"""
    _ensure_paths()
    project_dir = Path(project_dir).resolve()

    coherence_result = None
    coherence_score = 0.0
    coherence_ok = False
    try:
        coherence_mod = _load_sibling("coherence")
        coherence_result = coherence_mod.compute_coherence_score(project_dir)
        coherence_score = coherence_result["overall"]
        coherence_ok = True
    except Exception:
        pass

    telemetry_result = None
    telemetry_score = 0.0
    telemetry_ok = False
    try:
        telemetry_mod = _load_sibling("telemetry")
        telemetry_result = telemetry_mod.compute_telemetry_score(project_dir, days)
        telemetry_score = telemetry_result["overall"]
        telemetry_ok = telemetry_result["data_sufficiency"]
    except Exception:
        pass

    constitutional_result = None
    constitutional_score = 0.0
    constitutional_ok = False
    try:
        constitutional_mod = _load_sibling("constitutional")
        constitutional_result = constitutional_mod.compute_constitutional_score(project_dir)
        if constitutional_result and constitutional_result.get("overall") is not None:
            constitutional_score = constitutional_result["overall"]
            constitutional_ok = True
    except Exception:
        pass

    sources: List[str] = []
    if coherence_ok:
        sources.append("coherence")
    if telemetry_ok:
        sources.append("telemetry")
    if constitutional_ok:
        sources.append("constitutional")

    # ブレンド重み決定
    if coherence_ok and telemetry_ok and constitutional_ok:
        weights_used = WEIGHTS_3LAYER
        overall = (
            coherence_score * WEIGHTS_3LAYER["coherence"]
            + telemetry_score * WEIGHTS_3LAYER["telemetry"]
            + constitutional_score * WEIGHTS_3LAYER["constitutional"]
        )
    elif coherence_ok and telemetry_ok:
        weights_used = WEIGHTS
        overall = coherence_score * WEIGHTS["coherence"] + telemetry_score * WEIGHTS["telemetry"]
    elif coherence_ok and constitutional_ok:
        weights_used = WEIGHTS_COHERENCE_CONSTITUTIONAL
        overall = (
            coherence_score * WEIGHTS_COHERENCE_CONSTITUTIONAL["coherence"]
            + constitutional_score * WEIGHTS_COHERENCE_CONSTITUTIONAL["constitutional"]
        )
    elif coherence_ok:
        weights_used = {"coherence": 1.0}
        overall = coherence_score
    elif telemetry_ok:
        weights_used = {"telemetry": 1.0}
        overall = telemetry_score
    else:
        weights_used = {}
        overall = 0.0

    result: Dict[str, Any] = {
        "overall": round(overall, 4),
        "sources": sources,
        "weights": weights_used,
    }
    if coherence_result:
        result["coherence"] = coherence_result
    if telemetry_result:
        result["telemetry"] = telemetry_result
    if constitutional_result:
        result["constitutional"] = constitutional_result

    return result


def format_environment_report(result: Dict[str, Any]) -> List[str]:
    """Environment Fitness を audit レポート用にフォーマットする。"""
    lines = [f"## Environment Fitness: {result['overall']:.2f}", ""]
    lines.append(f"Sources: {', '.join(result['sources']) if result['sources'] else 'none'}")

    weights = result.get("weights", {})
    if "coherence" in result:
        w = weights.get("coherence", 0)
        lines.append(f"  Coherence:      {result['coherence']['overall']:.2f} (weight {w:.2f})")
    if "telemetry" in result:
        tel = result["telemetry"]
        w = weights.get("telemetry", 0)
        lines.append(f"  Telemetry:      {tel['overall']:.2f} (weight {w:.2f})")
        if not tel.get("data_sufficiency", True):
            lines.append("  (Telemetry data insufficient — using coherence only)")
    if "constitutional" in result:
        con = result["constitutional"]
        if con and con.get("overall") is not None:
            w = weights.get("constitutional", 0)
            lines.append(f"  Constitutional: {con['overall']:.2f} (weight {w:.2f})")
        elif con and con.get("skip_reason"):
            lines.append(f"  Constitutional: skipped ({con['skip_reason']})")

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
