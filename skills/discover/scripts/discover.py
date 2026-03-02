#!/usr/bin/env python3
"""パターン発見スクリプト。

usage.jsonl、errors.jsonl、sessions.jsonl、history.jsonl から
繰り返しパターンを検出し、スキル/ルール候補を生成する。
"""
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path.home() / ".claude" / "rl-anything"
HISTORY_DIR = (
    Path(__file__).parent.parent
    / "skills"
    / "genetic-prompt-optimizer"
    / "scripts"
    / "generations"
)

# 閾値
BEHAVIOR_THRESHOLD = 5   # 行動パターン検出閾値
ERROR_THRESHOLD = 3       # エラーパターン検出閾値
REJECTION_THRESHOLD = 3   # 却下理由検出閾値

# 構造的制約
MAX_SKILL_LINES = 500
MAX_RULE_LINES = 3

# Discover 振動防止用抑制リスト
SUPPRESSION_FILE = DATA_DIR / "discover-suppression.jsonl"


def load_jsonl(filepath: Path) -> List[Dict[str, Any]]:
    """JSONL ファイルを読み込む。"""
    if not filepath.exists():
        return []
    records = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def load_suppression_list() -> set:
    """抑制リスト（2回 reject されたパターン）を読み込む。"""
    records = load_jsonl(SUPPRESSION_FILE)
    return set(r.get("pattern", "") for r in records)


def add_to_suppression_list(pattern: str) -> None:
    """抑制リストにパターンを追加する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SUPPRESSION_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"pattern": pattern}, ensure_ascii=False) + "\n")


def detect_behavior_patterns(threshold: int = BEHAVIOR_THRESHOLD) -> List[Dict[str, Any]]:
    """繰り返し行動パターンの検出（usage + sessions、5+閾値）。"""
    usage = load_jsonl(DATA_DIR / "usage.jsonl")
    counter: Counter = Counter()
    for rec in usage:
        skill = rec.get("skill_name", "")
        if skill:
            counter[skill] += 1

    suppressed = load_suppression_list()
    patterns = []
    for skill, count in counter.most_common():
        if count >= threshold and skill not in suppressed:
            pattern: Dict[str, Any] = {
                "type": "behavior",
                "pattern": skill,
                "count": count,
                "suggestion": "skill_candidate",
            }
            # Agent パターンの場合、prompt を分析してサブカテゴリを付与
            if skill.startswith("Agent:"):
                prompts = [
                    r.get("prompt", "") for r in usage
                    if r.get("skill_name") == skill and r.get("prompt")
                ]
                subcategories = _classify_agent_prompts(prompts)
                if subcategories:
                    pattern["subcategories"] = subcategories
            patterns.append(pattern)
    return patterns


# Agent prompt を簡易分類するキーワードマップ
_PROMPT_CATEGORIES = {
    "spec-review": ["spec", "requirement", "MUST", "quality check", "review.*spec"],
    "code-exploration": ["structure", "explore", "codebase", "directory", "find.*file"],
    "research": ["research", "best practice", "latest", "how to", "pattern"],
    "code-review": ["review.*code", "review.*change", "review.*impl", "alignment", "verify"],
    "implementation": ["implement", "create", "build", "write.*code", "add.*feature"],
}


def _classify_agent_prompts(prompts: List[str]) -> List[Dict[str, Any]]:
    """Agent の prompt リストをキーワードベースで簡易分類する。"""
    import re

    category_counts: Counter = Counter()
    category_examples: Dict[str, str] = {}

    for prompt in prompts:
        prompt_lower = prompt.lower()
        matched = False
        for category, keywords in _PROMPT_CATEGORIES.items():
            for kw in keywords:
                if re.search(kw, prompt_lower):
                    category_counts[category] += 1
                    if category not in category_examples:
                        category_examples[category] = prompt[:120]
                    matched = True
                    break
            if matched:
                break
        if not matched:
            category_counts["other"] += 1

    results = []
    for cat, count in category_counts.most_common():
        entry: Dict[str, Any] = {
            "category": cat,
            "count": count,
        }
        if cat in category_examples:
            entry["example"] = category_examples[cat]
        results.append(entry)
    return results


def detect_error_patterns(threshold: int = ERROR_THRESHOLD) -> List[Dict[str, Any]]:
    """繰り返しエラーパターンの検出（errors、3+閾値）。"""
    errors = load_jsonl(DATA_DIR / "errors.jsonl")
    counter: Counter = Counter()
    for rec in errors:
        error = rec.get("error", "")[:200]
        if error:
            counter[error] += 1

    suppressed = load_suppression_list()
    patterns = []
    for error, count in counter.most_common():
        if count >= threshold and error not in suppressed:
            patterns.append({
                "type": "error",
                "pattern": error,
                "count": count,
                "suggestion": "rule_candidate",
            })
    return patterns


def detect_rejection_patterns(threshold: int = REJECTION_THRESHOLD) -> List[Dict[str, Any]]:
    """繰り返し却下理由の検出（rejection_reason、3+閾値）。"""
    history_file = HISTORY_DIR / "history.jsonl"
    records = load_jsonl(history_file)

    counter: Counter = Counter()
    for rec in records:
        reason = rec.get("rejection_reason")
        if reason:
            counter[reason] += 1

    suppressed = load_suppression_list()
    patterns = []
    for reason, count in counter.most_common():
        if count >= threshold and reason not in suppressed:
            patterns.append({
                "type": "rejection",
                "pattern": reason,
                "count": count,
                "suggestion": "rule_candidate",
            })
    return patterns


def determine_scope(pattern: Dict[str, Any]) -> str:
    """スコープ配置の判断（global / project / plugin）。"""
    p = pattern.get("pattern", "").lower()

    # global 配置の兆候
    global_keywords = ["git", "commit", "pr", "pull request", "test", "lint", "claude", "format"]
    if any(kw in p for kw in global_keywords):
        return "global"

    # project 配置の兆候
    project_keywords = ["react", "next", "vue", "django", "rails", "prisma", "docker"]
    if any(kw in p for kw in project_keywords):
        return "project"

    return "project"  # デフォルト


def validate_skill_content(content: str) -> bool:
    """スキル候補の構造バリデーション（MUST 500行以下）。"""
    lines = content.count("\n") + 1
    return lines <= MAX_SKILL_LINES


def validate_rule_content(content: str) -> bool:
    """ルール候補の構造バリデーション（MUST 3行以内）。"""
    lines = content.count("\n") + 1
    return lines <= MAX_RULE_LINES


def load_claude_reflect_data() -> List[Dict[str, Any]]:
    """claude-reflect データの取り込み（オプション）。未インストール時はスキップ。"""
    reflect_dir = Path.home() / ".claude" / "claude-reflect"
    learnings_file = reflect_dir / "learnings-queue.jsonl"

    if not learnings_file.exists():
        return []

    return load_jsonl(learnings_file)


def run_discover() -> Dict[str, Any]:
    """Discover を実行して候補を返す。"""
    behavior = detect_behavior_patterns()
    errors = detect_error_patterns()
    rejections = detect_rejection_patterns()
    reflect_data = load_claude_reflect_data()

    # スコープ判断
    all_patterns = behavior + errors + rejections
    for p in all_patterns:
        p["scope"] = determine_scope(p)

    result = {
        "behavior_patterns": behavior,
        "error_patterns": errors,
        "rejection_patterns": rejections,
        "reflect_data_count": len(reflect_data),
        "total_candidates": len(all_patterns),
    }

    return result


if __name__ == "__main__":
    result = run_discover()
    print(json.dumps(result, ensure_ascii=False, indent=2))
