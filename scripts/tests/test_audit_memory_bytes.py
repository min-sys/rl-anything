#!/usr/bin/env python3
"""audit.py の MEMORY.md バイトサイズチェックのテスト。"""
import sys
from pathlib import Path

import pytest

_audit_scripts = Path(__file__).resolve().parent.parent.parent / "skills" / "audit" / "scripts"
sys.path.insert(0, str(_audit_scripts))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit import check_line_limits


def _make_memory_file(tmp_path: Path, content: str, name: str = "MEMORY.md") -> Path:
    """tmp_path 配下に memory ファイルを作成して返す。"""
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    f = mem_dir / name
    f.write_text(content, encoding="utf-8")
    return f


def test_audit_memory_byte_violation(tmp_path):
    """26KB の MEMORY.md でバイト超過 violation が検出される。"""
    content = "a" * 26_000  # 26KB, 1行
    path = _make_memory_file(tmp_path, content)
    artifacts = {"memory": [path]}
    violations = check_line_limits(artifacts)
    byte_violations = [v for v in violations if v.get("bytes") is not None]
    assert len(byte_violations) == 1
    assert byte_violations[0]["bytes"] == 26_000
    assert byte_violations[0]["bytes_limit"] == 25_000


def test_audit_memory_byte_under_limit(tmp_path):
    """19KB の MEMORY.md でバイト violation/warning なし。"""
    content = "a" * 19_000  # 19KB < 20KB near-limit
    path = _make_memory_file(tmp_path, content)
    artifacts = {"memory": [path]}
    violations = check_line_limits(artifacts)
    byte_violations = [v for v in violations if v.get("bytes") is not None]
    assert len(byte_violations) == 0


def test_audit_memory_byte_near_limit(tmp_path):
    """21KB の MEMORY.md で near-limit warning が出る。"""
    content = "a" * 21_000  # 21KB > 20KB near-limit
    path = _make_memory_file(tmp_path, content)
    artifacts = {"memory": [path]}
    violations = check_line_limits(artifacts)
    near_warnings = [v for v in violations if v.get("near_limit") is True]
    assert len(near_warnings) == 1
    assert near_warnings[0]["bytes"] == 21_000
    assert near_warnings[0].get("warning_only") is True


def test_audit_memory_line_and_byte(tmp_path):
    """行数・バイト数の両方超過時に両方レポートされる。"""
    # 201行で各行130バイト = 201 * 131 (改行含む) ≈ 26331 bytes
    content = "\n".join(["x" * 130] * 201)
    path = _make_memory_file(tmp_path, content)
    artifacts = {"memory": [path]}
    violations = check_line_limits(artifacts)
    line_violations = [v for v in violations if "lines" in v and "bytes" not in v]
    byte_violations = [v for v in violations if v.get("bytes") is not None and v.get("near_limit") is not True]
    assert len(line_violations) >= 1  # 行数超過
    assert len(byte_violations) >= 1  # バイト超過


def test_audit_memory_non_index_file_no_byte_check(tmp_path):
    """MEMORY.md 以外の memory ファイルにはバイトチェックなし。"""
    content = "a" * 26_000  # 26KB だが MEMORY.md ではない
    path = _make_memory_file(tmp_path, content, name="topic.md")
    artifacts = {"memory": [path]}
    violations = check_line_limits(artifacts)
    byte_violations = [v for v in violations if v.get("bytes") is not None]
    assert len(byte_violations) == 0
