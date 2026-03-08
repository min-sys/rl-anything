#!/usr/bin/env python3
"""Constitutional Evaluation モジュール。

原則リスト × 4レイヤー（CLAUDE.md/Rules/Skills/Memory）を LLM Judge で評価し、
Constitutional Score（0.0〜1.0）を算出する。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
_fitness_dir = Path(__file__).resolve().parent

THRESHOLDS = {
    "min_coverage_for_eval": 0.5,
    "llm_timeout_sec": 60,
}

# Haiku pricing (per 1M tokens)
_HAIKU_INPUT_COST_PER_M = 0.25
_HAIKU_OUTPUT_COST_PER_M = 1.25
# Rough chars-per-token estimate
_CHARS_PER_TOKEN = 4


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
    import importlib.util

    path = _fitness_dir / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"fitness_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Layer content helpers
# ---------------------------------------------------------------------------

_LAYER_NAMES = ["claude_md", "rules", "skills", "memory"]


def _collect_layer_contents(project_dir: Path) -> Dict[str, str]:
    """各レイヤーのコンテンツを文字列として収集する。"""
    _ensure_paths()
    coherence_mod = _load_sibling("coherence")
    artifacts = coherence_mod._find_artifacts_local(project_dir)

    contents: Dict[str, str] = {}
    for layer in _LAYER_NAMES:
        paths = artifacts.get(layer, [])
        parts: List[str] = []
        for p in paths:
            try:
                text = p.read_text(encoding="utf-8")
                try:
                    label = str(p.relative_to(project_dir))
                except ValueError:
                    label = p.name
                parts.append(f"--- {label} ---\n{text}")
            except (OSError, UnicodeDecodeError):
                continue
        if parts:
            contents[layer] = "\n\n".join(parts)
    return contents


def _content_hash(content: str) -> str:
    """SHA-256 ハッシュを返す。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_path(project_dir: Path) -> Path:
    return project_dir / ".claude" / "constitutional_cache.json"


