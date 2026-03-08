#!/usr/bin/env python3
"""Chaos Testing — 仮想アブレーションによる環境ロバストネス評価。

各 Rule/Skill を仮想的に除去し、Coherence Score の変動幅から
環境の頑健性（Robustness Score）と単一障害点（SPOF）を検出する。
実ファイルは一切変更しない。
"""
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
_fitness_dir = Path(__file__).resolve().parent


def _ensure_paths():
    """遅延パス追加。テスト時のパス衝突を防ぐ。"""
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


THRESHOLDS = {
    "critical_delta": 0.10,
    "spof_delta": 0.15,
    "low_delta": 0.02,
}


def _classify_criticality(delta_score: float) -> str:
    """ΔScore から criticality を分類する。"""
    if delta_score >= THRESHOLDS["critical_delta"]:
        return "critical"
    if delta_score >= THRESHOLDS["low_delta"]:
        return "important"
    return "low"


def _collect_ablation_targets(project_dir: Path) -> List[Dict[str, Any]]:
    """アブレーション対象の Rule/Skill ファイルを収集する。

    Returns:
        [{"path": Path, "layer": "rules"|"skills", "name": str}, ...]
    """
    targets: List[Dict[str, Any]] = []
    claude_dir = project_dir / ".claude"

    # Rules
    rules_dir = claude_dir / "rules"
    if rules_dir.exists():
        for rule_path in sorted(rules_dir.glob("*.md")):
            targets.append({
                "path": rule_path,
                "layer": "rules",
                "name": rule_path.stem,
            })

    # Skills (SKILL.md)
    skills_dir = claude_dir / "skills"
    if skills_dir.exists():
        for skill_path in sorted(skills_dir.rglob("SKILL.md")):
            targets.append({
                "path": skill_path,
                "layer": "skills",
                "name": skill_path.parent.name,
            })

    return targets


def _prepare_shadow_project(project_dir: Path, tmp_root: Path) -> Path:
    """一時ディレクトリにプロジェクトのシャドウコピーを作成する。

    コピー対象: CLAUDE.md, .claude/ ディレクトリ
    """
    shadow_dir = tmp_root / "shadow"
    shadow_dir.mkdir(parents=True, exist_ok=True)

    # CLAUDE.md
    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists():
        shutil.copy2(claude_md, shadow_dir / "CLAUDE.md")

    # .claude ディレクトリ
    claude_dir = project_dir / ".claude"
    if claude_dir.exists():
        shutil.copytree(claude_dir, shadow_dir / ".claude", dirs_exist_ok=True)

    return shadow_dir


def _ablate_file(shadow_dir: Path, original_path: Path, project_dir: Path) -> None:
    """シャドウコピー内の対象ファイルを空にする。"""
    rel = original_path.relative_to(project_dir)
    target = shadow_dir / rel
    if target.exists():
        target.write_text("", encoding="utf-8")


def compute_chaos_score(project_dir: Path) -> Dict[str, Any]:
    """仮想アブレーションで環境のロバストネスを評価する。

    各 Rule/Skill を1つずつ仮想除去し、Coherence Score の変動から
    重要度ランキング・SPOF・ロバストネススコアを算出する。

    Args:
        project_dir: プロジェクトディレクトリのパス

    Returns:
        {
            "robustness_score": float,
            "baseline_coherence": float,
            "max_delta_score": float,
            "importance_ranking": [...],
            "single_point_of_failure": [...],
            "elements_tested": int,
        }
    """
    _ensure_paths()
    project_dir = Path(project_dir)
    coherence_mod = _load_sibling("coherence")

    # ベースライン Coherence Score
    baseline_result = coherence_mod.compute_coherence_score(project_dir)
    baseline = baseline_result["overall"]

    # アブレーション対象収集
    targets = _collect_ablation_targets(project_dir)

    importance_ranking: List[Dict[str, Any]] = []
    spof_list: List[Dict[str, Any]] = []
    max_delta = 0.0

    if targets:
        with tempfile.TemporaryDirectory() as tmp_root:
            tmp_root_path = Path(tmp_root)

            for target in targets:
                # 各ターゲットごとにシャドウコピーを作成
                shadow_dir = _prepare_shadow_project(project_dir, tmp_root_path)
                try:
                    # 対象ファイルを空にする
                    _ablate_file(shadow_dir, target["path"], project_dir)

                    # アブレーション後の Coherence Score を計算
                    ablated_result = coherence_mod.compute_coherence_score(shadow_dir)
                    ablated_score = ablated_result["overall"]

                    delta_score = round(baseline - ablated_score, 4)
                    # 負の delta（除去で改善）も記録するが、0 未満は 0 に丸めない
                    criticality = _classify_criticality(max(delta_score, 0.0))

                    entry = {
                        "name": target["name"],
                        "layer": target["layer"],
                        "delta_score": delta_score,
                        "criticality": criticality,
                    }
                    importance_ranking.append(entry)

                    if delta_score > max_delta:
                        max_delta = delta_score

                    if delta_score >= THRESHOLDS["spof_delta"]:
                        spof_list.append({
                            "name": target["name"],
                            "layer": target["layer"],
                            "delta_score": delta_score,
                        })
                finally:
                    # シャドウディレクトリをクリーンアップ（次のターゲット用）
                    shadow_path = tmp_root_path / "shadow"
                    if shadow_path.exists():
                        shutil.rmtree(shadow_path)

    # delta_score 降順でソート
    importance_ranking.sort(key=lambda x: x["delta_score"], reverse=True)
    spof_list.sort(key=lambda x: x["delta_score"], reverse=True)

    # Robustness Score
    robustness_score = max(0.0, 1.0 - (max_delta / max(baseline, 0.01)))

    return {
        "robustness_score": round(robustness_score, 4),
        "baseline_coherence": baseline,
        "max_delta_score": round(max_delta, 4),
        "importance_ranking": importance_ranking,
        "single_point_of_failure": spof_list,
        "elements_tested": len(targets),
    }


def format_chaos_report(result: Dict[str, Any]) -> List[str]:
    """Chaos Testing 結果を audit レポート用にフォーマットする。"""
    lines = [
        f"## Chaos Testing (Robustness): {result['robustness_score']:.2f}",
        "",
        f"Baseline Coherence: {result['baseline_coherence']:.2f}",
        f"Max ΔScore: {result['max_delta_score']:.4f}",
        f"Elements Tested: {result['elements_tested']}",
        "",
    ]

    # SPOF 警告
    if result["single_point_of_failure"]:
        lines.append("### Single Points of Failure")
        for spof in result["single_point_of_failure"]:
            lines.append(
                f"  ⚠ {spof['name']} ({spof['layer']}) — Δ{spof['delta_score']:.4f}"
            )
        lines.append("")

    # 重要度ランキング（上位10件）
    ranking = result["importance_ranking"]
    if ranking:
        lines.append("### Importance Ranking (top 10)")
        for entry in ranking[:10]:
            marker = ""
            if entry["criticality"] == "critical":
                marker = " [CRITICAL]"
            elif entry["criticality"] == "important":
                marker = " [IMPORTANT]"
            lines.append(
                f"  {entry['name']:30s} ({entry['layer']:6s}) Δ{entry['delta_score']:.4f}{marker}"
            )
        lines.append("")

    return lines


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Chaos Testing — 仮想アブレーション")
    parser.add_argument("project_dir", help="プロジェクトディレクトリ")
    args = parser.parse_args()

    result = compute_chaos_score(Path(args.project_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
