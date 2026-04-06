#!/usr/bin/env python3
"""hooks 共通ユーティリティ — scripts/lib/rl_common.py の re-exporter。

hook scripts は 'import common' で従来通り使用可能。
ライブラリスクリプトは scripts/lib/rl_common から直接インポートすること。
"""
import sys
from pathlib import Path

# hooks/ → plugin_root/ → scripts/lib/
_lib = Path(__file__).resolve().parent.parent / "scripts" / "lib"
sys.path.insert(0, str(_lib))

from rl_common import *  # noqa: F401, F403
