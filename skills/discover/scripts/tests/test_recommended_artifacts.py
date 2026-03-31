"""detect_recommended_artifacts() / detect_installed_artifacts() のテスト。"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from discover import (
    detect_recommended_artifacts,
    detect_installed_artifacts,
    RECOMMENDED_ARTIFACTS,
)


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


def test_recommendation_id_entries_have_required_fields():
    """recommendation_id 付きエントリが必須フィールドを持つことを検証。"""
    for art in RECOMMENDED_ARTIFACTS:
        if "recommendation_id" not in art:
            continue
        assert isinstance(art["recommendation_id"], str), f"{art['id']} missing recommendation_id str"
        assert "content_patterns" in art, f"{art['id']} missing content_patterns"
        assert isinstance(art["content_patterns"], list), f"{art['id']} content_patterns must be list"
        assert len(art["content_patterns"]) > 0, f"{art['id']} content_patterns must not be empty"
        assert "hook_path" in art, f"{art['id']} missing hook_path"


def test_builtin_replaceable_and_sleep_polling_registered():
    """builtin_replaceable と sleep_polling の recommendation_id が登録されている。"""
    rec_ids = {art["recommendation_id"] for art in RECOMMENDED_ARTIFACTS if "recommendation_id" in art}
    assert "builtin_replaceable" in rec_ids
    assert "sleep_polling" in rec_ids


def test_worktree_parallel_work_registered():
    """worktree-parallel-work エントリが RECOMMENDED_ARTIFACTS に登録されている。"""
    ids = {art["id"] for art in RECOMMENDED_ARTIFACTS}
    assert "worktree-parallel-work" in ids
    art = next(a for a in RECOMMENDED_ARTIFACTS if a["id"] == "worktree-parallel-work")
    assert art["type"] == "rule+hook"
    assert art["path"] is not None  # rule path あり
    assert art["hook_path"] is not None  # hook path あり


def test_deploy_lock_registered():
    """deploy-lock エントリが RECOMMENDED_ARTIFACTS に登録されている。"""
    ids = {art["id"] for art in RECOMMENDED_ARTIFACTS}
    assert "deploy-lock" in ids
    art = next(a for a in RECOMMENDED_ARTIFACTS if a["id"] == "deploy-lock")
    assert art["type"] == "hook"
    assert art["path"] is None  # hook-only
    assert art["hook_path"] is not None


def test_kill_guard_registered():
    """kill-guard エントリが RECOMMENDED_ARTIFACTS に登録されている。"""
    ids = {art["id"] for art in RECOMMENDED_ARTIFACTS}
    assert "kill-guard" in ids
    art = next(a for a in RECOMMENDED_ARTIFACTS if a["id"] == "kill-guard")
    assert art["type"] == "hook"
    assert art["path"] is None  # hook-only
    assert art["hook_path"] is not None


def test_kill_guard_missing_when_no_hook(tmp_path):
    """kill-guard hook が未導入の場合、missing に含まれる。"""
    patched = [
        {
            "id": "kill-guard",
            "type": "hook",
            "path": None,
            "description": "test",
            "hook_path": tmp_path / "nonexistent.py",
        },
    ]
    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_recommended_artifacts()
    assert len(result) == 1
    assert result[0]["id"] == "kill-guard"
    assert any(m["type"] == "hook" for m in result[0]["missing"])


def test_worktree_missing_when_no_rule(tmp_path):
    """worktree rule が未導入の場合、missing に含まれる。"""
    hook = tmp_path / "check-worktree.py"
    hook.write_text("# stash detection hook")
    patched = [
        {
            "id": "worktree-parallel-work",
            "type": "rule+hook",
            "path": tmp_path / "nonexistent.md",
            "description": "test",
            "hook_path": hook,
        },
    ]
    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_recommended_artifacts()
    assert len(result) == 1
    assert result[0]["id"] == "worktree-parallel-work"
    assert any(m["type"] == "rule" for m in result[0]["missing"])


def test_deploy_lock_missing_when_no_hook(tmp_path):
    """deploy-lock hook が未導入の場合、missing に含まれる。"""
    patched = [
        {
            "id": "deploy-lock",
            "type": "hook",
            "path": None,
            "description": "test",
            "hook_path": tmp_path / "nonexistent.py",
        },
    ]
    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_recommended_artifacts()
    assert len(result) == 1
    assert result[0]["id"] == "deploy-lock"
    assert any(m["type"] == "hook" for m in result[0]["missing"])


def test_path_none_artifact_handled_in_detect_recommended(tmp_path):
    """path=None の artifact（sleep-polling-guard 等）でエラーにならない。"""
    patched = [
        {
            "id": "test-null-path",
            "type": "hook",
            "path": None,
            "description": "test",
            "hook_path": tmp_path / "nonexistent.py",
            "recommendation_id": "test_rec",
            "content_patterns": ["TEST"],
        },
    ]
    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_recommended_artifacts()
    assert len(result) == 1
    assert any(m["type"] == "hook" for m in result[0]["missing"])


def test_path_none_artifact_handled_in_detect_installed(tmp_path):
    """path=None の artifact が hook 存在時に installed として検出される。"""
    hook = tmp_path / "hook.py"
    hook.write_text("test")
    patched = [
        {
            "id": "test-null-path",
            "type": "hook",
            "path": None,
            "description": "test",
            "hook_path": hook,
        },
    ]
    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_installed_artifacts()
    assert len(result) == 1
    assert result[0]["id"] == "test-null-path"


def test_mitigation_metrics_builtin_replaceable(tmp_path):
    """builtin_replaceable の mitigation_metrics が正しく算出される。"""
    hook = tmp_path / "hook.py"
    hook.write_text("REPLACEABLE = {'cat': 'Read'}\n")
    rule = tmp_path / "rule.md"
    rule.write_text("# test\n")
    patched = [
        {
            "id": "avoid-bash-builtin",
            "type": "rule+hook",
            "path": rule,
            "description": "test",
            "hook_path": hook,
            "data_driven": True,
            "recommendation_id": "builtin_replaceable",
            "content_patterns": ["REPLACEABLE"],
        },
    ]
    tool_usage = {
        "builtin_replaceable": [
            {"pattern": "cat → Read", "count": 10},
            {"pattern": "grep → Grep", "count": 5},
        ],
        "repeating_patterns": [],
    }
    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_installed_artifacts(tool_usage_patterns=tool_usage)
    assert len(result) == 1
    metrics = result[0]["mitigation_metrics"]
    assert metrics["mitigated"] is True
    assert metrics["recent_count"] == 15
    assert metrics["content_matched"] is True


def test_mitigation_metrics_sleep_polling(tmp_path):
    """sleep_polling の mitigation_metrics が正しく算出される。"""
    hook = tmp_path / "hook.py"
    hook.write_text("if 'sleep' in command:\n    block()\n")
    patched = [
        {
            "id": "sleep-polling-guard",
            "type": "hook",
            "path": None,
            "description": "test",
            "hook_path": hook,
            "recommendation_id": "sleep_polling",
            "content_patterns": [r"\bsleep\b"],
        },
    ]
    tool_usage = {
        "builtin_replaceable": [],
        "repeating_patterns": [
            {"pattern": "sleep 5", "count": 8},
            {"pattern": "git status", "count": 20},
        ],
    }
    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_installed_artifacts(tool_usage_patterns=tool_usage)
    assert len(result) == 1
    metrics = result[0]["mitigation_metrics"]
    assert metrics["mitigated"] is True
    assert metrics["recent_count"] == 8


def test_mitigation_metrics_no_telemetry(tmp_path):
    """テレメトリなしでも mitigated=True, recent_count=0 を返す。"""
    hook = tmp_path / "hook.py"
    hook.write_text("REPLACEABLE = {}\n")
    rule = tmp_path / "rule.md"
    rule.write_text("# test\n")
    patched = [
        {
            "id": "avoid-bash-builtin",
            "type": "rule+hook",
            "path": rule,
            "description": "test",
            "hook_path": hook,
            "data_driven": True,
            "recommendation_id": "builtin_replaceable",
            "content_patterns": ["REPLACEABLE"],
        },
    ]
    with patch("discover.RECOMMENDED_ARTIFACTS", patched):
        result = detect_installed_artifacts(tool_usage_patterns=None)
    assert len(result) == 1
    metrics = result[0]["mitigation_metrics"]
    assert metrics["mitigated"] is True
    assert metrics["recent_count"] == 0
