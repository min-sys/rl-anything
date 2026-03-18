#!/usr/bin/env python3
"""Pitfall 品質ゲート & ライフサイクル管理。

Candidate→New 2段階昇格、3層コンテキスト管理、
状態機械（Candidate→New→Active→Graduated→Pruned）、
回避回数ベース卒業判定を提供する。
"""
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import sys

_plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

from similarity import jaccard_coefficient, tokenize

# Cold 層自動アーカイブ定数
CAP_EXCEEDED_CONFIDENCE = 0.90
PREFLIGHT_MATURITY_RATIO = 0.50
# スクリプト化可能なカテゴリ
SCRIPTIFIABLE_CATEGORIES = frozenset({"action", "tool_use", "output"})

from skill_evolve import (
    ACTIVE_PITFALL_CAP,
    CANDIDATE_PROMOTION_COUNT,
    ERROR_FREQUENCY_THRESHOLD,
    GRADUATED_TTL_DAYS,
    GRADUATION_THRESHOLDS,
    HOT_TIER_MAX_ITEMS,
    INTEGRATION_JACCARD_THRESHOLD,
    PITFALL_MAX_LINES,
    RATIONALIZATION_MIN_CORRECTIONS,
    RATIONALIZATION_OUTCOME_WINDOW_DAYS,
    RATIONALIZATION_SKIP_KEYWORDS,
    ROOT_CAUSE_JACCARD_THRESHOLD,
    STALE_ESCALATION_MONTHS,
    STALE_KNOWLEDGE_MONTHS,
)

# --- Pitfall パース ---

_PITFALL_HEADER_RE = re.compile(r"^###\s+(.+)$", re.MULTILINE)
_FIELD_RE = re.compile(r"^-\s+\*\*(\w[\w-]*)\*\*:\s*(.+)$", re.MULTILINE)


def parse_pitfalls(content: str) -> Dict[str, List[Dict[str, Any]]]:
    """pitfalls.md をパースして3セクションに分離する。

    Returns:
        {"active": [...], "candidate": [...], "graduated": [...]}
        各要素: {"title": str, "fields": {key: value}, "raw": str}
    """
    sections: Dict[str, List[Dict[str, Any]]] = {
        "active": [],
        "candidate": [],
        "graduated": [],
    }

    current_section = "active"
    current_item: Optional[Dict[str, Any]] = None
    current_lines: List[str] = []

    for line in content.splitlines():
        # セクションヘッダ
        if re.match(r"^##\s+Active\s+Pitfalls", line, re.IGNORECASE):
            _flush_item(current_item, current_lines, sections, current_section)
            current_section = "active"
            current_item = None
            current_lines = []
            continue
        if re.match(r"^##\s+Candidate\s+Pitfalls", line, re.IGNORECASE):
            _flush_item(current_item, current_lines, sections, current_section)
            current_section = "candidate"
            current_item = None
            current_lines = []
            continue
        if re.match(r"^##\s+Graduated\s+Pitfalls", line, re.IGNORECASE):
            _flush_item(current_item, current_lines, sections, current_section)
            current_section = "graduated"
            current_item = None
            current_lines = []
            continue

        # 項目ヘッダ (### タイトル)
        m = _PITFALL_HEADER_RE.match(line)
        if m:
            _flush_item(current_item, current_lines, sections, current_section)
            current_item = {"title": m.group(1).strip(), "fields": {}}
            current_lines = [line]
            continue

        if current_item is not None:
            current_lines.append(line)
            fm = _FIELD_RE.match(line)
            if fm:
                current_item["fields"][fm.group(1)] = fm.group(2).strip()

    _flush_item(current_item, current_lines, sections, current_section)
    return sections


def _flush_item(
    item: Optional[Dict[str, Any]],
    lines: List[str],
    sections: Dict[str, List[Dict[str, Any]]],
    section: str,
) -> None:
    """現在のアイテムをセクションに追加する。"""
    if item is not None:
        item["raw"] = "\n".join(lines)
        sections[section].append(item)


def render_pitfalls(sections: Dict[str, List[Dict[str, Any]]]) -> str:
    """パース済み pitfalls を markdown に復元する。"""
    parts = ["# Pitfalls\n"]

    parts.append("\n## Active Pitfalls\n")
    for item in sections.get("active", []):
        parts.append("")
        parts.append(item["raw"])

    parts.append("\n## Candidate Pitfalls\n")
    for item in sections.get("candidate", []):
        parts.append("")
        parts.append(item["raw"])

    parts.append("\n## Graduated Pitfalls\n")
    for item in sections.get("graduated", []):
        parts.append("")
        parts.append(item["raw"])

    return "\n".join(parts) + "\n"


# --- 品質ゲート ---


