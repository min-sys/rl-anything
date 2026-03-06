"""tool_usage_analyzer のテスト。"""
import json
import os
import tempfile
from pathlib import Path

import pytest

# モジュールパス解決
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.tool_usage_analyzer import (
    BUILTIN_REPLACEABLE_MAP,
    extract_tool_calls,
    classify_bash_commands,
    detect_repeating_commands,
    analyze_tool_usage,
    _is_cat_replaceable,
)


# ---------- extract_tool_calls ----------

class TestExtractToolCalls:
    def _make_session(self, tmp_path, records):
        """テスト用セッション JSONL を作成する。"""
        proj_dir = tmp_path / "projects" / "test-project"
        proj_dir.mkdir(parents=True)
        session_file = proj_dir / "session1.jsonl"
        lines = [json.dumps(r, ensure_ascii=False) for r in records]
        session_file.write_text("\n".join(lines), encoding="utf-8")
        return tmp_path / "projects"

    def test_extracts_tool_use(self, tmp_path):
        records = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/a.txt"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}},
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}},
            ]}},
        ]
        projects_dir = self._make_session(tmp_path, records)
        project_root = Path("/fake/test-project")

        counts, bash_cmds = extract_tool_calls(
            project_root, projects_dir=projects_dir,
        )

        assert counts["Read"] == 1
        assert counts["Bash"] == 2
        assert "git status" in bash_cmds
        assert "ls -la" in bash_cmds

    def test_graceful_skip_invalid_json(self, tmp_path):
        proj_dir = tmp_path / "projects" / "test-project"
        proj_dir.mkdir(parents=True)
        session_file = proj_dir / "session1.jsonl"
        session_file.write_text(
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","input":{}}]}}\n'
            'INVALID JSON LINE\n'
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Grep","input":{}}]}}\n',
            encoding="utf-8",
        )

        counts, _ = extract_tool_calls(
            Path("/fake/test-project"),
            projects_dir=tmp_path / "projects",
        )

        assert counts["Read"] == 1
        assert counts["Grep"] == 1

    def test_no_session_dir(self, tmp_path):
        counts, bash_cmds = extract_tool_calls(
            Path("/nonexistent/project"),
            projects_dir=tmp_path / "nonexistent",
        )
        assert len(counts) == 0
        assert len(bash_cmds) == 0

    def test_skips_non_assistant(self, tmp_path):
        records = [
            {"type": "user", "message": {"content": "hello"}},
            {"type": "progress"},
        ]
        projects_dir = self._make_session(tmp_path, records)
        counts, _ = extract_tool_calls(
            Path("/fake/test-project"), projects_dir=projects_dir,
        )
        assert len(counts) == 0


# ---------- classify_bash_commands ----------

class TestClassifyBashCommands:
    def test_builtin_replaceable(self):
        commands = ["cat /tmp/file.txt", "grep -r pattern .", "find . -name '*.py'"]
        result = classify_bash_commands(commands)
        assert len(result["builtin_replaceable"]) == 3
        heads = [item["head"] for item in result["builtin_replaceable"]]
        assert "cat" in heads
        assert "grep" in heads
        assert "find" in heads

    def test_cli_legitimate(self):
        commands = ["git status", "gh pr list", "npm install"]
        result = classify_bash_commands(commands)
        assert len(result["builtin_replaceable"]) == 0
        assert len(result["cli_legitimate"]) == 3

    def test_cat_heredoc_excluded(self):
        commands = ["cat <<'EOF'\nhello\nEOF"]
        result = classify_bash_commands(commands)
        assert len(result["builtin_replaceable"]) == 0
        assert len(result["cli_legitimate"]) == 1

    def test_cat_redirect_excluded(self):
        commands = ["cat file.txt > output.txt"]
        result = classify_bash_commands(commands)
        assert len(result["builtin_replaceable"]) == 0
        assert len(result["cli_legitimate"]) == 1

    def test_cat_simple_read(self):
        commands = ["cat /etc/hosts"]
        result = classify_bash_commands(commands)
        assert len(result["builtin_replaceable"]) == 1
        assert result["builtin_replaceable"][0]["alternative"] == "Read"

    def test_alternatives_correct(self):
        commands = ["sed -i 's/foo/bar/' file.txt", "awk '{print $1}' data.csv"]
        result = classify_bash_commands(commands)
        alternatives = {item["head"]: item["alternative"] for item in result["builtin_replaceable"]}
        assert alternatives["sed"] == "Edit"
        assert alternatives["awk"] == "Edit"

    def test_rg_replaceable(self):
        commands = ["rg pattern src/"]
        result = classify_bash_commands(commands)
        assert len(result["builtin_replaceable"]) == 1
        assert result["builtin_replaceable"][0]["alternative"] == "Grep"


