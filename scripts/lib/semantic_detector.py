#!/usr/bin/env python3
"""LLM セマンティック検証モジュール。

claude-reflect の semantic_detector.py から移植。
corrections を `claude -p` でバッチ検証し、偽陽性を除去する。
"""
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# common.py の sanitize_message を利用
_hooks_dir = Path(__file__).resolve().parent.parent.parent / "hooks"
sys.path.insert(0, str(_hooks_dir))
from common import sanitize_message

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

        # バッチ用の簡易リストを作成（サニタイズ済み）
        batch_items = [
            {"index": i, "message": sanitize_message(c.get("message", ""))}
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
            elif parsed and 0 < len(parsed) < len(batch):
                # partial success: index フィールドでマッチングし、残りは is_learning=True
                print(
                    f"Warning: validate_corrections partial success "
                    f"(expected {len(batch)}, got {len(parsed)}), "
                    f"unmatched items default to is_learning=True",
                    file=sys.stderr,
                )
                matched = {item.get("index"): item for item in parsed if "index" in item}
                for i in range(len(batch)):
                    if i in matched:
                        results.append({
                            "is_learning": matched[i].get("is_learning", True),
                            "extracted_learning": matched[i].get("extracted_learning"),
                        })
                    else:
                        results.append({"is_learning": True, "extracted_learning": None})
            else:
                # 完全失敗（パース不能/空リスト/件数超過） → フォールバック（is_learning=True）
                print(
                    f"Warning: validate_corrections count mismatch "
                    f"(expected {len(batch)}, got {len(parsed) if parsed else 0}), "
                    f"defaulting to is_learning=True",
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
        print(f"Warning: validate_corrections failed, defaulting to is_learning=True", file=sys.stderr)

    # フォールバック: 全件を is_learning=True として返す（regex 結果尊重）
    return [{"is_learning": True, "extracted_learning": None} for _ in corrections]


CONTRADICTION_PROMPT = """以下の corrections リストで、矛盾するペアを見つけてください。
矛盾 = 同じ対象について相反する指示（例: 「日本語で応答して」と「英語で応答して」）

corrections:
{corrections_json}

矛盾ペアがあれば以下の JSON 配列で回答してください（なければ空配列 []）:
[{{"pair": [index_a, index_b], "reason": "矛盾の理由"}}]
"""


def detect_contradictions(
    corrections: List[Dict[str, Any]],
    model: str = "sonnet",
) -> List[Dict[str, Any]]:
    """corrections リスト内の矛盾するペアを検出する。

    `claude -p` を使用してセマンティックに矛盾を判定する。

    Args:
        corrections: correction レコードのリスト。各レコードに message フィールドが必要。
        model: 使用するモデル名。

    Returns:
        矛盾ペアのリスト。各要素は {"pair": [index_a, index_b], "reason": "矛盾理由"} 形式。
    """
    # 空入力ガード: 0件 or 1件以下は LLM 呼び出し不要
    if len(corrections) <= 1:
        return []

    # corrections の message を抽出してサニタイズ
    items = [
        {"index": i, "message": sanitize_message(c.get("message", ""))}
        for i, c in enumerate(corrections)
    ]

    prompt = CONTRADICTION_PROMPT.format(
        corrections_json=json.dumps(items, ensure_ascii=False, indent=2)
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

        if parsed is None:
            return []

        # 各エントリのバリデーション: pair と reason が存在するもののみ返す
        validated = []
        for item in parsed:
            pair = item.get("pair")
            reason = item.get("reason", "")
            if (
                isinstance(pair, list)
                and len(pair) == 2
                and all(isinstance(idx, int) for idx in pair)
            ):
                validated.append({"pair": pair, "reason": reason})

        return validated

    except (subprocess.TimeoutExpired, OSError) as e:
        print("Warning: contradiction detection failed", file=sys.stderr)
        return []
    except Exception as e:
        print("Warning: contradiction detection failed", file=sys.stderr)
        return []