def find_matching_candidate(
    candidates: List[Dict[str, Any]],
    root_cause: str,
) -> Optional[int]:
    """既存 Candidate から同一根本原因を Jaccard 類似度で検索する。

    Returns:
        マッチした Candidate のインデックス、またはNone
    """
    new_tokens = tokenize(root_cause)
    for i, candidate in enumerate(candidates):
        existing_cause = candidate["fields"].get("Root-cause", "")
        existing_tokens = tokenize(existing_cause)
        if jaccard_coefficient(new_tokens, existing_tokens) >= ROOT_CAUSE_JACCARD_THRESHOLD:
            return i
    return None


def record_pitfall(
    pitfalls_path: Path,
    title: str,
    root_cause: str,
    *,
    is_user_correction: bool = False,
) -> Dict[str, Any]:
    """新しい pitfall を記録する（品質ゲート適用）。

    Args:
        pitfalls_path: references/pitfalls.md のパス
        title: pitfall のタイトル
        root_cause: 根本原因（カテゴリ — 説明）
        is_user_correction: ユーザー訂正の場合 True（ゲートスキップ）

    Returns:
        {"action": str, "status": str, "title": str}
    """
    content = _safe_read(pitfalls_path)
    sections = parse_pitfalls(content)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if is_user_correction:
        # ゲートスキップ → 即 Active
        new_item = _make_pitfall_entry(title, root_cause, "Active", today)
        sections["active"].append(new_item)
        pitfalls_path.write_text(render_pitfalls(sections), encoding="utf-8")
        return {"action": "created_active", "status": "Active", "title": title}

    # 既存 Candidate とのマッチング
    match_idx = find_matching_candidate(sections["candidate"], root_cause)

    if match_idx is not None:
        # 同一根本原因2回目 → New に昇格
        candidate = sections["candidate"].pop(match_idx)
        promoted = _make_pitfall_entry(
            candidate["title"], root_cause, "New", today
        )
        sections["active"].append(promoted)  # New は active セクションに配置
        pitfalls_path.write_text(render_pitfalls(sections), encoding="utf-8")
        return {"action": "promoted_to_new", "status": "New", "title": candidate["title"]}

    # 初回 → Candidate
    new_item = _make_pitfall_entry(title, root_cause, "Candidate", today)
    new_item["fields"]["Occurrence-count"] = "1"
    sections["candidate"].append(new_item)
    pitfalls_path.write_text(render_pitfalls(sections), encoding="utf-8")
    return {"action": "created_candidate", "status": "Candidate", "title": title}


def promote_to_active(
    pitfalls_path: Path,
    title: str,
) -> bool:
    """New pitfall を Active に昇格する。"""
    content = _safe_read(pitfalls_path)
    sections = parse_pitfalls(content)

    for item in sections["active"]:
        if item["title"] == title and item["fields"].get("Status") == "New":
            item["fields"]["Status"] = "Active"
            item["raw"] = re.sub(
                r"\*\*Status\*\*:\s*New",
                "**Status**: Active",
                item["raw"],
            )
            pitfalls_path.write_text(render_pitfalls(sections), encoding="utf-8")
            return True
    return False


def graduate_pitfall(
    pitfalls_path: Path,
    title: str,
    integration_target: str = "",
) -> bool:
    """Active pitfall を Graduated に移行する。"""
    content = _safe_read(pitfalls_path)
    sections = parse_pitfalls(content)

    for i, item in enumerate(sections["active"]):
        if item["title"] == title and item["fields"].get("Status") == "Active":
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            graduated = _make_pitfall_entry(
                title,
                item["fields"].get("Root-cause", ""),
                "Graduated",
                today,
            )
            graduated["fields"]["Graduated-date"] = today
            if integration_target:
                graduated["fields"]["統合先"] = integration_target
            sections["active"].pop(i)
            sections["graduated"].append(graduated)
            pitfalls_path.write_text(render_pitfalls(sections), encoding="utf-8")
            return True
    return False


# --- 3層コンテキスト管理 ---