def _load_cache(project_dir: Path) -> Optional[Dict[str, Any]]:
    path = _cache_path(project_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(project_dir: Path, data: Dict[str, Any]) -> None:
    path = _cache_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def _estimate_cost(input_chars: int, output_chars: int) -> float:
    """Haiku の推定コスト (USD) を返す。"""
    input_tokens = input_chars / _CHARS_PER_TOKEN
    output_tokens = output_chars / _CHARS_PER_TOKEN
    cost = (
        input_tokens / 1_000_000 * _HAIKU_INPUT_COST_PER_M
        + output_tokens / 1_000_000 * _HAIKU_OUTPUT_COST_PER_M
    )
    return cost


# ---------------------------------------------------------------------------
# LLM evaluation
# ---------------------------------------------------------------------------

def _build_eval_prompt(layer_name: str, layer_content: str, principles: List[Dict[str, Any]]) -> str:
    """レイヤー評価用プロンプトを構築する。"""
    principles_text = "\n".join(
        f"  {i+1}. id={p['id']}: {p['text']}"
        for i, p in enumerate(principles)
    )
    return f"""You are evaluating a Claude Code environment layer against a set of principles.

## Layer: {layer_name}

{layer_content}

## Principles to evaluate

{principles_text}

## Instructions

For each principle, evaluate how well this layer adheres to it.
Return a JSON object with the following structure (no markdown fences, raw JSON only):

{{
  "evaluations": [
    {{
      "principle_id": "<id>",
      "score": <float 0.0-1.0>,
      "rationale": "<brief explanation>",
      "violations": ["<violation description>", ...]
    }}
  ]
}}

Rules:
- score 1.0 = fully compliant, 0.0 = completely non-compliant
- If the layer content is not relevant to a principle, score 0.8 (neutral-positive)
- violations should be empty list if score >= 0.8
- Be concise in rationale (1-2 sentences)
"""


def _parse_llm_response(raw: str) -> Optional[Dict[str, Any]]:
    """LLM レスポンスから JSON をパースする。"""
    text = raw.strip()
    # マークダウンコードブロック除去
    if text.startswith("```"):
        lines = text.split("\n")
        # 先頭と末尾の ``` 行を除去
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _evaluate_layer(
    layer_name: str,
    layer_content: str,
    principles: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """1レイヤーを LLM で評価する。リトライ1回。失敗時は None。

    Returns:
        {
            "evaluations": [{"principle_id", "score", "rationale", "violations"}, ...],
            "input_chars": int,
            "output_chars": int,
        }
    """
    prompt = _build_eval_prompt(layer_name, layer_content, principles)
    timeout = THRESHOLDS["llm_timeout_sec"]

    for attempt in range(2):  # 最大2回（初回 + 1リトライ）
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", "haiku"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                continue

            raw_output = result.stdout
            parsed = _parse_llm_response(raw_output)
            if parsed is None:
                continue

            evaluations = parsed.get("evaluations", [])
            if not evaluations:
                continue

            # スコア clamp
            for ev in evaluations:
                if "score" in ev:
                    ev["score"] = _clamp(float(ev["score"]))

            return {
                "evaluations": evaluations,
                "input_chars": len(prompt),
                "output_chars": len(raw_output),
            }
        except subprocess.TimeoutExpired:
            return None
        except Exception:
            continue

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def compute_constitutional_score(
    project_dir: Path,
    refresh: bool = False,
) -> Optional[Dict[str, Any]]:
    """Constitutional Score を算出する。

    Returns:
        成功時: {"overall", "per_principle", "per_layer", "violations", ...}
        スキップ時: {"overall": None, "skip_reason", "coverage_value"}
        全失敗時: None
    """
    _ensure_paths()
    project_dir = Path(project_dir)

    # --- Coherence Coverage gate ---
    coherence_mod = _load_sibling("coherence")
    try:
        coherence_result = coherence_mod.compute_coherence_score(project_dir)
        coverage = coherence_result["coverage"]
    except Exception:
        coverage = 0.0

    if coverage < THRESHOLDS["min_coverage_for_eval"]:
        return {
            "overall": None,
            "skip_reason": "low_coverage",
            "coverage_value": coverage,
        }

    # --- Principles ---
    principles_mod = _load_sibling("principles")
    principles_result = principles_mod.extract_principles(project_dir)
    principles = principles_result["principles"]
    if not principles:
        return None

    # --- Layer contents ---
    layer_contents = _collect_layer_contents(project_dir)
    if not layer_contents:
        return None

    # --- Cache handling ---
    cache = _load_cache(project_dir) if not refresh else None
    cached_layers: Dict[str, Dict[str, Any]] = {}
    cached_hashes: Dict[str, str] = {}
    if cache:
        cached_layers = cache.get("layer_results", {})
        cached_hashes = cache.get("layer_hashes", {})

    # --- Per-layer evaluation ---
    layer_results: Dict[str, Dict[str, Any]] = {}
    layer_hashes: Dict[str, str] = {}
    total_input_chars = 0
    total_output_chars = 0
    llm_calls = 0
    from_cache_count = 0

    for layer_name, content in layer_contents.items():
        content_hash = _content_hash(content)
        layer_hashes[layer_name] = content_hash

        # キャッシュ一致チェック
        if (
            not refresh
            and layer_name in cached_layers
            and cached_hashes.get(layer_name) == content_hash
        ):
            layer_results[layer_name] = cached_layers[layer_name]
            from_cache_count += 1
            continue

        # LLM 評価
        eval_result = _evaluate_layer(layer_name, content, principles)
        if eval_result is None:
            continue  # スキップ

        layer_results[layer_name] = {
            "evaluations": eval_result["evaluations"],
        }
        total_input_chars += eval_result["input_chars"]
        total_output_chars += eval_result["output_chars"]
        llm_calls += 1

    # --- 全レイヤー失敗 ---
    if not layer_results:
        return None

    # --- Score aggregation ---
    # principle_id → list of scores across layers
    principle_scores: Dict[str, List[float]] = {}
    # layer_name → list of scores across principles
    layer_scores_map: Dict[str, List[float]] = {}
    # All violations
    all_violations: List[Dict[str, Any]] = []

    for layer_name, lr in layer_results.items():
        scores_for_layer: List[float] = []
        for ev in lr["evaluations"]:
            pid = ev.get("principle_id", "unknown")
            score = ev.get("score", 0.0)
            scores_for_layer.append(score)

            if pid not in principle_scores:
                principle_scores[pid] = []
            principle_scores[pid].append(score)

            # Collect violations
            for v in ev.get("violations", []):
                all_violations.append({
                    "principle_id": pid,
                    "layer": layer_name,
                    "description": v,
                })

        if scores_for_layer:
            layer_scores_map[layer_name] = scores_for_layer

    # per_principle
    per_principle: List[Dict[str, Any]] = []
    principle_means: List[float] = []
    for p in principles:
        pid = p["id"]
        scores = principle_scores.get(pid, [])
        mean_score = sum(scores) / len(scores) if scores else 0.0
        per_principle.append({
            "id": pid,
            "text": p["text"],
            "score": round(mean_score, 4),
        })
        if scores:
            principle_means.append(mean_score)

    # per_layer
    per_layer: Dict[str, float] = {}
    for layer_name, scores in layer_scores_map.items():
        per_layer[layer_name] = round(sum(scores) / len(scores), 4) if scores else 0.0

    # overall
    overall = round(sum(principle_means) / len(principle_means), 4) if principle_means else 0.0

    # Cost estimation
    estimated_cost = _estimate_cost(total_input_chars, total_output_chars)

    result = {
        "overall": overall,
        "per_principle": per_principle,
        "per_layer": per_layer,
        "violations": all_violations,
        "evaluated_layers": len(layer_results),
        "total_layers": len(layer_contents),
        "estimated_cost_usd": round(estimated_cost, 6),
        "llm_calls_count": llm_calls,
        "from_cache": from_cache_count > 0,
    }

    # --- Save cache ---
    cache_data = {
        "layer_results": layer_results,
        "layer_hashes": layer_hashes,
    }
    try:
        _save_cache(project_dir, cache_data)
    except OSError:
        pass

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Constitutional Evaluation")
    parser.add_argument("project_dir", help="プロジェクトディレクトリ")
    parser.add_argument("--refresh", action="store_true", help="キャッシュを無視して再評価")
    args = parser.parse_args()

    result = compute_constitutional_score(Path(args.project_dir), refresh=args.refresh)
    print(json.dumps(result, ensure_ascii=False, indent=2))
