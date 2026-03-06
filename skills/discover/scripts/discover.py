#!/usr/bin/env python3
"""パターン発見スクリプト。

usage.jsonl、errors.jsonl、sessions.jsonl、history.jsonl から
繰り返しパターンを検出し、スキル/ルール候補を生成する。
"""
import argparse
import json
import sys
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
MISSED_SKILL_THRESHOLD = 2  # missed skill 検出閾値（セッション数）

# 構造的制約は共通モジュールから取得
_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
from agent_classifier import classify_agent_type
from line_limit import MAX_RULE_LINES, MAX_SKILL_LINES
from skill_triggers import extract_skill_triggers, normalize_skill_name

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
    """抑制リスト（2回 reject されたパターン）を読み込む。

    type: "merge" エントリは除外し、type 未指定エントリのみを返す。
    """
    records = load_jsonl(SUPPRESSION_FILE)
    return set(r.get("pattern", "") for r in records if r.get("type") != "merge")


def load_merge_suppression() -> set:
    """merge suppression リスト（type: "merge" エントリ）を読み込み、ペアキーの set を返す。"""
    records = load_jsonl(SUPPRESSION_FILE)
    return set(r.get("pattern", "") for r in records if r.get("type") == "merge")


def add_merge_suppression(skill_a: str, skill_b: str) -> None:
    """merge suppression エントリを追加する。スキル名をソートし :: 結合で正規化。

    書き込み失敗時は stderr にエラー出力し、例外を送出しない。
    """
    key = "::".join(sorted([skill_a, skill_b]))
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SUPPRESSION_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"pattern": key, "type": "merge"}, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[rl-anything] merge suppression write failed: {e}", file=sys.stderr)


