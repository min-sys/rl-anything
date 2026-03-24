"""instruction compliance の E2E テスト。

corrections → violation 検出 → issue_schema → pitfall 登録の全フェーズ結合テスト。
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from critical_instruction_extractor import (
    CriticalInstruction,
    detect_instruction_violation,
    extract_critical_lines,
)
from issue_schema import (
    INSTRUCTION_VIOLATION_CANDIDATE,
    make_instruction_violation_issue,
)
from pitfall_manager import record_pitfall


def test_full_loop_corrections_to_pitfall(tmp_path):
    """Full loop: SKILL.md → extract → violation detect → issue → pitfall 登録。"""
    # 1. SKILL.md のコンテンツ
    skill_content = """\
# Commit Skill

## Usage
Run /commit to create a git commit.

## Important Rules
- 古い項目は CHANGELOG.md へ移動すること（削除は禁止）
- コミットメッセージは Conventional Commits 形式で記述すること
"""

    # 2. Extract: critical 行を抽出
    instructions = extract_critical_lines(skill_content)
    assert len(instructions) >= 1
    # 「移動」「禁止」を含む行が抽出されている
    move_instructions = [i for i in instructions if "移動" in i.original or "禁止" in i.original]
    assert len(move_instructions) >= 1

    # 3. Detect: correction との突合
    correction = {
        "message": "削除じゃなくて CHANGELOG に移動して",
        "correction_type": "stop",
        "last_skill": "commit",
    }

    violation = detect_instruction_violation(correction, instructions)
    assert violation is not None
    assert violation.match_type == "opposing_verb"

    # 4. Issue Schema: issue dict を生成
    issue = make_instruction_violation_issue(
        skill_name="commit",
        skill_path="/path/to/commit/SKILL.md",
        instruction_text=violation.instruction.original,
        correction_message=violation.correction_message,
        match_type=violation.match_type,
        confidence=violation.confidence,
        reason=violation.reason,
        needs_review=violation.needs_review,
    )
    assert issue["type"] == INSTRUCTION_VIOLATION_CANDIDATE
    assert issue["detail"]["match_type"] == "opposing_verb"

    # 5. Pitfall: pitfall として記録
    pitfalls_path = tmp_path / "pitfalls.md"
    pitfall_result = record_pitfall(
        pitfalls_path,
        f"Instruction violation: {violation.instruction.original[:50]}",
        f"instruction — {violation.reason}",
    )
    assert pitfall_result["status"] == "Candidate"

    # 6. 2回目の同一違反 → New に昇格
    pitfall_result2 = record_pitfall(
        pitfalls_path,
        f"Instruction violation: {violation.instruction.original[:50]}",
        f"instruction — {violation.reason}",
    )
    assert pitfall_result2["status"] == "New"

    # pitfalls.md に instruction カテゴリが記録されている
    content = pitfalls_path.read_text(encoding="utf-8")
    assert "instruction" in content
