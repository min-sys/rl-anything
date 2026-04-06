"""plugin_root.py のテスト。"""
import sys
from pathlib import Path

_lib = Path(__file__).resolve().parent.parent / "lib"
sys.path.insert(0, str(_lib))

from plugin_root import PLUGIN_ROOT


def test_plugin_root_is_directory():
    assert PLUGIN_ROOT.is_dir(), f"PLUGIN_ROOT が存在しない: {PLUGIN_ROOT}"


def test_plugin_root_contains_expected_dirs():
    """PLUGIN_ROOT がプラグインルートであることを構造で検証する。"""
    assert (PLUGIN_ROOT / "hooks").is_dir(), "hooks/ が見つからない"
    assert (PLUGIN_ROOT / "scripts").is_dir(), "scripts/ が見つからない"
    assert (PLUGIN_ROOT / "skills").is_dir(), "skills/ が見つからない"


def test_plugin_root_contains_claude_md():
    assert (PLUGIN_ROOT / "CLAUDE.md").exists(), "CLAUDE.md が見つからない"


def test_plugin_root_depth():
    """scripts/lib/plugin_root.py からの depth が正しいことを確認。"""
    from plugin_root import __file__ as src
    src_path = Path(src).resolve()
    # scripts/lib/plugin_root.py → scripts/lib → scripts → root
    assert src_path.parent.parent.parent == PLUGIN_ROOT
