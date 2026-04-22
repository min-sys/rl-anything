"""fleet モジュールのユニットテスト。

Phase 1 で必須の 5 関数をカバー:
- resolve_auto_memory_dir
- enumerate_projects
- classify_project
- run_audit_subprocess
- format_status_table

特殊文字を含むパスは Phase 3 で扱う（本テストは扱わない）。
"""

import sys
from pathlib import Path

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

from fleet import enumerate_projects, resolve_auto_memory_dir  # noqa: E402


class TestResolveAutoMemoryDir:
    """resolve_auto_memory_dir() の命名規則逆引きテスト。"""

    def test_通常のPJパス(self):
        pj = Path("/Users/foo/matsukaze-utils/bots")
        result = resolve_auto_memory_dir(pj)
        assert result == Path.home() / ".claude" / "projects" / "-Users-foo-matsukaze-utils-bots"

    def test_実測_rl_anything_PJ(self):
        """~/.claude/projects/ 内に実在するはずの slug と一致する。"""
        pj = Path("/Users/matsukaze-takashi/matsukaze-utils/rl-anything")
        result = resolve_auto_memory_dir(pj)
        expected = Path.home() / ".claude" / "projects" / "-Users-matsukaze-takashi-matsukaze-utils-rl-anything"
        assert result == expected

    def test_trailing_slash_正規化(self):
        """末尾スラッシュは除去されて同じ結果になる。"""
        with_slash = Path("/Users/foo/bar/")
        without_slash = Path("/Users/foo/bar")
        assert resolve_auto_memory_dir(with_slash) == resolve_auto_memory_dir(without_slash)

    def test_相対パスは絶対化される(self):
        """相対パスを渡されたら resolve して絶対パスに揃える。"""
        rel = Path("./somewhere")
        result = resolve_auto_memory_dir(rel)
        # resolve した absolute path が `-` 区切りで slug 化されている
        abs_str = str(rel.resolve())
        expected = Path.home() / ".claude" / "projects" / abs_str.replace("/", "-")
        assert result == expected


class TestEnumerateProjects:
    """enumerate_projects() の PJ 列挙フィルタテスト。"""

    def test_両方持ちとCLAUDE_md単体と_claude_単体を含み両方無しを除外(self, tmp_path):
        (tmp_path / "both" / ".claude").mkdir(parents=True)
        (tmp_path / "both" / "CLAUDE.md").write_text("")
        (tmp_path / "claude_md_only" / "CLAUDE.md").parent.mkdir()
        (tmp_path / "claude_md_only" / "CLAUDE.md").write_text("")
        (tmp_path / "dot_claude_only" / ".claude").mkdir(parents=True)
        (tmp_path / "neither").mkdir()
        result = enumerate_projects(tmp_path)
        names = [p.name for p in result]
        assert names == ["both", "claude_md_only", "dot_claude_only"]

    def test_rootが存在しなければ空リスト(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        assert enumerate_projects(missing) == []

    def test_ファイルは除外_子ディレクトリのみ対象(self, tmp_path):
        (tmp_path / "pj" / ".claude").mkdir(parents=True)
        (tmp_path / "CLAUDE.md").write_text("")  # root 直下のファイルは対象外
        result = enumerate_projects(tmp_path)
        assert [p.name for p in result] == ["pj"]

    def test_ドットディレクトリは除外(self, tmp_path):
        """`.worktrees` のようなドットディレクトリは PJ 候補にしない。"""
        (tmp_path / ".worktrees" / ".claude").mkdir(parents=True)
        (tmp_path / "pj" / "CLAUDE.md").parent.mkdir()
        (tmp_path / "pj" / "CLAUDE.md").write_text("")
        result = enumerate_projects(tmp_path)
        assert [p.name for p in result] == ["pj"]
