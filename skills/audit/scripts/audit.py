#!/usr/bin/env python3
"""CLI エントリポイント shim — 実装は scripts/lib/audit.py に移設。
bin/rl-audit が整備されたら SKILL.md から直接呼ばれなくなる。"""
import importlib.util
import sys
from pathlib import Path

_lib = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "lib"
_spec = importlib.util.spec_from_file_location("audit", _lib / "audit.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["audit"] = _mod
_spec.loader.exec_module(_mod)

if __name__ == "__main__":
    _mod.main()
