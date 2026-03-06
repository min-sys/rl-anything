#!/usr/bin/env python3
"""LLM Hybrid 再分類ユーティリティ。

sessions.jsonl から "other" intent のプロンプトを抽出し、
Claude が再分類できる形式で stdout に出力する。
再分類結果を sessions.jsonl に書き戻す機能も提供する。

Usage:
    # Step 1: "other" プロンプトを抽出
    python3 reclassify.py extract --project <project_name>

    # Step 1b: 既分類セッションの残 "other" も抽出
    python3 reclassify.py extract --project <project_name> --include-reclassified

    # Step 2: 再分類結果を書き戻し
    python3 reclassify.py apply --input <reclassified.json>
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# hooks/common.py を import
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "hooks"))

import common

# 有効なカテゴリ一覧
VALID_CATEGORIES = list(common.PROMPT_CATEGORIES.keys()) + ["other", "skill-invocation", "conversation"]


def load_corrections_by_session() -> Dict[str, List[Dict[str, Any]]]:
    """corrections.jsonl を session_id ベースでグループ化して返す。"""
    corrections_file = common.DATA_DIR / "corrections.jsonl"
    if not corrections_file.exists():
        return {}
    by_session: Dict[str, List[Dict[str, Any]]] = {}
    for line in corrections_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            sid = record.get("session_id", "")
            if sid:
                by_session.setdefault(sid, []).append(record)
        except json.JSONDecodeError:
            continue
    return by_session


def get_project_session_ids(project_name: str) -> Set[str]:
    """sessions.jsonl から該当 project_name の session_id セットを返す。"""
    sessions_file = common.DATA_DIR / "sessions.jsonl"
    if not sessions_file.exists():
        return set()
    session_ids: Set[str] = set()
    for line in sessions_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            if record.get("project_name") == project_name:
                sid = record.get("session_id", "")
                if sid:
                    session_ids.add(sid)
        except json.JSONDecodeError:
            continue
    return session_ids


def extract_other_intents(
    project_name: Optional[str] = None,
    include_reclassified: bool = False,
) -> List[Dict[str, Any]]:
    """sessions.jsonl から "other" intent を持つプロンプトを抽出する。

    corrections.jsonl のデータがある場合、correction が紐付いたセッションの
    intent を優先的に抽出対象とする（結果の先頭に配置）。

    Args:
        project_name: フィルタ対象のプロジェクト名
        include_reclassified: True の場合、reclassified_intents が存在するセッションでも
            残 "other" を抽出する。reclassified_intents の値を参照し、
            存在しない場合は user_intents を参照する。

    Returns:
        各要素: {"session_id": str, "intent_index": int, "prompt": str}
    """
    sessions_file = common.DATA_DIR / "sessions.jsonl"
    if not sessions_file.exists():
        return []

    session_ids: Optional[Set[str]] = None
    if project_name:
        session_ids = get_project_session_ids(project_name)

    # corrections.jsonl との session_id ベース join
    corrections_by_session = load_corrections_by_session()
    correction_session_ids = set(corrections_by_session.keys())

    priority_results: List[Dict[str, Any]] = []  # correction 紐付き
    normal_results: List[Dict[str, Any]] = []    # 通常

    for line in sessions_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        sid = record.get("session_id", "")
        if session_ids is not None and sid not in session_ids:
            continue

        has_reclassified = bool(record.get("reclassified_intents"))

        if has_reclassified and not include_reclassified:
            continue

        if has_reclassified:
            intents_to_check = record.get("reclassified_intents", [])
        else:
            intents_to_check = record.get("user_intents", [])

        user_prompts = record.get("user_prompts", [])
        is_correction_session = sid in correction_session_ids

        for i, intent in enumerate(intents_to_check):
            if intent == "other":
                prompt = user_prompts[i] if i < len(user_prompts) else ""
                if prompt:
                    item = {
                        "session_id": sid,
                        "intent_index": i,
                        "prompt": prompt[:500],
                    }
                    if is_correction_session:
                        priority_results.append(item)
                    else:
                        normal_results.append(item)

    # correction 紐付きセッションを先頭に配置
    return priority_results + normal_results


def build_correction_context(session_id: str) -> Optional[str]:
    """セッションに紐付く correction 情報から LLM 分類用の context テキストを生成する。"""
    corrections_by_session = load_corrections_by_session()
    corrections = corrections_by_session.get(session_id, [])
    if not corrections:
        return None

    contexts = []
    for corr in corrections:
        skill = corr.get("last_skill", "不明")
        ctype = corr.get("correction_type", "")
        contexts.append(f"ユーザーは {skill} スキルに対して修正を行った（type: {ctype}）")

    return "。".join(contexts)


def apply_reclassification(reclassified: List[Dict[str, Any]]) -> Dict[str, Any]:
    """再分類結果を sessions.jsonl に書き戻す。

    Args:
        reclassified: [{"session_id": str, "intent_index": int, "category": str}, ...]

    Returns:
        {"updated_sessions": int, "updated_intents": int, "invalid_categories": int}
    """
    sessions_file = common.DATA_DIR / "sessions.jsonl"
    if not sessions_file.exists():
        return {"updated_sessions": 0, "updated_intents": 0, "invalid_categories": 0}

    # session_id -> {intent_index: category} のマップを構築
    reclass_map: Dict[str, Dict[int, str]] = {}
    invalid_count = 0
    for item in reclassified:
        category = item.get("category", "other")
        if category not in VALID_CATEGORIES:
            invalid_count += 1
            continue
        sid = item["session_id"]
        idx = item["intent_index"]
        reclass_map.setdefault(sid, {})[idx] = category

    # sessions.jsonl を読み込み、再分類結果を書き戻す
    lines = sessions_file.read_text(encoding="utf-8").splitlines()
    updated_lines: List[str] = []
    updated_sessions = 0
    updated_intents = 0

    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            updated_lines.append(line)
            continue

        sid = record.get("session_id", "")
        if sid in reclass_map:
            user_intents = record.get("user_intents", [])
            reclassified_intents = record.get("reclassified_intents", list(user_intents))

            for idx, category in reclass_map[sid].items():
                if idx < len(reclassified_intents):
                    reclassified_intents[idx] = category
                    updated_intents += 1

            record["reclassified_intents"] = reclassified_intents
            updated_sessions += 1

        updated_lines.append(json.dumps(record, ensure_ascii=False))

    sessions_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    return {
        "updated_sessions": updated_sessions,
        "updated_intents": updated_intents,
        "invalid_categories": invalid_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Hybrid 再分類ユーティリティ")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # extract サブコマンド
    extract_parser = subparsers.add_parser("extract", help='"other" プロンプトを抽出')
    extract_parser.add_argument(
        "--project",
        default=None,
        help="フィルタ対象のプロジェクト名",
    )
    extract_parser.add_argument(
        "--include-reclassified",
        action="store_true",
        help="reclassified_intents が存在するセッションでも残 other を抽出",
    )

    # apply サブコマンド
    apply_parser = subparsers.add_parser("apply", help="再分類結果を書き戻し")
    apply_parser.add_argument(
        "--input",
        required=True,
        help="再分類結果の JSON ファイルパス",
    )

    args = parser.parse_args()

    if args.command == "extract":
        others = extract_other_intents(
            project_name=args.project,
            include_reclassified=args.include_reclassified,
        )
        # correction context を付与
        for item in others:
            ctx = build_correction_context(item["session_id"])
            if ctx:
                item["correction_context"] = ctx
        output = {
            "total_other_prompts": len(others),
            "valid_categories": VALID_CATEGORIES,
            "prompts": others,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    elif args.command == "apply":
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: {args.input} not found", file=sys.stderr)
            sys.exit(1)

        reclassified = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(reclassified, dict):
            reclassified = reclassified.get("reclassified", [])

        result = apply_reclassification(reclassified)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
