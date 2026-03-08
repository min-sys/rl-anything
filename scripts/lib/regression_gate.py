"""共通 regression gate ライブラリ。

optimize.py / rl-loop で共有するゲートチェックを一元管理する。
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

FORBIDDEN_PATTERNS = ["TODO", "FIXME", "HACK", "XXX"]


@dataclass
class GateResult:
    """ゲートチェックの結果。スコアリングは呼び出し側の責務。"""

    passed: bool
    reason: Optional[str]


def check_gates(
    candidate: str,
    original: Optional[str] = None,
    *,
    max_lines: int,
    pitfall_patterns_path: Optional[str] = None,
) -> GateResult:
    """全ゲートチェックを実行し結果を返す。

    Args:
        candidate: パッチ候補テキスト
        original: 元のファイル内容（frontmatter 保持チェック用）
        max_lines: 行数上限（必須）。呼び出し側が line_limit.py の定数を参照して渡す
        pitfall_patterns_path: pitfalls.md のパス。None ならスキップ
    """
    # 空コンテンツチェック
    if not candidate or not candidate.strip():
        return GateResult(passed=False, reason="empty_content")

    # 行数制限チェック
    lines = candidate.count("\n") + 1
    if lines > max_lines:
        return GateResult(
            passed=False, reason=f"line_limit_exceeded({lines}/{max_lines})"
        )

    # 禁止パターンチェック
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in candidate:
            return GateResult(passed=False, reason=f"forbidden_pattern({pattern})")

    # pitfall パターンチェック
    if pitfall_patterns_path is not None:
        for pp in _load_pitfall_patterns(pitfall_patterns_path):
            if pp in candidate:
                return GateResult(passed=False, reason=f"pitfall_pattern({pp})")

    # frontmatter 保持チェック
    if original and original.startswith("---"):
        if not candidate.startswith("---"):
            return GateResult(passed=False, reason="frontmatter_lost")

    return GateResult(passed=True, reason=None)


def _load_pitfall_patterns(pitfall_patterns_path: str) -> List[str]:
    """pitfalls.md からゲート不合格パターンを読み込む。"""
    path = Path(pitfall_patterns_path)
    if not path.exists():
        return []

    patterns = []
    content = path.read_text(encoding="utf-8")
    for line in content.strip().split("\n"):
        if not line.strip().startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4 and parts[1] == "gate":
            m = re.match(r"forbidden_pattern\((.+)\)", parts[2])
            if m:
                patterns.append(m.group(1))
    return patterns