# ---------- _is_cat_replaceable ----------

class TestIsCatReplaceable:
    def test_simple_cat(self):
        assert _is_cat_replaceable("cat file.txt") is True

    def test_cat_pipe(self):
        assert _is_cat_replaceable("cat file.txt | head -5") is True

    def test_cat_heredoc(self):
        assert _is_cat_replaceable("cat <<'EOF'") is False

    def test_cat_redirect(self):
        assert _is_cat_replaceable("cat > output.txt") is False

    def test_cat_append(self):
        assert _is_cat_replaceable("cat >> output.txt") is False


# ---------- detect_repeating_commands ----------

class TestDetectRepeatingCommands:
    def test_above_threshold(self):
        commands = ["git status"] * 6 + ["git diff"] * 3
        patterns = detect_repeating_commands(commands, threshold=5)
        assert len(patterns) == 1
        assert patterns[0]["pattern"] == "git status"
        assert patterns[0]["count"] == 6

    def test_below_threshold(self):
        commands = ["git status"] * 4
        patterns = detect_repeating_commands(commands, threshold=5)
        assert len(patterns) == 0

    def test_subcategory_classification(self):
        commands = ["python3 -m pytest tests/ -v"] * 6
        patterns = detect_repeating_commands(commands, threshold=5)
        assert len(patterns) == 1
        # "python3 -m" がキー
        assert patterns[0]["subcategory"] in ("script", "pytest")

    def test_multiple_patterns(self):
        commands = (
            ["git status"] * 5
            + ["gh pr list"] * 5
            + ["docker ps"] * 5
        )
        patterns = detect_repeating_commands(commands, threshold=5)
        assert len(patterns) == 3

    def test_examples_limited(self):
        commands = ["git status"] * 10
        patterns = detect_repeating_commands(commands, threshold=5)
        assert len(patterns[0]["examples"]) <= 3


# ---------- analyze_tool_usage ----------

class TestAnalyzeToolUsage:
    def test_empty_result(self, tmp_path):
        result = analyze_tool_usage(
            project_root=Path("/nonexistent"),
            projects_dir=tmp_path / "nonexistent",
        )
        assert result["total_tool_calls"] == 0
        assert result["bash_calls"] == 0
        assert result["builtin_replaceable"] == []
        assert result["repeating_patterns"] == []

    def test_integration(self, tmp_path):
        proj_dir = tmp_path / "projects" / "test-project"
        proj_dir.mkdir(parents=True)
        records = []
        # 6 git status + 3 cat (builtin_replaceable)
        for _ in range(6):
            records.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}},
            ]}})
        for _ in range(3):
            records.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "cat /tmp/file.txt"}},
            ]}})
        records.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/a.txt"}},
        ]}})

        session_file = proj_dir / "session1.jsonl"
        lines = [json.dumps(r, ensure_ascii=False) for r in records]
        session_file.write_text("\n".join(lines), encoding="utf-8")

        result = analyze_tool_usage(
            project_root=Path("/fake/test-project"),
            threshold=5,
            projects_dir=tmp_path / "projects",
        )

        assert result["total_tool_calls"] == 10
        assert result["bash_calls"] == 9
        assert len(result["repeating_patterns"]) >= 1  # git status >= 5
        assert len(result["builtin_replaceable"]) >= 1  # cat
