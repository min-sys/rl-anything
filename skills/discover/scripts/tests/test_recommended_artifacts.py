"""detect_recommended_artifacts() のテスト。"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from discover import detect_recommended_artifacts, RECOMMENDED_ARTIFACTS


def test_all_installed_returns_empty(tmp_path):
    """全推奨アーティファクトが存在する場合、空リストを返す。"""
    patched = []
    for art in RECOMMENDED_ARTIFACTS:
        rule = tmp_path / f"{art['id']}.md"
        rule.write_text("test")
        new_art = {**art, "path": rule}
        if "hook_path" in art:
            hook = tmp_path / f"{art['id']}.py"
            hook.write_text("test")
            new_art["hook_path"] = hook
        patched.append(new_art)

    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_recommended_artifacts()
    assert result == []


def test_missing_rule_detected(tmp_path):
    """ルールが存在しない場合、missing に含まれる。"""
    patched = []
    for art in RECOMMENDED_ARTIFACTS:
        new_art = {**art, "path": tmp_path / "nonexistent.md"}
        if "hook_path" in art:
            hook = tmp_path / f"{art['id']}.py"
            hook.write_text("test")
            new_art["hook_path"] = hook
        patched.append(new_art)

    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_recommended_artifacts()
    assert len(result) > 0
    assert any(m["type"] == "rule" for m in result[0]["missing"])


def test_missing_hook_detected(tmp_path):
    """hook が存在しない場合、missing に含まれる。"""
    patched = []
    for art in RECOMMENDED_ARTIFACTS:
        rule = tmp_path / f"{art['id']}.md"
        rule.write_text("test")
        new_art = {**art, "path": rule}
        if "hook_path" in art:
            new_art["hook_path"] = tmp_path / "nonexistent.py"
        patched.append(new_art)

    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_recommended_artifacts()
    assert len(result) > 0
    assert any(m["type"] == "hook" for m in result[0]["missing"])
