#!/usr/bin/env python3
"""remediation.py の新レイヤー issue type テスト。"""
import sys
from pathlib import Path

import pytest

# remediation.py のパスを通す
_evolve_scripts = Path(__file__).resolve().parent.parent.parent / "skills" / "evolve" / "scripts"
sys.path.insert(0, str(_evolve_scripts))

from remediation import compute_confidence_score, generate_rationale, classify_issue


# ── compute_confidence_score ──────────────────────────────


def test_confidence_orphan_rule():
    issue = {"type": "orphan_rule", "file": "rule.md", "detail": {"name": "test"}}
    score = compute_confidence_score(issue)
    assert 0.4 <= score <= 0.6


def test_confidence_stale_rule():
    issue = {"type": "stale_rule", "file": "rule.md", "detail": {"path": "missing.sh"}}
    score = compute_confidence_score(issue)
    assert score >= 0.9


def test_confidence_stale_memory():
    issue = {"type": "stale_memory", "file": "MEMORY.md", "detail": {"path": "old"}}
    score = compute_confidence_score(issue)
    assert 0.5 <= score <= 0.7


def test_confidence_memory_duplicate():
    issue = {"type": "memory_duplicate", "file": "MEMORY.md", "detail": {"similarity": 0.7}}
    score = compute_confidence_score(issue)
    assert 0.6 <= score <= 0.8


def test_confidence_hooks_unconfigured():
    issue = {"type": "hooks_unconfigured", "file": "settings.json", "detail": {}}
    score = compute_confidence_score(issue)
    assert 0.3 <= score <= 0.5


def test_confidence_claudemd_phantom_ref():
    issue = {"type": "claudemd_phantom_ref", "file": "CLAUDE.md", "detail": {"name": "x"}}
    score = compute_confidence_score(issue)
    assert score >= 0.85


def test_confidence_claudemd_missing_section():
    issue = {"type": "claudemd_missing_section", "file": "CLAUDE.md", "detail": {}}
    score = compute_confidence_score(issue)
    assert score >= 0.9


# ── generate_rationale ──────────────────────────────


def test_rationale_orphan_rule():
    issue = {"type": "orphan_rule", "file": "rule.md", "detail": {"name": "old-rule"}}
    r = generate_rationale(issue, "proposable")
    assert "old-rule" in r
    assert "参照されていません" in r


def test_rationale_stale_rule():
    issue = {"type": "stale_rule", "file": "rule.md", "detail": {"path": "scripts/deploy.sh"}}
    r = generate_rationale(issue, "auto_fixable")
    assert "scripts/deploy.sh" in r


def test_rationale_stale_memory():
    issue = {"type": "stale_memory", "file": "MEMORY.md", "detail": {"path": "obsolete_mod"}}
    r = generate_rationale(issue, "proposable")
    assert "obsolete_mod" in r


def test_rationale_memory_duplicate():
    issue = {
        "type": "memory_duplicate",
        "file": "MEMORY.md",
        "detail": {"sections": ["A Section", "B Section"], "similarity": 0.7},
    }
    r = generate_rationale(issue, "proposable")
    assert "A Section" in r
    assert "B Section" in r
    assert "0.7" in r


def test_rationale_hooks_unconfigured():
    issue = {"type": "hooks_unconfigured", "file": "settings.json", "detail": {}}
    r = generate_rationale(issue, "manual_required")
    assert "hooks" in r


def test_rationale_claudemd_phantom_ref():
    issue = {
        "type": "claudemd_phantom_ref",
        "file": "CLAUDE.md",
        "detail": {"name": "ghost-skill", "ref_type": "skill"},
    }
    r = generate_rationale(issue, "proposable")
    assert "ghost-skill" in r
    assert "skill" in r


def test_rationale_claudemd_missing_section():
    issue = {
        "type": "claudemd_missing_section",
        "file": "CLAUDE.md",
        "detail": {"section": "skills", "skill_count": 5},
    }
    r = generate_rationale(issue, "proposable")
    assert "skills" in r
    assert "5" in r


# ── classify_issue: 新 type の分類確認 ──────────────────


def test_classify_orphan_rule():
    issue = {"type": "orphan_rule", "file": ".claude/rules/x.md", "detail": {"name": "x"}}
    classified = classify_issue(issue)
    assert classified["category"] == "proposable"


def test_classify_hooks_unconfigured():
    issue = {"type": "hooks_unconfigured", "file": ".claude/settings.json", "detail": {}}
    classified = classify_issue(issue)
    assert classified["category"] == "manual_required"


def test_classify_claudemd_phantom_ref():
    issue = {"type": "claudemd_phantom_ref", "file": "CLAUDE.md", "detail": {"name": "x"}}
    classified = classify_issue(issue)
    # confidence=0.9, scope=project → proposable
    assert classified["category"] in ("proposable", "auto_fixable")
