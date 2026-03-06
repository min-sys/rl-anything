"""collect_issues() のユニットテスト。"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "scripts"))

from audit import collect_issues


@pytest.fixture
def project_dir(tmp_path):
    """基本的なプロジェクト構造を作成する。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "skills").mkdir()
    (claude_dir / "rules").mkdir()
    memory_dir = claude_dir / "memory"
    memory_dir.mkdir()
    return tmp_path


def test_violations(project_dir):
    """行数超過の issue が返される。"""
    claude_md = project_dir / "CLAUDE.md"
    claude_md.write_text("\n".join([f"line {i}" for i in range(250)]))

    with patch("audit.read_auto_memory", return_value=[]):
        issues = collect_issues(project_dir)

    violation_issues = [i for i in issues if i["type"] == "line_limit_violation"]
    assert len(violation_issues) >= 1
    assert violation_issues[0]["detail"]["lines"] == 250
    assert violation_issues[0]["detail"]["limit"] == 200
    assert violation_issues[0]["source"] == "check_line_limits"


def test_stale_refs(project_dir):
    """存在しないパス参照が stale_ref として返される。"""
    memory_dir = project_dir / ".claude" / "memory"
    memory_file = memory_dir / "MEMORY.md"
    memory_file.write_text("# Memory\n\n- See skills/nonexistent/SKILL.md\n")

    with patch("audit.read_auto_memory", return_value=[]):
        issues = collect_issues(project_dir)

    stale_issues = [i for i in issues if i["type"] == "stale_ref"]
    assert len(stale_issues) >= 1
    assert "nonexistent" in stale_issues[0]["detail"]["path"]


def test_near_limits(project_dir):
    """肥大化警告の issue が返される。"""
    memory_dir = project_dir / ".claude" / "memory"
    memory_file = memory_dir / "MEMORY.md"
    # MEMORY.md の制限は 200 行、80% = 160 行以上で near_limit
    memory_file.write_text("\n".join([f"line {i}" for i in range(170)]))

    with patch("audit.read_auto_memory", return_value=[]):
        issues = collect_issues(project_dir)

    near_issues = [i for i in issues if i["type"] == "near_limit"]
    assert len(near_issues) >= 1
    assert near_issues[0]["detail"]["pct"] >= 80


def test_duplicates(project_dir):
    """重複候補の issue が返される。"""
    skills_dir = project_dir / ".claude" / "skills"
    for name in ["my-skill", "myskill"]:
        d = skills_dir / name
        d.mkdir()
        (d / "SKILL.md").write_text(f"# {name}\ncontent\n")

    with patch("audit.read_auto_memory", return_value=[]):
        issues = collect_issues(project_dir)

    dup_issues = [i for i in issues if i["type"] == "duplicate"]
    assert len(dup_issues) >= 1
    assert dup_issues[0]["source"] == "detect_duplicates_simple"


def test_no_issues(project_dir):
    """問題がなければ空リストを返す。"""
    with patch("audit.read_auto_memory", return_value=[]):
        issues = collect_issues(project_dir)

    assert issues == []


def test_issue_format(project_dir):
    """各 issue が統一フォーマットを満たす。"""
    claude_md = project_dir / "CLAUDE.md"
    claude_md.write_text("\n".join([f"line {i}" for i in range(250)]))

    with patch("audit.read_auto_memory", return_value=[]):
        issues = collect_issues(project_dir)

    for issue in issues:
        assert "type" in issue
        assert "file" in issue
        assert "detail" in issue
        assert "source" in issue
        assert isinstance(issue["type"], str)
        assert isinstance(issue["detail"], dict)
