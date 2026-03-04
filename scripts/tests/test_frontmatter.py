"""scripts/lib/frontmatter.py のユニットテスト。"""
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.frontmatter import extract_description, parse_frontmatter


# --- parse_frontmatter ---


def test_parse_frontmatter_basic(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\nname: foo\ndescription: bar\n---\n# Body")
    result = parse_frontmatter(f)
    assert result == {"name": "foo", "description": "bar"}


def test_parse_frontmatter_no_frontmatter(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("# Just a heading\nSome content")
    assert parse_frontmatter(f) == {}


def test_parse_frontmatter_empty_yaml(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\n---\n# Body")
    assert parse_frontmatter(f) == {}


def test_parse_frontmatter_invalid_yaml(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\n: invalid: yaml: [[\n---\n")
    assert parse_frontmatter(f) == {}


def test_parse_frontmatter_missing_end_delimiter(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\nname: foo\n# no closing delimiter")
    assert parse_frontmatter(f) == {}


def test_parse_frontmatter_nonexistent_file(tmp_path):
    assert parse_frontmatter(tmp_path / "nonexistent.md") == {}


def test_parse_frontmatter_with_paths(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\npaths:\n  - src/**/*.ts\n  - lib/*.py\n---\n")
    result = parse_frontmatter(f)
    assert result["paths"] == ["src/**/*.ts", "lib/*.py"]


# --- extract_description ---


def test_extract_description_basic(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: my-skill\ndescription: A useful skill\n---\n")
    assert extract_description(f) == "A useful skill"


def test_extract_description_multiline(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text(
        "---\nname: my-skill\ndescription: |\n"
        "  First line of description.\n"
        "  Second line of description.\n"
        "---\n"
    )
    assert extract_description(f) == "First line of description."


def test_extract_description_missing(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("---\nname: my-skill\n---\n")
    assert extract_description(f) == ""


def test_extract_description_no_file(tmp_path):
    assert extract_description(tmp_path / "nonexistent.md") == ""


def test_extract_description_no_frontmatter(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("# No frontmatter here")
    assert extract_description(f) == ""
