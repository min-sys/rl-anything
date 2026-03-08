#!/usr/bin/env python3
"""プロジェクトの設計原則を抽出・キャッシュするモジュール。

CLAUDE.md + Rules ファイルから LLM で原則を抽出し、
品質スコアでフィルタリングして .claude/principles.json にキャッシュする。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent


def _ensure_paths():
    """遅延パス追加。テスト時のパス衝突を防ぐ。"""
    paths = [
        str(_plugin_root / "scripts" / "lib"),
        str(_plugin_root / "scripts"),
    ]
    for p in paths:
        if p not in sys.path:
            sys.path.insert(0, p)


THRESHOLDS = {
    "min_coverage_for_eval": 0.5,
    "min_principle_quality": 0.3,
}

SEED_PRINCIPLES: List[Dict[str, Any]] = [
    {
        "id": "single-responsibility",
        "text": "各スキル/ルールは単一の責務を持つ",
        "source": "seed",
        "category": "quality",
        "specificity": 0.7,
        "testability": 0.8,
        "seed": True,
    },
    {
        "id": "graceful-degradation",
        "text": "外部依存の失敗時にフォールバックする",
        "source": "seed",
        "category": "safety",
        "specificity": 0.6,
        "testability": 0.7,
        "seed": True,
    },
    {
        "id": "user-consent",
        "text": "破壊的操作の前にユーザー確認を取る",
        "source": "seed",
        "category": "safety",
        "specificity": 0.8,
        "testability": 0.9,
        "seed": True,
    },
    {
        "id": "idempotency",
        "text": "同じ操作の繰り返しで副作用が増大しない",
        "source": "seed",
        "category": "quality",
        "specificity": 0.7,
        "testability": 0.8,
        "seed": True,
    },
    {
        "id": "minimal-llm-cost",
        "text": "LLM 呼び出しを最小化する",
        "source": "seed",
        "category": "performance",
        "specificity": 0.6,
        "testability": 0.6,
        "seed": True,
    },
]


def _compute_source_hash(project_dir: Path) -> str:
    """CLAUDE.md + 全 Rules ファイルの SHA-256 ハッシュを算出する。"""
    hasher = hashlib.sha256()

    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists():
        try:
            hasher.update(claude_md.read_bytes())
        except OSError:
            pass

    rules_dir = project_dir / ".claude" / "rules"
    if rules_dir.exists():
        for rule_path in sorted(rules_dir.glob("*.md")):
            try:
                hasher.update(rule_path.read_bytes())
            except OSError:
                pass

    return hasher.hexdigest()


def _read_source_content(project_dir: Path) -> str:
    """CLAUDE.md + Rules ファイルの内容を結合して返す。"""
    parts: List[str] = []

    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists():
        try:
            content = claude_md.read_text(encoding="utf-8")
            parts.append(f"=== CLAUDE.md ===\n{content}")
        except (OSError, UnicodeDecodeError):
            pass

    rules_dir = project_dir / ".claude" / "rules"
    if rules_dir.exists():
        for rule_path in sorted(rules_dir.glob("*.md")):
            try:
                content = rule_path.read_text(encoding="utf-8")
                parts.append(f"=== {rule_path.name} ===\n{content}")
            except (OSError, UnicodeDecodeError):
                pass

    return "\n\n".join(parts)


def _build_extraction_prompt(source_content: str) -> str:
    """LLM に渡す原則抽出プロンプトを構築する。"""
    return f"""以下のプロジェクト設定ファイルから、設計原則・ルール・ベストプラクティスを抽出してください。

各原則について以下の形式の JSON 配列で返してください（JSON のみ、説明不要）:

[
  {{
    "id": "kebab-case-id",
    "text": "原則の説明文",
    "source": "抽出元ファイル名",
    "category": "quality|safety|performance|convention",
    "specificity": 0.0-1.0,
    "testability": 0.0-1.0
  }}
]

specificity: 原則がどれだけ具体的か（0.0=曖昧、1.0=非常に具体的）
testability: 原則の遵守を機械的に検証できるか（0.0=検証不可、1.0=完全に自動検証可能）

