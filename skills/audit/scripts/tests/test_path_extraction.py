"""_extract_paths_outside_codeblocks() の専用ユニットテスト。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit import _extract_paths_outside_codeblocks


def _paths(text: str) -> list[str]:
    """抽出パスの文字列リストを返すヘルパー。"""
    return [p for _, p in _extract_paths_outside_codeblocks(text)]


# --- 真陽性: 受け入れるべきパス ---

@pytest.mark.parametrize(
    "text,expected",
    [
        pytest.param("skills/update", ["skills/update"], id="known-prefix-no-ext"),
        pytest.param("scripts/lib", ["scripts/lib"], id="known-prefix-scripts-lib"),
        pytest.param("hooks/common", ["hooks/common"], id="known-prefix-hooks"),
        pytest.param(".claude/rules", [".claude/rules"], id="known-prefix-dotclaude"),
        pytest.param("openspec/changes", ["openspec/changes"], id="known-prefix-openspec"),
        pytest.param("docs/guide", ["docs/guide"], id="known-prefix-docs"),
        pytest.param("scripts/reflect_utils.py", ["scripts/reflect_utils.py"], id="known-prefix-with-ext"),
        pytest.param("config/settings.yaml", ["config/settings.yaml"], id="unknown-prefix-with-ext"),
        pytest.param("some/deep/nested/file.py", ["some/deep/nested/file.py"], id="deep-path-with-ext"),
        pytest.param("skills/audit/scripts", ["skills/audit/scripts"], id="three-segments-no-ext"),
        pytest.param(
            "scripts/rl/tests/test_workflow_analysis.py",
            ["scripts/rl/tests/test_workflow_analysis.py"],
            id="deep-path-known-prefix",
        ),
        pytest.param("/Users/foo/bar", ["/Users/foo/bar"], id="absolute-path"),
    ],
)
def test_true_positives(text: str, expected: list[str]):
    assert _paths(text) == expected


# --- 偽陽性: 除外すべきパス ---

@pytest.mark.parametrize(
    "text",
    [
        pytest.param("usage/errors", id="usage-errors"),
        pytest.param("discover/audit", id="discover-audit"),
        pytest.param("observe/hooks", id="observe-hooks"),
        pytest.param("- discover/audit: telemetry_query 経由の project フィルタリング対応", id="list-context"),
        pytest.param("approval/confirmation", id="approval-confirmation"),
    ],
)
def test_false_positives_excluded(text: str):
    assert _paths(text) == []


# --- エッジケース ---

def test_codeblock_paths_excluded():
    text = "```\nusage/errors\nskills/update\n```"
    assert _paths(text) == []


def test_mixed_content():
    text = """- discover/audit: telemetry_query で分析
- skills/update/ — `/rl-anything:update` スキル
- scripts/reflect_utils.py — 8層メモリルーティング
- usage/errors レコードに project フィールド追加"""
    paths = _paths(text)
    assert "skills/update" in paths
    assert "scripts/reflect_utils.py" in paths
    assert "usage/errors" not in paths
    assert "discover/audit" not in paths


def test_known_prefix_in_codeblock_excluded():
    text = "通常テキスト skills/update\n```\nscripts/lib\n```"
    paths = _paths(text)
    assert "skills/update" in paths
    assert "scripts/lib" not in paths


# --- 数値パターン除外 ---

@pytest.mark.parametrize(
    "text",
    [
        pytest.param("429/500/503", id="http-status-codes"),
        pytest.param("429/500", id="two-status-codes"),
        pytest.param("1.0/2.1", id="version-numbers"),
    ],
)
def test_numeric_patterns_excluded(text: str):
    assert _paths(text) == []