def get_hot_tier(sections: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Hot 層: Active + Pre-flight対応=Yes の上位5件を返す。"""
    hot = [
        item for item in sections.get("active", [])
        if item["fields"].get("Status") == "Active"
        and item["fields"].get("Pre-flight対応", "").lower().startswith("yes")
    ]
    # Last-seen 降順でソート
    hot.sort(key=lambda x: x["fields"].get("Last-seen", ""), reverse=True)
    return hot[:HOT_TIER_MAX_ITEMS]


def get_warm_tier(sections: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Warm 層: New + Hot 層に入らなかった Active を返す。"""
    hot_titles = {item["title"] for item in get_hot_tier(sections)}
    warm = [
        item for item in sections.get("active", [])
        if item["title"] not in hot_titles
    ]
    return warm


def get_cold_tier(sections: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Cold 層: Graduated + Candidate + New を返す。

    アーカイブ優先順: Graduated > Candidate > New
    """
    cold = list(sections.get("graduated", []))
    cold.extend(sections.get("candidate", []))
    # New は active セクション内で Status=New のもの
    for item in sections.get("active", []):
        if item["fields"].get("Status") == "New":
            cold.append(item)
    return cold


# --- 状態機械 ---


def _make_pitfall_entry(
    title: str,
    root_cause: str,
    status: str,
    date: str,
) -> Dict[str, Any]:
    """pitfall エントリを生成する。"""
    if status == "Candidate":
        raw = (
            f"### {title}\n"
            f"- **Status**: Candidate\n"
            f"- **First-seen**: {date}\n"
            f"- **Root-cause**: {root_cause}\n"
            f"- **Occurrence-count**: 1"
        )
    elif status == "Graduated":
        raw = (
            f"### {title}\n"
            f"- **Status**: Graduated\n"
            f"- **Graduated-date**: {date}\n"
            f"- **Root-cause**: {root_cause}"
        )
    else:
        raw = (
            f"### {title}\n"
            f"- **Status**: {status}\n"
            f"- **Last-seen**: {date}\n"
            f"- **Root-cause**: {root_cause}\n"
            f"- **Pre-flight対応**: No\n"
            f"- **Avoidance-count**: 0"
        )
    fields = {}
    for m in _FIELD_RE.finditer(raw):
        fields[m.group(1)] = m.group(2).strip()
    return {"title": title, "fields": fields, "raw": raw}


def _safe_read(pitfalls_path: Path) -> str:
    """pitfalls.md を安全に読み込む。破損時はバックアップ+再作成。"""
    if not pitfalls_path.exists():
        pitfalls_path.parent.mkdir(parents=True, exist_ok=True)
        _write_empty_template(pitfalls_path)
        return pitfalls_path.read_text(encoding="utf-8")

    content = pitfalls_path.read_text(encoding="utf-8")

    if not content.strip():
        _write_empty_template(pitfalls_path)
        return pitfalls_path.read_text(encoding="utf-8")

    # 最低限のセクション構造チェック
    has_active = bool(re.search(r"##\s+Active\s+Pitfalls", content, re.IGNORECASE))
    has_candidate = bool(re.search(r"##\s+Candidate\s+Pitfalls", content, re.IGNORECASE))

    if not has_active or not has_candidate:
        # 破損 → バックアップして再作成
        backup = pitfalls_path.with_suffix(".md.bak")
        shutil.copy2(pitfalls_path, backup)
        _write_empty_template(pitfalls_path)
        print(
            f"  [warn] pitfalls.md が破損していたため再作成しました。バックアップ: {backup}",
            file=sys.stderr,
        )
        return pitfalls_path.read_text(encoding="utf-8")

    return content


def _write_empty_template(pitfalls_path: Path) -> None:
    """空テンプレートで pitfalls.md を初期化する。"""
    template = (
        "# Pitfalls\n\n"
        "## Active Pitfalls\n\n"
        "_まだ記録がありません。_\n\n"
        "## Candidate Pitfalls\n\n"
        "_まだ記録がありません。_\n\n"
        "## Graduated Pitfalls\n\n"
        "_まだ記録がありません。_\n"
    )
    pitfalls_path.write_text(template, encoding="utf-8")


# --- Root-cause キーワード抽出 ---

# ストップワード（日本語助詞・英語冠詞等）
_STOP_WORDS = frozenset({
    "の", "は", "が", "を", "に", "で", "と", "も", "や", "へ", "から", "まで",
    "より", "など", "か", "て", "た", "だ", "な", "する", "ある", "いる", "れる",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "and", "or", "but", "not", "no", "it", "its", "this", "that",
})


def extract_root_cause_keywords(root_cause: str) -> Set[str]:
    """Root-cause 文字列からキーワード集合を抽出する。

    D2.1: 「—」（em dash）で分割し後半部分を単語分割、ストップワード除外。
    """
    parts = root_cause.split("—")
    text = parts[-1] if len(parts) >= 2 else root_cause
    tokens = tokenize(text)
    return tokens - _STOP_WORDS


def _split_sections_from_content(content: str) -> List[str]:
    """Markdown テキストを ## 見出し単位でセクション分割する。

    D2.2: YAML frontmatter を除外。
    """
    # frontmatter 除外
    stripped = content
    if stripped.startswith("---"):
        end = stripped.find("---", 3)
        if end != -1:
            stripped = stripped[end + 3:]

    sections: List[str] = []
    current: List[str] = []
    for line in stripped.splitlines():
        if re.match(r"^##\s+", line):
            if current:
                sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    return sections


# --- 統合済み判定 ---


def detect_integration(
    pitfall: Dict[str, Any],
    skill_dir: Path,
) -> Dict[str, Any]:
    """Active pitfall の SKILL.md / references/ との統合済み判定。

    Args:
        pitfall: parse_pitfalls() の要素
        skill_dir: スキルディレクトリ

    Returns:
        {"integration_detected": bool, "integration_target": str|None, "confidence": float}
    """
    root_cause = pitfall["fields"].get("Root-cause", "")
    keywords = extract_root_cause_keywords(root_cause)
    if not keywords:
        return {"integration_detected": False, "integration_target": None, "confidence": 0.0}

    # D2.2: SKILL.md 突合
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8")
        sections = _split_sections_from_content(content)
        for section_text in sections:
            section_tokens = tokenize(section_text) - _STOP_WORDS
            score = jaccard_coefficient(keywords, section_tokens)
            if score >= INTEGRATION_JACCARD_THRESHOLD:
                return {
                    "integration_detected": True,
                    "integration_target": "SKILL.md",
                    "confidence": round(score, 3),
                }

    # D2.3: references/ 突合（pitfalls.md 除外）
    refs_dir = skill_dir / "references"
    if refs_dir.exists():
        for ref_file in sorted(refs_dir.glob("*.md")):
            if ref_file.name == "pitfalls.md":
                continue
            ref_content = ref_file.read_text(encoding="utf-8")
            ref_sections = _split_sections_from_content(ref_content)
            for section_text in ref_sections:
                section_tokens = tokenize(section_text) - _STOP_WORDS
                score = jaccard_coefficient(keywords, section_tokens)
                if score >= INTEGRATION_JACCARD_THRESHOLD:
                    return {
                        "integration_detected": True,
                        "integration_target": f"references/{ref_file.name}",
                        "confidence": round(score, 3),
                    }

    return {"integration_detected": False, "integration_target": None, "confidence": 0.0}


# --- 自動検出 ---


def extract_pitfall_candidates(
    corrections: List[Dict[str, Any]],
    errors: Optional[List[Dict[str, Any]]] = None,
    skill_name: Optional[str] = None,
    existing_candidates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """corrections/errors から pitfall Candidate を自動抽出する。

    Args:
        corrections: corrections.jsonl のレコード群
        errors: errors.jsonl のレコード群（省略可）
        skill_name: フィルタ対象スキル名（省略時は全スキル）
        existing_candidates: 既存 Candidate リスト（重複排除用）

    Returns:
        {"candidates": [...], "occurrence_increments": [...], "skipped": int}
    """
    candidates: List[Dict[str, Any]] = []
    occurrence_increments: List[Dict[str, Any]] = []
    skipped = 0
    existing = existing_candidates or []

    # corrections からの抽出
    for rec in corrections:
        try:
            if not isinstance(rec, dict):
                skipped += 1
                continue
            ct = rec.get("correction_type", "")
            if ct not in ("stop", "iya"):
                continue
            last_skill = rec.get("last_skill")
            if not last_skill:  # null or empty string
                continue
            if skill_name and last_skill != skill_name:
                continue
            message = rec.get("message", "")
            if not message:
                continue

            # Root-cause 生成: correction_type — message の要約
            root_cause = f"{ct} — {message[:100]}"

            # D6: 既存 Candidate との重複チェック
            match_idx = find_matching_candidate(existing, root_cause)
            if match_idx is not None:
                # Occurrence-count += 1
                count = int(existing[match_idx]["fields"].get("Occurrence-count", "1") or "1")
                existing[match_idx]["fields"]["Occurrence-count"] = str(count + 1)
                occurrence_increments.append({
                    "title": existing[match_idx]["title"],
                    "new_count": count + 1,
                    "auto_promote": (count + 1) >= CANDIDATE_PROMOTION_COUNT,
                })
                continue

            # 新規候補との重複チェック
            dup = False
            for c in candidates:
                c_tokens = tokenize(c["root_cause"])
                new_tokens = tokenize(root_cause)
                if jaccard_coefficient(c_tokens, new_tokens) >= ROOT_CAUSE_JACCARD_THRESHOLD:
                    dup = True
                    break
            if dup:
                continue

            candidates.append({
                "title": f"Auto: {last_skill} — {ct}",
                "root_cause": root_cause,
                "skill_name": last_skill,
                "source": "corrections",
            })
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue

    # errors からの頻出パターン検出
    if errors:
        error_counter: Counter = Counter()
        error_samples: Dict[str, str] = {}
        for rec in errors:
            try:
                err_skill = rec.get("skill_name")
                if not err_skill:
                    continue
                if skill_name and err_skill != skill_name:
                    continue
                err_msg = rec.get("error_message", "")
                if not err_msg:
                    continue
                # 正規化: 先頭80文字をキーに
                key = f"{err_skill}:{err_msg[:80]}"
                error_counter[key] += 1
                error_samples[key] = err_msg
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue

        for key, count in error_counter.items():
            if count >= ERROR_FREQUENCY_THRESHOLD:
                parts = key.split(":", 1)
                s_name = parts[0]
                root_cause = f"error — {error_samples[key][:100]}"

                # 既存 Candidate・新規候補との重複チェック
                match_idx = find_matching_candidate(existing, root_cause)
                if match_idx is not None:
                    continue
                dup = False
                for c in candidates:
                    c_tokens = tokenize(c["root_cause"])
                    new_tokens = tokenize(root_cause)
                    if jaccard_coefficient(c_tokens, new_tokens) >= ROOT_CAUSE_JACCARD_THRESHOLD:
                        dup = True
                        break
                if dup:
                    continue

                candidates.append({
                    "title": f"Auto: {s_name} — frequent error",
                    "root_cause": root_cause,
                    "skill_name": s_name,
                    "source": "errors",
                    "error_count": count,
                })

    return {
        "candidates": candidates,
        "occurrence_increments": occurrence_increments,
        "skipped": skipped,
    }


# --- TTL アーカイブ ---


def detect_archive_candidates(
    sections: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """TTL ベースのアーカイブ候補を検出する。

    - Graduated: GRADUATED_TTL_DAYS 超過で候補
    - Active/New: STALE_KNOWLEDGE_MONTHS + STALE_ESCALATION_MONTHS (9ヶ月) で候補
    """
    candidates: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # Graduated TTL
    for item in sections.get("graduated", []):
        grad_date = item["fields"].get("Graduated-date", "")
        if not grad_date:
            continue
        try:
            grad_dt = datetime.strptime(grad_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_since = (now - grad_dt).days
            if days_since > GRADUATED_TTL_DAYS:
                candidates.append({
                    "title": item["title"],
                    "reason": f"卒業から{days_since}日経過",
                    "days_since": days_since,
                    "category": "graduated_ttl",
                })
        except ValueError:
            pass

    # Active/New stale escalation (9ヶ月)
    escalation_months = STALE_KNOWLEDGE_MONTHS + STALE_ESCALATION_MONTHS
    for item in sections.get("active", []):
        status = item["fields"].get("Status", "")
        if status not in ("Active", "New"):
            continue
        last_seen = item["fields"].get("Last-seen", "")
        if not last_seen:
            continue
        try:
            last_dt = datetime.strptime(last_seen, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            months_since = (now - last_dt).days / 30
            if months_since >= escalation_months:
                candidates.append({
                    "title": item["title"],
                    "reason": f"{round(months_since, 1)}ヶ月未更新 — 現在も有効か検証を推奨",
                    "months_since": round(months_since, 1),
                    "category": "stale_escalation",
                })
        except ValueError:
            pass

    return candidates


def execute_archive(
    pitfalls_path: Path,
    titles: List[str],
) -> Dict[str, Any]:
    """指定タイトルの pitfall を pitfalls.md から削除する。

    Returns:
        {"removed": [str], "not_found": [str]}
    """
    content = _safe_read(pitfalls_path)
    sections = parse_pitfalls(content)
    titles_set = set(titles)
    removed: List[str] = []
    not_found: List[str] = []

    for title in titles:
        found = False
        for section_key in ("graduated", "candidate", "active"):
            for i, item in enumerate(sections[section_key]):
                if item["title"] == title:
                    sections[section_key].pop(i)
                    removed.append(title)
                    found = True
                    break
            if found:
                break
        if not found:
            not_found.append(title)

    if removed:
        pitfalls_path.write_text(render_pitfalls(sections), encoding="utf-8")

    return {"removed": removed, "not_found": not_found}


# --- 行数ガード ---


def _compute_line_guard(
    sections: Dict[str, List[Dict[str, Any]]],
    content: str,
) -> Dict[str, Any]:
    """行数ガード: PITFALL_MAX_LINES 超過時に Cold 層から削除候補を生成。

    Returns:
        {"line_count": int, "line_guard_candidates": [...], "warning": str|None}
    """
    line_count = len(content.splitlines())
    if line_count <= PITFALL_MAX_LINES:
        return {"line_count": line_count, "line_guard_candidates": [], "warning": None}

    excess = line_count - PITFALL_MAX_LINES

    # Cold 層を古い順にソート
    cold_items: List[Dict[str, Any]] = []

    # Graduated: Graduated-date 古い順
    for item in sections.get("graduated", []):
        cold_items.append({
            "title": item["title"],
            "sort_key": item["fields"].get("Graduated-date", "9999-99-99"),
            "category": "graduated",
            "raw_lines": len(item.get("raw", "").splitlines()),
        })

    # Candidate: First-seen 古い順
    for item in sections.get("candidate", []):
        cold_items.append({
            "title": item["title"],
            "sort_key": item["fields"].get("First-seen", "9999-99-99"),
            "category": "candidate",
            "raw_lines": len(item.get("raw", "").splitlines()),
        })

    cold_items.sort(key=lambda x: x["sort_key"])

    candidates: List[Dict[str, Any]] = []
    removed_lines = 0
    for ci in cold_items:
        if removed_lines >= excess:
            break
        candidates.append({
            "title": ci["title"],
            "category": ci["category"],
            "lines": ci["raw_lines"],
        })
        removed_lines += ci["raw_lines"]

    warning = None
    if removed_lines < excess:
        warning = "Active/New 項目の手動レビューが必要"

    return {
        "line_count": line_count,
        "line_guard_candidates": candidates,
        "warning": warning,
    }


# --- Pre-flight スクリプト提案 ---


_CATEGORY_TEMPLATE_MAP = {
    "action": "action.sh",
    "tool_use": "tool_use.sh",
    "output": "output.sh",
}


def suggest_preflight_script(
    pitfall: Dict[str, Any],
    templates_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Pre-flight 対応 pitfall にテンプレートパスを提案する。

    Returns:
        {"pitfall_title": str, "category": str, "template_path": str} or None
    """
    if pitfall["fields"].get("Pre-flight対応", "").lower() != "yes":
        return None
    if pitfall["fields"].get("Status") != "Active":
        return None

    root_cause = pitfall["fields"].get("Root-cause", "")
    category = root_cause.split("—")[0].strip().lower() if "—" in root_cause else "generic"

    tmpl_dir = templates_dir or (_plugin_root.parent / "skills" / "evolve" / "templates" / "preflight")
    template_name = _CATEGORY_TEMPLATE_MAP.get(category)
    if template_name is None:
        template_name = "generic.sh"
        category = "generic"

    template_path = tmpl_dir / template_name

    # フォールバック: ファイルが存在しない場合
    if not template_path.exists():
        template_path = tmpl_dir / "generic.sh"
        template_name = "generic.sh"
        category = "generic"

    return {
        "pitfall_title": pitfall["title"],
        "category": category,
        "template_path": str(template_path),
    }


# --- 合理化防止テーブル (superpowers-knowledge-integration) ---


def detect_rationalization_patterns(
    corrections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """corrections からスキップ/バイパスの合理化パターンを検出する。

    Returns:
        [{"excuse": str, "corrections": [dict], "sample_count": int}]
    """
    keyword_set = {kw.lower() for kw in RATIONALIZATION_SKIP_KEYWORDS}
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for rec in corrections:
        if not isinstance(rec, dict):
            continue
        message = rec.get("message", "")
        if not message:
            continue
        msg_lower = message.lower()
        matched = [kw for kw in keyword_set if kw in msg_lower]
        if not matched:
            continue
        # グルーピングキー: 最初にマッチしたキーワード
        key = sorted(matched, key=lambda k: msg_lower.index(k))[0]
        excuse = message[:120]
        if excuse not in groups:
            groups[excuse] = []
        groups[excuse].append(rec)

    return [
        {"excuse": excuse, "corrections": recs, "sample_count": len(recs)}
        for excuse, recs in groups.items()
        if len(recs) >= 1
    ]


def generate_rationalization_table(
    corrections: List[Dict[str, Any]],
    usage: Optional[List[Dict[str, Any]]] = None,
    errors: Optional[List[Dict[str, Any]]] = None,
    *,
    existing_pitfalls: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """合理化防止テーブルを生成する。

    corrections のスキップパターンをテレメトリと突合し、
    「言い訳 vs 実際の結果」テーブルを生成する。

    Args:
        corrections: corrections.jsonl のレコード群
        usage: usage.jsonl のレコード群
        errors: errors.jsonl のレコード群
        existing_pitfalls: 既存 pitfall セクション（重複チェック用）

    Returns:
        {"data_insufficient": bool, "table": [...], "enriched_pitfalls": [...]}
    """
    patterns = detect_rationalization_patterns(corrections)
    total_skip_corrections = sum(p["sample_count"] for p in patterns)

    if total_skip_corrections < RATIONALIZATION_MIN_CORRECTIONS:
        return {"data_insufficient": True, "table": [], "enriched_pitfalls": []}

    error_list = errors or []
    table: List[Dict[str, Any]] = []
    enriched_pitfalls: List[Dict[str, Any]] = []

    for pattern in patterns:
        excuse = pattern["excuse"]
        sample_count = pattern["sample_count"]

        # テレメトリ突合: パターン発生時期の前後でエラー率を算出
        outcome_error_rate: Optional[float] = None
        telemetry_source = "corrections_only"

        if error_list and pattern["corrections"]:
            # corrections のタイムスタンプ前後 OUTCOME_WINDOW_DAYS のエラーを集計
            post_errors = 0
            for corr in pattern["corrections"]:
                corr_ts = corr.get("timestamp", "")
                if not corr_ts:
                    continue
                try:
                    corr_dt = datetime.fromisoformat(corr_ts.replace("Z", "+00:00"))
                    window_end = corr_dt + timedelta(days=RATIONALIZATION_OUTCOME_WINDOW_DAYS)
                    for err in error_list:
                        err_ts = err.get("timestamp", "")
                        if not err_ts:
                            continue
                        try:
                            err_dt = datetime.fromisoformat(err_ts.replace("Z", "+00:00"))
                            if corr_dt <= err_dt <= window_end:
                                post_errors += 1
                        except (ValueError, TypeError):
                            continue
                except (ValueError, TypeError):
                    continue

            if sample_count > 0:
                outcome_error_rate = round(post_errors / sample_count, 2)
                telemetry_source = "usage+errors"

        entry = {
            "excuse": excuse,
            "outcome_error_rate": outcome_error_rate,
            "sample_count": sample_count,
            "telemetry_source": telemetry_source,
        }
        table.append(entry)

        # 既存 pitfall との Jaccard 重複チェック → エンリッチ
        if existing_pitfalls:
            excuse_tokens = tokenize(excuse)
            for section_key in ("active", "candidate"):
                for pitfall in existing_pitfalls.get(section_key, []):
                    root_cause = pitfall["fields"].get("Root-cause", "")
                    pitfall_tokens = tokenize(root_cause)
                    if excuse_tokens and pitfall_tokens:
                        score = jaccard_coefficient(excuse_tokens, pitfall_tokens)
                        if score >= ROOT_CAUSE_JACCARD_THRESHOLD:
                            enriched_pitfalls.append({
                                "pitfall_title": pitfall["title"],
                                "matched_excuse": excuse,
                                "jaccard_score": round(score, 3),
                                "telemetry_data": entry,
                            })

    # sample_count で降順ソート
    table.sort(key=lambda x: x["sample_count"], reverse=True)

    return {
        "data_insufficient": False,
        "table": table,
        "enriched_pitfalls": enriched_pitfalls,
    }


# --- Pitfall 剪定 (pitfall_hygiene) ---


def pitfall_hygiene(
    project_dir: Optional[Path] = None,
    *,
    frequency_scores: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """自己進化済みスキルの pitfall を剪定する。

    Args:
        project_dir: プロジェクトディレクトリ
        frequency_scores: スキル名→実行頻度スコアのマップ（省略時はデフォルト閾値）

    Returns:
        {"skills_checked": int, "graduation_candidates": [...],
         "graduation_proposals": [...], "archive_candidates": [...],
         "codegen_proposals": [...], "line_count": int,
         "cap_exceeded": [...], "stale_warnings": [...],
         "cross_skill_analysis": {...}}
    """
    from skill_evolve import is_self_evolved_skill

    _audit_scripts = _plugin_root / "skills" / "audit" / "scripts"
    if str(_audit_scripts) not in sys.path:
        sys.path.insert(0, str(_audit_scripts))
    from audit import find_artifacts

    proj = project_dir or Path.cwd()
    artifacts = find_artifacts(proj)

    freq_scores = frequency_scores or {}
    graduation_candidates: List[Dict[str, Any]] = []
    graduation_proposals: List[Dict[str, Any]] = []
    all_archive_candidates: List[Dict[str, Any]] = []
    codegen_proposals: List[Dict[str, Any]] = []
    cap_exceeded: List[Dict[str, Any]] = []
    stale_warnings: List[Dict[str, Any]] = []
    all_root_causes: Dict[str, List[str]] = {}  # category → [skill_names]
    hygiene_issues: List[Dict[str, Any]] = []
    preflight_candidates: List[Dict[str, Any]] = []
    skills_checked = 0
    total_line_count = 0

    for skill_path in artifacts.get("skills", []):
        skill_dir = skill_path.parent
        skill_name = skill_dir.name

        if not is_self_evolved_skill(skill_dir):
            continue

        skills_checked += 1
        pitfalls_path = skill_dir / "references" / "pitfalls.md"
        if not pitfalls_path.exists():
            continue

        content = pitfalls_path.read_text(encoding="utf-8")
        sections = parse_pitfalls(content)

        # 卒業判定
        freq = freq_scores.get(skill_name, 1)
        threshold = GRADUATION_THRESHOLDS.get(freq, 3)

        for item in sections.get("active", []):
            if item["fields"].get("Status") != "Active":
                continue

            avoidance = int(item["fields"].get("Avoidance-count", "0") or "0")
            if avoidance >= threshold:
                graduation_candidates.append({
                    "skill_name": skill_name,
                    "pitfall_title": item["title"],
                    "avoidance_count": avoidance,
                    "threshold": threshold,
                })

            # 統合済み判定 → graduation_proposals
            integration = detect_integration(item, skill_dir)
            if integration["integration_detected"]:
                graduation_proposals.append({
                    "skill_name": skill_name,
                    "pitfall_title": item["title"],
                    "integration_target": integration["integration_target"],
                    "confidence": integration["confidence"],
                })

            # Stale Knowledge ガード
            last_seen = item["fields"].get("Last-seen", "")
            if last_seen:
                try:
                    last_dt = datetime.strptime(last_seen, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                    months_ago = (datetime.now(timezone.utc) - last_dt).days / 30
                    if months_ago >= STALE_KNOWLEDGE_MONTHS:
                        stale_warnings.append({
                            "skill_name": skill_name,
                            "pitfall_title": item["title"],
                            "last_seen": last_seen,
                            "months_since": round(months_ago, 1),
                        })
                except ValueError:
                    pass

            # Pre-flight スクリプト提案
            proposal = suggest_preflight_script(item)
            if proposal:
                codegen_proposals.append(proposal)

        # Pre-flight スクリプト化候補検出
        for item in sections.get("active", []):
            if item["fields"].get("Status") != "Active":
                continue
            avoidance = int(item["fields"].get("Avoidance-count", "0") or "0")
            root_cause = item["fields"].get("Root-cause", "")
            category = root_cause.split("—")[0].strip().lower() if "—" in root_cause else ""
            if (
                category in SCRIPTIFIABLE_CATEGORIES
                and item["fields"].get("Pre-flight対応", "").lower().startswith("yes")
                and avoidance >= threshold * PREFLIGHT_MATURITY_RATIO
            ):
                template = suggest_preflight_script(item)
                preflight_candidates.append({
                    "pitfall_id": item["title"],
                    "skill_name": skill_name,
                    "category": category,
                    "avoidance_count": avoidance,
                    "template": template.get("template_path", "") if template else "",
                })

        # Active 上限チェック
        active_count = sum(
            1 for item in sections.get("active", [])
            if item["fields"].get("Status") == "Active"
        )
        cold_count = len(get_cold_tier(sections))
        if active_count > ACTIVE_PITFALL_CAP:
            cap_exceeded.append({
                "skill_name": skill_name,
                "active_count": active_count,
                "cap": ACTIVE_PITFALL_CAP,
                "cold_count": cold_count,
            })
            hygiene_issues.append({
                "type": "cap_exceeded",
                "file": str(pitfalls_path),
                "detail": {
                    "skill_name": skill_name,
                    "active_count": active_count,
                    "cap": ACTIVE_PITFALL_CAP,
                    "cold_count": cold_count,
                },
                "source": "pitfall_hygiene",
            })

        # TTL アーカイブ候補
        archive_cands = detect_archive_candidates(sections)
        for ac in archive_cands:
            ac["skill_name"] = skill_name
        all_archive_candidates.extend(archive_cands)

        # 行数ガード
        line_guard = _compute_line_guard(sections, content)
        total_line_count += line_guard["line_count"]
        if line_guard["line_guard_candidates"]:
            for lgc in line_guard["line_guard_candidates"]:
                lgc["skill_name"] = skill_name
            all_archive_candidates.extend(line_guard["line_guard_candidates"])
            hygiene_issues.append({
                "type": "line_guard",
                "file": str(pitfalls_path),
                "detail": {
                    "skill_name": skill_name,
                    "line_count": line_guard["line_count"],
                    "max_lines": PITFALL_MAX_LINES,
                    "cold_count": cold_count,
                },
                "source": "pitfall_hygiene",
            })

        # 横断分析: 根本原因カテゴリ集計
        for item in sections.get("active", []):
            cause = item["fields"].get("Root-cause", "")
            category = cause.split("—")[0].strip() if "—" in cause else cause.split("-")[0].strip()
            category = category.lower().strip()
            if category:
                if category not in all_root_causes:
                    all_root_causes[category] = []
                if skill_name not in all_root_causes[category]:
                    all_root_causes[category].append(skill_name)

    # 横断分析: 3スキル以上で同じカテゴリ
    cross_skill = {
        cat: skills
        for cat, skills in all_root_causes.items()
        if len(skills) >= 3
    }

    # preflight_candidates → issue 化
    for pc in preflight_candidates:
        hygiene_issues.append({
            "type": "preflight_scriptification",
            "file": "",  # pitfall 単位なのでファイル不要
            "detail": {
                "pitfall_title": pc["pitfall_id"],
                "skill_name": pc["skill_name"],
                "category": pc["category"],
                "avoidance_count": pc["avoidance_count"],
                "template_path": pc.get("template", ""),
            },
            "source": "pitfall_hygiene",
        })

    # 合理化防止テーブル生成 (superpowers-knowledge-integration)
    rationalization_table: Dict[str, Any] = {"data_insufficient": True, "table": [], "enriched_pitfalls": []}
    try:
        import telemetry_query
        corrections = telemetry_query.query_corrections(
            project=proj.name if proj else None,
        )
        errors_data = telemetry_query.query_errors(
            project=proj.name if proj else None,
        )
        # 全スキルの pitfall セクションを集約
        all_pitfall_sections: Dict[str, List[Dict[str, Any]]] = {"active": [], "candidate": [], "graduated": []}
        for skill_path in artifacts.get("skills", []):
            pf_path = skill_path.parent / "references" / "pitfalls.md"
            if pf_path.exists():
                pf_content = pf_path.read_text(encoding="utf-8")
                pf_sections = parse_pitfalls(pf_content)
                for key in all_pitfall_sections:
                    all_pitfall_sections[key].extend(pf_sections.get(key, []))

        rationalization_table = generate_rationalization_table(
            corrections,
            errors=errors_data,
            existing_pitfalls=all_pitfall_sections,
        )
    except Exception:
        pass  # テレメトリ取得失敗時は data_insufficient のまま

    return {
        "skills_checked": skills_checked,
        "graduation_candidates": sorted(
            graduation_candidates,
            key=lambda x: x["avoidance_count"],
            reverse=True,
        ),
        "graduation_proposals": graduation_proposals,
        "archive_candidates": all_archive_candidates,
        "codegen_proposals": codegen_proposals,
        "line_count": total_line_count,
        "cap_exceeded": cap_exceeded,
        "stale_warnings": stale_warnings,
        "cross_skill_analysis": cross_skill if cross_skill else {"status": "問題なし"},
        "issues": hygiene_issues,
        "preflight_candidates": preflight_candidates,
        "rationalization_table": rationalization_table,
    }