def add_to_suppression_list(pattern: str) -> None:
    """抑制リストにパターンを追加する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SUPPRESSION_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"pattern": pattern}, ensure_ascii=False) + "\n")


def _load_classify_usage_skill():
    """audit.py の _is_plugin_skill と classify_usage_skill を遅延インポートで取得する。

    Returns:
        _is_plugin_skill 関数（classify_usage_skill + _is_openspec_skill の併用）
    """
    import sys as _sys
    _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    _audit_scripts = _plugin_root / "skills" / "audit" / "scripts"
    if str(_audit_scripts) not in _sys.path:
        _sys.path.insert(0, str(_audit_scripts))
    from audit import _is_plugin_skill, classify_usage_skill
    return _is_plugin_skill, classify_usage_skill


def detect_behavior_patterns(
    threshold: int = BEHAVIOR_THRESHOLD,
    *,
    project_root: Optional[Path] = None,
    include_unknown: bool = False,
) -> List[Dict[str, Any]]:
    """繰り返し行動パターンの検出（usage + sessions、5+閾値）。

    parent_skill の有無で contextualized / ad-hoc / unknown を分類し、
    ad-hoc パターンのみをスキル候補として提案する。
    処理順序:
    1. プラグインスキルはメインランキングから除外し、plugin_summary に集約
    2. 組み込み Agent は agent_usage_summary に分離
    3. カスタム Agent はメインランキングに残留
    """
    from telemetry_query import query_usage

    project_name = project_root.name if project_root else None
    usage = query_usage(
        project=project_name,
        include_unknown=include_unknown,
        usage_file=DATA_DIR / "usage.jsonl",
    )
    _is_plugin, _classify = _load_classify_usage_skill()

    # ad-hoc レコードのみカウント（contextualized/unknown を除外）
    ad_hoc_counter: Counter = Counter()
    all_counter: Counter = Counter()
    plugin_counter: Counter = Counter()  # プラグイン別集計
    for rec in usage:
        skill = rec.get("skill_name", "")
        if not skill:
            continue
        all_counter[skill] += 1

        # (1) プラグインスキルは別集計
        if _is_plugin(skill):
            plugin_name = _classify(skill) or "openspec(legacy)"
            plugin_counter[plugin_name] += 1
            continue

        parent_skill = rec.get("parent_skill")
        source = rec.get("source", "")

        # backfill データ（parent_skill なし + source=backfill）は unknown として除外
        if parent_skill is None and source == "backfill":
            continue
        # contextualized（parent_skill あり）は除外
        if parent_skill is not None:
            continue
        # ad-hoc（parent_skill なし、backfill でない）のみカウント
        ad_hoc_counter[skill] += 1

    suppressed = load_suppression_list()
    patterns = []
    builtin_agent_counter: Counter = Counter()
    builtin_agent_prompts: Dict[str, List[str]] = defaultdict(list)

    for skill, ad_hoc_count in ad_hoc_counter.most_common():
        if ad_hoc_count < threshold or skill in suppressed:
            continue

        # (2) Agent:XX パターンの分類
        if skill.startswith("Agent:"):
            agent_name = skill[len("Agent:"):]
            agent_type = classify_agent_type(agent_name, project_root=project_root)

            prompts = [
                r.get("prompt", "") for r in usage
                if r.get("skill_name") == skill
                and r.get("prompt")
                and r.get("parent_skill") is None
                and r.get("source", "") != "backfill"
            ]

            if agent_type == "builtin":
                # 組み込み Agent → builtin_agent_counter に分離
                builtin_agent_counter[skill] = ad_hoc_count
                builtin_agent_prompts[skill] = prompts
                continue

            # (3) カスタム Agent → メインランキングに残留
            pattern: Dict[str, Any] = {
                "type": "behavior",
                "pattern": skill,
                "count": ad_hoc_count,
                "total_count": all_counter.get(skill, 0),
                "suggestion": "skill_candidate",
                "agent_type": agent_type,
            }
            subcategories = _classify_agent_prompts(prompts)
            if subcategories:
                pattern["subcategories"] = subcategories
            patterns.append(pattern)
            continue

        # 非 Agent パターン
        pattern = {
            "type": "behavior",
            "pattern": skill,
            "count": ad_hoc_count,
            "total_count": all_counter.get(skill, 0),
            "suggestion": "skill_candidate",
        }
        patterns.append(pattern)

    # プラグイン利用サマリを末尾に付加
    if plugin_counter:
        patterns.append({
            "type": "plugin_summary",
            "pattern": "plugin_usage",
            "count": sum(plugin_counter.values()),
            "suggestion": "info_only",
            "plugin_breakdown": dict(plugin_counter.most_common()),
        })

    # 組み込み Agent 利用サマリを末尾に付加
    if builtin_agent_counter:
        agent_breakdown: Dict[str, Any] = {}
        for agent_skill, count in builtin_agent_counter.most_common():
            entry: Dict[str, Any] = {"count": count}
            subcategories = _classify_agent_prompts(builtin_agent_prompts.get(agent_skill, []))
            if subcategories:
                entry["subcategories"] = subcategories
            agent_breakdown[agent_skill] = entry

        patterns.append({
            "type": "agent_usage_summary",
            "pattern": "builtin_agent_usage",
            "count": sum(builtin_agent_counter.values()),
            "suggestion": "info_only",
            "agent_breakdown": agent_breakdown,
        })

    return patterns


def _classify_agent_prompts(prompts: List[str]) -> List[Dict[str, Any]]:
    """Agent の prompt リストをキーワードベースで簡易分類する。

    common.PROMPT_CATEGORIES / common.classify_prompt() を利用。
    """
    # hooks/common.py をインポート
    import sys as _sys
    _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    if str(_plugin_root / "hooks") not in _sys.path:
        _sys.path.insert(0, str(_plugin_root / "hooks"))
    import common as _common

    category_counts: Counter = Counter()
    category_examples: Dict[str, str] = {}

    for prompt in prompts:
        cat = _common.classify_prompt(prompt)
        category_counts[cat] += 1
        if cat != "other" and cat not in category_examples:
            category_examples[cat] = prompt[:120]

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


def detect_missed_skills(
    threshold: int = MISSED_SKILL_THRESHOLD,
    *,
    project_root: Optional[Path] = None,
    include_unknown: bool = False,
) -> Dict[str, Any]:
    """スキルのトリガーワードにマッチしたがスキルが使われなかったセッションを検出する。

    Returns:
        {"missed": [...], "message": str or None}
        missed: [{"skill": str, "triggers_matched": [str], "session_count": int}, ...]
    """
    from telemetry_query import query_sessions, query_usage

    # CLAUDE.md からスキルトリガーを取得
    skill_triggers = extract_skill_triggers(project_root=project_root)
    if not skill_triggers:
        return {"missed": [], "message": "No CLAUDE.md found, skipping missed skill detection"}

    project_name = project_root.name if project_root else None

    # sessions.jsonl からセッションデータを取得
    sessions_file = DATA_DIR / "sessions.jsonl"
    sessions = query_sessions(
        project=project_name,
        include_unknown=include_unknown,
        sessions_file=sessions_file,
    )
    if not sessions:
        if not sessions_file.exists():
            return {"missed": [], "message": "No sessions.jsonl found (run backfill first), skipping missed skill detection"}
        return {"missed": [], "message": None}

    # usage.jsonl からスキル使用実績を取得
    usage = query_usage(
        project=project_name,
        include_unknown=include_unknown,
        usage_file=DATA_DIR / "usage.jsonl",
    )

    # session_id ごとに使用されたスキル名を集約
    used_skills_by_session: Dict[str, set] = defaultdict(set)
    for rec in usage:
        sid = rec.get("session_id", "")
        skill = rec.get("skill_name", "")
        if sid and skill:
            used_skills_by_session[sid].add(normalize_skill_name(skill))

    # セッションごとにトリガーマッチ → スキル使用チェック
    # skill -> {triggers_matched: set, sessions: set}
    missed_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"triggers_matched": set(), "sessions": set()})

    for session in sessions:
        sid = session.get("session_id", "")
        user_prompts = session.get("user_prompts", [])
        if not sid or not user_prompts:
            continue

        prompts_text = " ".join(user_prompts).lower()
        used_in_session = used_skills_by_session.get(sid, set())

        for skill_entry in skill_triggers:
            skill_name = skill_entry["skill"]
            if skill_name in used_in_session:
                continue

            for trigger in skill_entry["triggers"]:
                if trigger.lower() in prompts_text:
                    missed_map[skill_name]["triggers_matched"].add(trigger)
                    missed_map[skill_name]["sessions"].add(sid)

    # 閾値フィルタリング
    missed = []
    for skill, data in sorted(missed_map.items(), key=lambda x: len(x[1]["sessions"]), reverse=True):
        session_count = len(data["sessions"])
        if session_count >= threshold:
            missed.append({
                "skill": skill,
                "triggers_matched": sorted(data["triggers_matched"]),
                "session_count": session_count,
            })

    return {"missed": missed, "message": None}


def detect_error_patterns(
    threshold: int = ERROR_THRESHOLD,
    *,
    project_root: Optional[Path] = None,
    include_unknown: bool = False,
) -> List[Dict[str, Any]]:
    """繰り返しエラーパターンの検出（errors、3+閾値）。"""
    from telemetry_query import query_errors

    project_name = project_root.name if project_root else None
    errors = query_errors(
        project=project_name,
        include_unknown=include_unknown,
        errors_file=DATA_DIR / "errors.jsonl",
    )
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
    """スコープ配置の判断（global / project / plugin）。

    カスタム Agent は agent_type フィールドから判定する。
    """
    # カスタム Agent: agent_type フィールドで判定
    agent_type = pattern.get("agent_type")
    if agent_type == "custom_global":
        return "global"
    if agent_type == "custom_project":
        return "project"

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
    """corrections.jsonl からの修正データ取り込み（オプション）。未生成時はスキップ。"""
    corrections_file = DATA_DIR / "corrections.jsonl"

    if not corrections_file.exists():
        return []

    return load_jsonl(corrections_file)


# ---------- session-scan ----------

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
SESSION_SCAN_THRESHOLD = 5


def _get_backfill_parse_transcript():
    """backfill の parse_transcript を遅延インポートで取得する。"""
    import sys as _sys
    _plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    _backfill_scripts = _plugin_root / "skills" / "backfill" / "scripts"
    if str(_backfill_scripts) not in _sys.path:
        _sys.path.insert(0, str(_backfill_scripts))
    from backfill import parse_transcript
    return parse_transcript


def detect_session_patterns(
    threshold: int = SESSION_SCAN_THRESHOLD,
    projects_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """セッション JSONL のユーザーメッセージテキストを直接分析し、繰り返しパターンを検出する。

    Args:
        threshold: パターン検出閾値（デフォルト5回以上）
        projects_dir: プロジェクトディレクトリのルート（テスト用）

    Returns:
        検出されたパターンのリスト
    """
    if projects_dir is None:
        projects_dir = CLAUDE_PROJECTS_DIR

    if not projects_dir.is_dir():
        return []

    parse_transcript = _get_backfill_parse_transcript()

    # 全セッションからユーザーメッセージを収集
    prompt_counter: Counter = Counter()

    for session_file in projects_dir.glob("*/sessions/*.jsonl"):
        try:
            result = parse_transcript(session_file)
        except Exception as e:
            print(
                f"[rl-anything:discover] session parse error: {session_file.name}: {e}",
                file=sys.stderr,
            )
            continue

        if result.session_meta and result.session_meta.get("user_prompts"):
            for prompt in result.session_meta["user_prompts"]:
                # 短すぎるプロンプトや空文字列はスキップ
                prompt = prompt.strip()
                if len(prompt) >= 5:
                    prompt_counter[prompt] += 1

    suppressed = load_suppression_list()
    patterns = []
    for prompt_text, count in prompt_counter.most_common():
        if count >= threshold and prompt_text not in suppressed:
            patterns.append({
                "type": "session_text",
                "pattern": prompt_text,
                "count": count,
                "suggestion": "skill_candidate",
            })
    return patterns


# ---------- recommended artifacts ----------

RECOMMENDED_ARTIFACTS = [
    {
        "id": "no-defer-use-subagent",
        "type": "rule",
        "path": Path.home() / ".claude" / "rules" / "no-defer-use-subagent.md",
        "description": "先送り禁止 — background subagent 即時委譲ルール",
        "hook_path": Path.home() / ".claude" / "hooks" / "detect-deferred-task.py",
        "hook_description": "Stop hook: 先送り表現検出 → 会話続行強制",
    },
]


def detect_recommended_artifacts() -> List[Dict[str, Any]]:
    """推奨ルール/hook が未導入かチェックし、未導入のものを返す。"""
    missing = []
    for artifact in RECOMMENDED_ARTIFACTS:
        rule_exists = artifact["path"].exists()
        hook_path = artifact.get("hook_path")
        hook_exists = hook_path.exists() if hook_path else True

        if rule_exists and hook_exists:
            continue

        entry: Dict[str, Any] = {
            "id": artifact["id"],
            "description": artifact["description"],
            "missing": [],
        }
        if not rule_exists:
            entry["missing"].append({"type": "rule", "path": str(artifact["path"])})
        if not hook_exists and hook_path:
            entry["missing"].append({
                "type": "hook",
                "path": str(hook_path),
                "description": artifact.get("hook_description", ""),
            })
        missing.append(entry)
    return missing


def run_discover(
    session_scan: bool = False,
    *,
    project_root: Optional[Path] = None,
    include_unknown: bool = False,
    tool_usage: bool = False,
) -> Dict[str, Any]:
    """Discover を実行して候補を返す。"""
    behavior = detect_behavior_patterns(
        project_root=project_root, include_unknown=include_unknown,
    )
    errors = detect_error_patterns(
        project_root=project_root, include_unknown=include_unknown,
    )
    rejections = detect_rejection_patterns()
    reflect_data = load_claude_reflect_data()

    # missed skill 検出
    missed_result = detect_missed_skills(
        project_root=project_root,
        include_unknown=include_unknown,
    )

    result: Dict[str, Any] = {
        "behavior_patterns": behavior,
        "error_patterns": errors,
        "rejection_patterns": rejections,
        "reflect_data_count": len(reflect_data),
    }

    # missed skill opportunities をレポートに含める
    if missed_result["missed"]:
        result["missed_skill_opportunities"] = missed_result["missed"]
    if missed_result["message"]:
        result["missed_skill_message"] = missed_result["message"]

    if session_scan:
        session_patterns = detect_session_patterns()
        result["session_patterns"] = session_patterns
    else:
        session_patterns = []

    # スコープ判断
    all_patterns = behavior + errors + rejections + session_patterns
    for p in all_patterns:
        p["scope"] = determine_scope(p)

    result["total_candidates"] = len(all_patterns)

    if tool_usage:
        from tool_usage_analyzer import analyze_tool_usage
        tool_result = analyze_tool_usage(project_root=project_root)
        if tool_result["total_tool_calls"] > 0:
            result["tool_usage_patterns"] = tool_result

    # 推奨アーティファクト未導入チェック
    recommended_missing = detect_recommended_artifacts()
    if recommended_missing:
        result["recommended_artifacts"] = recommended_missing

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="パターン発見スクリプト")
    parser.add_argument(
        "--session-scan",
        action="store_true",
        help="セッション JSONL のユーザーメッセージテキストを直接分析して繰り返しパターンを検出する",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="プロジェクトディレクトリ（指定時はそのプロジェクトのレコードのみ集計）",
    )
    parser.add_argument(
        "--include-unknown",
        action="store_true",
        help="project が null のレコードも集計に含める",
    )
    parser.add_argument(
        "--tool-usage",
        action="store_true",
        help="セッション JSONL からツール利用パターンを分析する",
    )
    args = parser.parse_args()

    project_root = Path(args.project_dir) if args.project_dir else None
    result = run_discover(
        session_scan=args.session_scan,
        project_root=project_root,
        include_unknown=args.include_unknown,
        tool_usage=args.tool_usage,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
