"""issue_schema の instruction_violation_candidate factory テスト。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from issue_schema import (
    INSTRUCTION_VIOLATION_CANDIDATE,
    IVC_CONFIDENCE,
    IVC_CORRECTION_MESSAGE,
    IVC_INSTRUCTION_TEXT,
    IVC_MATCH_TYPE,
    IVC_NEEDS_REVIEW,
    IVC_REASON,
    IVC_SKILL_NAME,
    make_instruction_violation_issue,
)


def test_make_instruction_violation_issue():
    """factory が正しい構造の issue dict を生成する。"""
    issue = make_instruction_violation_issue(
        skill_name="commit",
        skill_path="/path/to/SKILL.md",
        instruction_text="古い項目は CHANGELOG に移動すること",
        correction_message="削除じゃなくて移動して",
        match_type="opposing_verb",
        confidence=0.95,
        reason="対立動詞検出: move vs delete",
        needs_review=False,
    )

    assert issue["type"] == INSTRUCTION_VIOLATION_CANDIDATE
    assert issue["file"] == "/path/to/SKILL.md"
    assert issue["source"] == "instruction_violation_detection"
    assert issue["detail"][IVC_SKILL_NAME] == "commit"
    assert issue["detail"][IVC_INSTRUCTION_TEXT] == "古い項目は CHANGELOG に移動すること"
    assert issue["detail"][IVC_CORRECTION_MESSAGE] == "削除じゃなくて移動して"
    assert issue["detail"][IVC_MATCH_TYPE] == "opposing_verb"
    assert issue["detail"][IVC_CONFIDENCE] == 0.95
    assert issue["detail"][IVC_REASON] == "対立動詞検出: move vs delete"
    assert issue["detail"][IVC_NEEDS_REVIEW] is False
