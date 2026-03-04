#!/usr/bin/env python3
"""LLM セマンティック検証モジュール。

claude-reflect の semantic_detector.py から移植。
corrections を `claude -p` でバッチ検証し、偽陽性を除去する。
"""
import json
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

BATCH_SIZE = 20

ANALYSIS_PROMPT = """以下の corrections リストを分析し、各項目が本当に「学習すべき修正」かどうか判定してください。

判定基準:
- is_learning: true — ユーザーが Claude の行動を変えてほしいと明示的に指示している
- is_learning: false — 質問、タスク依頼、エラー報告、雑談、文脈なしの否定

各項目について以下の JSON 配列を返してください（他のテキストは不要）:
[
  {{"index": 0, "is_learning": true/false, "extracted_learning": "簡潔な学習文 or null"}},
  ...
]

corrections:
{corrections_json}
"""


def semantic_analyze(
    corrections: List[Dict[str, Any]],
    model: str = "sonnet",
) -> List[Dict[str, Any]]:
    """corrections リストを `claude -p` に送信して is_learning 判定を取得する。

    バッチサイズ上限 20件。超過時は複数バッチに分割。

    Args:
        corrections: correction レコードのリスト。各レコードに message フィールドが必要。
        model: 使用するモデル名。

    Returns:
        各 correction に is_learning, extracted_learning を付与したリスト。
    """
    if not corrections:
        return []

    results: List[Dict[str, Any]] = []

    for batch_start in range(0, len(corrections), BATCH_SIZE):
        batch = corrections[batch_start:batch_start + BATCH_SIZE]

        # バッチ用の簡易リストを作成
        batch_items = [
            {"index": i, "message": c.get("message", "")}
            for i, c in enumerate(batch)
        ]

        prompt = ANALYSIS_PROMPT.format(
            corrections_json=json.dumps(batch_items, ensure_ascii=False, indent=2)
        )

        try:
            proc = subprocess.run(
                ["claude", "-p", "--model", model, prompt],
                capture_output=True,
                text=True,
                timeout=60,
            )
            response_text = proc.stdout.strip()
            parsed = _extract_json_array(response_text)

            if parsed and len(parsed) == len(batch):
                for item in parsed:
                    results.append({
                        "is_learning": item.get("is_learning", True),
                        "extracted_learning": item.get("extracted_learning"),
                    })
            else:
                # 件数不一致 → フォールバック
                print(
                    f"Warning: semantic response count mismatch "
                    f"(expected {len(batch)}, got {len(parsed) if parsed else 0})",
                    file=sys.stderr,
                )
                for _ in batch:
                    results.append({"is_learning": True, "extracted_learning": None})

        except (subprocess.TimeoutExpired, OSError) as e:
            print(f"Warning: semantic analysis failed: {e}", file=sys.stderr)
            for _ in batch:
                results.append({"is_learning": True, "extracted_learning": None})

    return results


def _extract_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    """テキストから JSON 配列を抽出する。"""
    # まず直接パース
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # コードブロック内を探す
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # [ から ] までを探す
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def validate_corrections(
    corrections: List[Dict[str, Any]],
    model: str = "sonnet",
) -> List[Dict[str, Any]]:
    """semantic_analyze のラッパー。失敗時は regex フォールバック。

    Args:
        corrections: correction レコードのリスト。
        model: 使用するモデル名。

    Returns:
        各 correction に is_learning, extracted_learning を付与したリスト。
    """
    try:
        results = semantic_analyze(corrections, model=model)
        if len(results) == len(corrections):
            return results
    except Exception as e:
        print(f"Warning: validate_corrections failed: {e}", file=sys.stderr)

    # フォールバック: 全件を is_learning=True として返す
    return [{"is_learning": True, "extracted_learning": None} for _ in corrections]


def detect_contradictions(
    corrections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """矛盾する correction ペアを検出する（将来用スタブ）。

    Args:
        corrections: correction レコードのリスト。

    Returns:
        矛盾ペアのリスト。現在は空リストを返す。
    """
    return []