--- ファイル内容 ---
{source_content}"""


def _extract_via_llm(source_content: str) -> Optional[List[Dict[str, Any]]]:
    """claude CLI で原則を抽出する。失敗時は None を返す。"""
    if not source_content.strip():
        return []

    prompt = _build_extraction_prompt(source_content)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "haiku"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"[principles] LLM call failed: {e}", file=sys.stderr)
        return None

    if result.returncode != 0:
        print(
            f"[principles] LLM call returned non-zero: {result.returncode}",
            file=sys.stderr,
        )
        return None

    output = result.stdout.strip()

    # JSON 配列を抽出（コードブロックで囲まれている場合に対応）
    if "```" in output:
        lines = output.splitlines()
        in_block = False
        json_lines: List[str] = []
        for line in lines:
            if line.strip().startswith("```"):
                if in_block:
                    break
                in_block = True
                continue
            if in_block:
                json_lines.append(line)
        output = "\n".join(json_lines)

    # JSON 配列の開始位置を探す
    start = output.find("[")
    end = output.rfind("]")
    if start == -1 or end == -1:
        print("[principles] LLM output does not contain JSON array", file=sys.stderr)
        return None

    try:
        principles = json.loads(output[start : end + 1])
        if not isinstance(principles, list):
            return None
        return principles
    except json.JSONDecodeError as e:
        print(f"[principles] Failed to parse LLM JSON: {e}", file=sys.stderr)
        return None


def _quality_score(principle: Dict[str, Any]) -> float:
    """原則の品質スコアを算出する。"""
    specificity = float(principle.get("specificity", 0.0))
    testability = float(principle.get("testability", 0.0))
    return (specificity + testability) / 2.0


def _filter_by_quality(
    principles: List[Dict[str, Any]],
) -> tuple:
    """品質スコアでフィルタリングする。seed は除外対象外。

    Returns:
        (passed, excluded_low_quality)
    """
    passed: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    threshold = THRESHOLDS["min_principle_quality"]

    for p in principles:
        if p.get("seed"):
            passed.append(p)
        elif _quality_score(p) < threshold:
            excluded.append(p)
        else:
            passed.append(p)

    return passed, excluded


def _cache_path(project_dir: Path) -> Path:
    """キャッシュファイルのパスを返す。"""
    return project_dir / ".claude" / "principles.json"


def _load_cache(project_dir: Path) -> Optional[Dict[str, Any]]:
    """キャッシュを読み込む。存在しない/不正な場合は None。"""
    path = _cache_path(project_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "principles" in data:
            return data
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        pass
    return None


def _save_cache(project_dir: Path, data: Dict[str, Any]) -> None:
    """キャッシュを保存する。"""
    path = _cache_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        print(f"[principles] Failed to save cache: {e}", file=sys.stderr)


def _merge_user_defined(
    new_principles: List[Dict[str, Any]],
    cached_principles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """user_defined 原則をキャッシュから復元してマージする。"""
    user_defined = [p for p in cached_principles if p.get("user_defined")]
    if not user_defined:
        return new_principles

    # 新規抽出の ID セット
    new_ids = {p["id"] for p in new_principles if "id" in p}

    # user_defined で ID が重複しないものを追加
    merged = list(new_principles)
    for ud in user_defined:
        if ud.get("id") not in new_ids:
            merged.append(ud)

    return merged


def extract_principles(
    project_dir: str | Path,
    refresh: bool = False,
) -> Dict[str, Any]:
    """プロジェクトから設計原則を抽出する。

    Args:
        project_dir: プロジェクトディレクトリパス
        refresh: True の場合キャッシュを無視して再抽出

    Returns:
        {
            "principles": [...],
            "excluded_low_quality": [...],
            "source_hash": "sha256...",
            "stale_cache": bool,
            "from_cache": bool,
        }
    """
    project_dir = Path(project_dir)
    current_hash = _compute_source_hash(project_dir)

    # キャッシュ利用（refresh=False の場合）
    if not refresh:
        cached = _load_cache(project_dir)
        if cached is not None:
            stale = cached.get("source_hash", "") != current_hash
            return {
                "principles": cached.get("principles", []),
                "excluded_low_quality": cached.get("excluded_low_quality", []),
                "source_hash": current_hash,
                "stale_cache": stale,
                "from_cache": True,
            }

    # user_defined を保存用に退避
    cached_for_merge = _load_cache(project_dir)
    cached_principles = (
        cached_for_merge.get("principles", []) if cached_for_merge else []
    )

    # ソースコンテンツ読み込み + LLM 抽出
    source_content = _read_source_content(project_dir)
    llm_principles = _extract_via_llm(source_content)

    if llm_principles is None:
        # LLM 失敗時: seed のみ返す
        print(
            "[principles] LLM extraction failed, returning seed principles only",
            file=sys.stderr,
        )
        result = {
            "principles": list(SEED_PRINCIPLES),
            "excluded_low_quality": [],
            "source_hash": current_hash,
            "stale_cache": False,
            "from_cache": False,
        }
        _save_cache(project_dir, result)
        return result

    # seed 原則を追加（LLM 抽出結果に含まれていない場合）
    llm_ids = {p.get("id") for p in llm_principles}
    all_principles = list(llm_principles)
    for seed in SEED_PRINCIPLES:
        if seed["id"] not in llm_ids:
            all_principles.append(dict(seed))

    # user_defined をマージ
    all_principles = _merge_user_defined(all_principles, cached_principles)

    # 品質フィルタリング
    passed, excluded = _filter_by_quality(all_principles)

    result = {
        "principles": passed,
        "excluded_low_quality": excluded,
        "source_hash": current_hash,
        "stale_cache": False,
        "from_cache": False,
    }
    _save_cache(project_dir, result)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="プロジェクト設計原則の抽出")
    parser.add_argument("project_dir", help="プロジェクトディレクトリ")
    parser.add_argument(
        "--refresh", action="store_true", help="キャッシュを無視して再抽出"
    )
    args = parser.parse_args()

    result = extract_principles(Path(args.project_dir), refresh=args.refresh)
    print(json.dumps(result, ensure_ascii=False, indent=2))
