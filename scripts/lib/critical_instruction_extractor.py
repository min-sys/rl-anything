"""Critical Instruction Extractor — スキル指示の遵守保証サイクルのコアモジュール。

Phase 1 (EXTRACT): extract_critical_lines() — MUST/禁止等のキーワードで critical 行を抽出
Phase 1 (REPHRASE): rephrase_to_calm() — 攻撃的表現を calm/direct に LLM 変換
Phase 3 (DETECT): detect_instruction_violation() — corrections と instructions の突合

LLM Judge 呼び出しは本モジュールにカプセル化（discover.py は関数を呼ぶだけ）。

Related: issue #39
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# ── 定数 ────────────────────────────────────────────────

CRITICAL_KEYWORDS = [
    "MUST", "must not", "必須", "禁止", "絶対に", "決して",
    "never", "always", "required", "forbidden", "mandatory",
    "必ず", "してはいけない", "厳禁",
]

CRITICAL_SECTION_HEADERS = [
    "Important", "Critical", "注意", "Warning", "禁止事項",
    "Must", "Required", "必須事項",
]

# 対立動詞ペア（矛盾検出用）— キーはタプル (en, ja)
OPPOSING_VERBS: Dict[Tuple[str, ...], Tuple[str, ...]] = {
    ("move", "移動"): ("delete", "削除"),
    ("add", "追加"): ("remove", "除去"),
    ("create", "作成"): ("delete", "削除"),
    ("keep", "保持"): ("remove", "除去"),
    ("archive", "アーカイブ"): ("delete", "削除"),
    ("update", "更新"): ("skip", "スキップ"),
    ("copy", "コピー"): ("delete", "削除"),
}

# 同義動詞ペア（誤検出防止用）— キーはタプル、値は同義語タプル
SYNONYM_VERBS: Dict[Tuple[str, ...], Tuple[str, ...]] = {
    ("move", "移動"): ("transfer", "移管", "migrate"),
    ("delete", "削除"): ("remove", "除去", "drop"),
    ("create", "作成"): ("generate", "生成", "add", "追加"),
    ("update", "更新"): ("modify", "変更", "edit", "編集"),
}

REPHRASE_CONFIDENCE_MIN = 0.80
REPHRASE_HUMAN_REVIEW_MIN = 0.60
LLM_JUDGE_TIMEOUT_SECONDS = 30
KEYWORD_OVERLAP_FALLBACK_MIN = 3


# ── データクラス ────────────────────────────────────────

@dataclass
class CriticalInstruction:
    """スキルから抽出された critical 指示。"""
    original: str
    rephrased: str = ""
    language: str = "en"
    source_line: int = 0


@dataclass
class Violation:
    """検出された指示違反。"""
    instruction: CriticalInstruction
    correction_message: str
    match_type: str = ""  # "opposing_verb" | "llm_judge" | "keyword_overlap"
    confidence: float = 0.0
    reason: str = ""
    needs_review: bool = False


# ── Phase 1: EXTRACT ────────────────────────────────────


def _detect_language(text: str) -> str:
    """テキストの主要言語を推定する。"""
    ja_chars = sum(1 for c in text if ord(c) > 0x3000)
    return "ja" if ja_chars > len(text) * 0.1 else "en"


def _build_keyword_pattern() -> re.Pattern:
    """CRITICAL_KEYWORDS から正規表現パターンを構築する。"""
    escaped = [re.escape(kw) for kw in CRITICAL_KEYWORDS]
    return re.compile(r"(?i)\b(?:" + "|".join(escaped) + r")\b|" +
                      "|".join(re.escape(kw) for kw in CRITICAL_KEYWORDS if any(ord(c) > 0x3000 for c in kw)))


def _build_section_pattern() -> re.Pattern:
    """CRITICAL_SECTION_HEADERS からセクション見出しパターンを構築する。"""
    escaped = [re.escape(h) for h in CRITICAL_SECTION_HEADERS]
    return re.compile(r"^#{1,3}\s+.*(?:" + "|".join(escaped) + r")", re.IGNORECASE | re.MULTILINE)


_KEYWORD_RE = _build_keyword_pattern()
_SECTION_RE = _build_section_pattern()
_CONDITIONAL_RE = re.compile(
    r"(?:の場合は?必ず|場合は?絶対|if.*(?:must|always|never)|when.*(?:must|always|never))",
    re.IGNORECASE,
)


def extract_critical_lines(skill_content: str) -> List[CriticalInstruction]:
    """スキルコンテンツから critical 指示を抽出する。

    3つのソースから検出:
    1. CRITICAL_KEYWORDS を含む行
    2. CRITICAL_SECTION_HEADERS 配下の行
    3. 条件付き指示パターン
    """
    if not skill_content.strip():
        return []

    results: List[CriticalInstruction] = []
    seen: Set[str] = set()
    lines = skill_content.split("\n")

    # 1. キーワードマッチング
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _KEYWORD_RE.search(stripped) and stripped not in seen:
            seen.add(stripped)
            results.append(CriticalInstruction(
                original=stripped,
                language=_detect_language(stripped),
                source_line=i,
            ))

    # 2. セクション見出し配下の行
    in_critical_section = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.match(r"^#{1,3}\s+", stripped):
            in_critical_section = bool(_SECTION_RE.match(stripped))
            continue
        if in_critical_section and stripped and not stripped.startswith("#"):
            if stripped not in seen:
                seen.add(stripped)
                results.append(CriticalInstruction(
                    original=stripped,
                    language=_detect_language(stripped),
                    source_line=i,
                ))

    # 3. 条件付き指示パターン
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if _CONDITIONAL_RE.search(stripped) and stripped not in seen:
            seen.add(stripped)
            results.append(CriticalInstruction(
                original=stripped,
                language=_detect_language(stripped),
                source_line=i,
            ))

    return results


# ── Phase 1: REPHRASE ──────────────────────────────────


def rephrase_to_calm(
    instruction: str, *, language: str = "en"
) -> Tuple[str, float, str]:
    """攻撃的表現を calm/direct に変換する。

    Returns:
        (rephrased_text, confidence, action)
        action: "auto" | "human_review" | "reject"
    """
    lang_hint = "日本語" if language == "ja" else "English"
    prompt = (
        f"以下の指示を、攻撃的な表現（MUST/NEVER/禁止等）を使わずに、"
        f"穏やかで直接的な表現にリフレーズしてください。"
        f"元の意味を正確に保持してください。{lang_hint}で回答してください。\n\n"
        f"元の指示: {instruction}\n\n"
        f'JSON形式で回答: {{"rephrased": "...", "confidence": 0.0-1.0}}'
    )
    try:
        result = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True, text=True, timeout=LLM_JUDGE_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            # JSON を抽出
            output = result.stdout.strip()
            json_match = re.search(r"\{[^}]+\}", output)
            if json_match:
                data = json.loads(json_match.group())
                rephrased = data.get("rephrased", instruction)
                confidence = float(data.get("confidence", 0.0))

                if confidence >= REPHRASE_CONFIDENCE_MIN:
                    return rephrased, confidence, "auto"
                elif confidence >= REPHRASE_HUMAN_REVIEW_MIN:
                    return rephrased, confidence, "human_review"
                else:
                    return instruction, confidence, "reject"
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, OSError):
        pass

    return instruction, 0.0, "reject"


# ── Phase 3: DETECT ────────────────────────────────────


def _flatten_verb_group(group: Tuple[str, ...]) -> Set[str]:
    """動詞グループをフラットな小文字セットに変換する。"""
    return {v.lower() for v in group}


def _get_all_synonyms(verb: str) -> Set[str]:
    """指定動詞の全同義語を返す。"""
    verb_lower = verb.lower()
    result = {verb_lower}
    for key_group, syn_group in SYNONYM_VERBS.items():
        all_in_group = _flatten_verb_group(key_group) | _flatten_verb_group(syn_group)
        if verb_lower in all_in_group:
            result |= all_in_group
    return result


def _extract_verbs_from_text(text: str) -> Set[str]:
    """テキストから OPPOSING_VERBS / SYNONYM_VERBS に含まれる動詞を抽出する。"""
    all_verbs: Set[str] = set()
    for key_group, val_group in OPPOSING_VERBS.items():
        all_verbs |= _flatten_verb_group(key_group)
        all_verbs |= _flatten_verb_group(val_group)
    for key_group, syn_group in SYNONYM_VERBS.items():
        all_verbs |= _flatten_verb_group(key_group)
        all_verbs |= _flatten_verb_group(syn_group)

    text_lower = text.lower()
    return {v for v in all_verbs if v in text_lower}


def _check_opposing_verbs(
    instruction_verbs: Set[str], correction_verbs: Set[str]
) -> Optional[Tuple[str, str]]:
    """対立動詞ペアが instruction と correction の間に存在するか確認する。"""
    for key_group, val_group in OPPOSING_VERBS.items():
        key_set = _flatten_verb_group(key_group)
        val_set = _flatten_verb_group(val_group)
        # instruction に key があり correction に val がある（またはその逆）
        if (instruction_verbs & key_set and correction_verbs & val_set):
            return (
                next(iter(instruction_verbs & key_set)),
                next(iter(correction_verbs & val_set)),
            )
        if (instruction_verbs & val_set and correction_verbs & key_set):
            return (
                next(iter(instruction_verbs & val_set)),
                next(iter(correction_verbs & key_set)),
            )
    return None


def _are_synonyms(verb1: str, verb2: str) -> bool:
    """2つの動詞が同義かどうか判定する。"""
    syns1 = _get_all_synonyms(verb1)
    return verb2.lower() in syns1


def _call_llm_judge(
    correction_message: str, instruction_text: str
) -> Optional[Dict[str, Any]]:
    """LLM Judge で違反判定する。失敗時は None を返す。"""
    prompt = (
        f"以下のユーザー修正が、スキル指示への違反を示しているか判定してください。\n\n"
        f"スキル指示: {instruction_text}\n"
        f"ユーザー修正: {correction_message}\n\n"
        f"direct scoring: 違反していれば is_violation=true、していなければ false。\n"
        f"Chain of Thought: まず理由を考え、次に判定を出してください。\n\n"
        f'JSON形式で回答: {{"is_violation": true/false, "confidence": 0.0-1.0, "reason": "..."}}'
    )
    try:
        result = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True, text=True, timeout=LLM_JUDGE_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            json_match = re.search(r"\{[^}]+\}", output)
            if json_match:
                return json.loads(json_match.group())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, OSError):
        pass
    return None


def _keyword_overlap(text1: str, text2: str) -> int:
    """2つのテキストの共通キーワード数を返す（小文字化、3文字以上）。"""
    words1 = {w.lower() for w in re.findall(r"\w{3,}", text1)}
    words2 = {w.lower() for w in re.findall(r"\w{3,}", text2)}
    return len(words1 & words2)


def detect_instruction_violation(
    correction: Dict[str, Any],
    instructions: List[CriticalInstruction],
) -> Optional[Violation]:
    """correction が instructions のいずれかに違反しているか検出する。

    2段階マッチング:
    1. 対立動詞検出 (deterministic) → 確定違反
    2. LLM Judge (direct scoring + CoT) → 違反/非違反
       失敗時: keyword overlap >= KEYWORD_OVERLAP_FALLBACK_MIN → 「要確認」
    """
    message = correction.get("message", "")
    if not message or not instructions:
        return None

    correction_verbs = _extract_verbs_from_text(message)

    for instr in instructions:
        instruction_text = instr.original
        instruction_verbs = _extract_verbs_from_text(instruction_text)

        # Stage 1: 対立動詞検出
        opposing = _check_opposing_verbs(instruction_verbs, correction_verbs)
        if opposing:
            # 同義動詞チェック（false positive 防止）
            v1, v2 = opposing
            if not _are_synonyms(v1, v2):
                return Violation(
                    instruction=instr,
                    correction_message=message,
                    match_type="opposing_verb",
                    confidence=0.95,
                    reason=f"対立動詞検出: instruction={v1}, correction={v2}",
                )

        # Stage 2: LLM Judge
        judge_result = _call_llm_judge(message, instruction_text)
        if judge_result is not None:
            if judge_result.get("is_violation"):
                return Violation(
                    instruction=instr,
                    correction_message=message,
                    match_type="llm_judge",
                    confidence=judge_result.get("confidence", 0.0),
                    reason=judge_result.get("reason", ""),
                )
            # LLM が非違反と判定 → この instruction についてはスキップ
            continue

        # Stage 2 fallback: keyword overlap
        overlap = _keyword_overlap(message, instruction_text)
        if overlap >= KEYWORD_OVERLAP_FALLBACK_MIN:
            return Violation(
                instruction=instr,
                correction_message=message,
                match_type="keyword_overlap",
                confidence=0.50,
                reason=f"keyword overlap={overlap} (LLM Judge 失敗時 fallback)",
                needs_review=True,
            )

    return None
