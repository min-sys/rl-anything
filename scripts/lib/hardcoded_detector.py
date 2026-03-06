#!/usr/bin/env python3
"""ハードコード値検出モジュール。

skill/rule の Markdown ファイル内に含まれる環境固有のリテラル値
（AWS ARN, Slack ID, API キー, サービス URL, 長数値 ID）を
正規表現 + ヒューリスティクスで検出する。
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------- 検出パターン ----------

PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "api_key",
        "regex": re.compile(r"(xoxb-|xapp-|sk-|AKIA)[A-Za-z0-9\-_]{8,}"),
        "confidence": 0.85,
    },
    {
        "name": "aws_arn",
        "regex": re.compile(r"arn:aws:[a-z0-9\-]+:[a-z0-9\-]*:\d{12}:\S+"),
        "confidence": 0.75,
    },
    {
        "name": "slack_id",
        "regex": re.compile(r"\b[ABCUW](?=[A-Z0-9]*\d)[A-Z0-9]{10,}\b"),
        "confidence": 0.65,
    },
    {
        "name": "service_url",
        "regex": re.compile(
            r"https?://(?:[a-z0-9\-]+\.)*(?:slack|amazonaws|github)\.com/\S+"
        ),
        "confidence": 0.55,
    },
    {
        "name": "numeric_id",
        "regex": re.compile(r"\b\d{12,}\b"),
        "confidence": 0.45,
    },
]

# ---------- 許容パターン（false positive 除外） ----------

_SUPPRESSION_COMMENT = re.compile(r"<!--\s*rl-allow:\s*hardcoded\s*-->")

_PLACEHOLDER_PATTERNS = [
    re.compile(r"\$\{[^}]+\}"),              # ${VAR}
    re.compile(r"\{[a-z_][a-z0-9_]*\}"),     # {var} テンプレート変数
    re.compile(r"<[A-Z_]+>"),                # <YOUR_APP_ID>
    re.compile(r"\bYOUR_\w+", re.IGNORECASE),  # YOUR_*
    re.compile(r"\bEXAMPLE\b", re.IGNORECASE),
]

# ダミー値: 連番、ゼロ埋め
_DUMMY_PATTERNS = [
    re.compile(r"^[A-Z]?0123456789\d*$"),    # A0123456789
    re.compile(r"^0{6,}$"),                   # 000000000000
    re.compile(r"x{3,}", re.IGNORECASE),      # xxx
]

_SAFE_URL_PARTS = ["example.com", "localhost", "127.0.0.1"]

# バージョン番号
_VERSION_PATTERN = re.compile(
    r"(?:^|[v=:\s])(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)\b"
)

# 算術式（数値の前後に演算子がある）
_ARITHMETIC_PATTERN = re.compile(r"\d+\s*[+\-*/]{1,2}\s*\d+")

# タイムスタンプ (10桁 Unix epoch 風, ISO 8601 日付隣接)
_TIMESTAMP_PATTERN = re.compile(r"\b\d{10}\b")
_ISO_DATE_ADJACENT = re.compile(r"\d{4}-\d{2}-\d{2}")

# version: キー行の数値
_VERSION_KEY_LINE = re.compile(r"^\s*version\s*[:=]", re.IGNORECASE)


def _is_placeholder(matched: str, line: str) -> bool:
    """マッチした文字列がプレースホルダかどうか判定する。"""
    for pat in _PLACEHOLDER_PATTERNS:
        # マッチした文字列自体にプレースホルダが含まれる場合
        if pat.search(matched):
            return True
        # ${VAR} は行全体を除外
        if pat.pattern == r"\$\{[^}]+\}" and pat.search(line):
            return True
    return False


def _is_dummy(matched: str) -> bool:
    """マッチした文字列がダミー値かどうか判定する。"""
    return any(pat.search(matched) for pat in _DUMMY_PATTERNS)


def _is_safe_url(matched: str) -> bool:
    """URL が安全なもの（localhost, example.com 等）かどうか判定する。"""
    return any(part in matched.lower() for part in _SAFE_URL_PARTS)


def _is_version_number(matched: str, line: str) -> bool:
    """マッチした文字列がバージョン番号かどうか判定する。"""
    if _VERSION_PATTERN.search(line):
        return True
    if _VERSION_KEY_LINE.search(line):
        return True
    return False


def _is_arithmetic(line: str) -> bool:
    """行が算術式を含むかどうか判定する。"""
    return bool(_ARITHMETIC_PATTERN.search(line))


def _is_timestamp(matched: str, line: str) -> bool:
    """マッチした文字列がタイムスタンプかどうか判定する。"""
    if len(matched) == 10 and matched.isdigit() and _TIMESTAMP_PATTERN.match(matched):
        return True
    if _ISO_DATE_ADJACENT.search(line):
        return True
    return False


def _should_exclude(
    matched: str,
    line: str,
    pattern_name: str,
    extra_allowlist: Optional[List[str]] = None,
) -> bool:
    """マッチが許容パターンに該当するかどうか判定する。"""
    # インライン抑制コメント
    if _SUPPRESSION_COMMENT.search(line):
        return True

    # プレースホルダ
    if _is_placeholder(matched, line):
        return True

    # ダミー値（URL は部分一致で誤判定しやすいのでスキップ）
    if pattern_name != "service_url" and _is_dummy(matched):
        return True

    # URL の安全チェック
    if pattern_name == "service_url" and _is_safe_url(matched):
        return True

    # バージョン番号
    if pattern_name == "numeric_id" and _is_version_number(matched, line):
        return True

    # 算術式
    if pattern_name == "numeric_id" and _is_arithmetic(line):
        return True

    # タイムスタンプ
    if pattern_name == "numeric_id" and _is_timestamp(matched, line):
        return True

    # ユーザー指定の許容パターン
    if extra_allowlist:
        for allow_pat in extra_allowlist:
            if re.search(allow_pat, matched):
                return True

    return False


# ---------- confidence_score ----------

_CONFIDENCE_TABLE: Dict[str, float] = {
    "api_key": 0.85,
    "aws_arn": 0.75,
    "slack_id": 0.65,
    "service_url": 0.55,
    "numeric_id": 0.45,
}


def compute_confidence_score(pattern_type: str) -> float:
    """pattern_type ごとのデフォルト confidence_score を返す。"""
    return _CONFIDENCE_TABLE.get(pattern_type, 0.5)


# ---------- メイン検出関数 ----------

def detect_hardcoded_values(
    file_path: str,
    extra_patterns: Optional[List[Dict[str, Any]]] = None,
    extra_allowlist: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """ファイル内のハードコード値を検出する。

    Args:
        file_path: 走査対象ファイルのパス
        extra_patterns: 追加パターン [{"name": str, "regex": str, "confidence": float}]
        extra_allowlist: 追加許容パターン ["regex_pattern", ...]

    Returns:
        検出結果リスト。各要素は
        {"line": int, "matched": str, "pattern_type": str, "context": str, "confidence_score": float}
    """
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    # バイナリファイルチェック (null バイトを含む場合)
    if "\x00" in content:
        return []

    all_patterns = list(PATTERNS)
    if extra_patterns:
        for ep in extra_patterns:
            regex = ep["regex"] if isinstance(ep["regex"], re.Pattern) else re.compile(ep["regex"])
            all_patterns.append({
                "name": ep["name"],
                "regex": regex,
                "confidence": ep.get("confidence", 0.5),
            })

    results: List[Dict[str, Any]] = []
    seen: set = set()  # (line_num, matched) で重複排除

    for line_num, line in enumerate(content.splitlines(), start=1):
        # インライン抑制コメントチェック（行全体をスキップ）
        if _SUPPRESSION_COMMENT.search(line):
            continue

        for pat in all_patterns:
            for m in pat["regex"].finditer(line):
                matched = m.group(0)
                key = (line_num, matched)
                if key in seen:
                    continue

                if _should_exclude(matched, line, pat["name"], extra_allowlist):
                    continue

                seen.add(key)
                confidence = pat.get("confidence", compute_confidence_score(pat["name"]))
                results.append({
                    "line": line_num,
                    "matched": matched,
                    "pattern_type": pat["name"],
                    "context": line.strip(),
                    "confidence_score": confidence,
                })

    return results
