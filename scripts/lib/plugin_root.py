#!/usr/bin/env python3
"""プラグインルートディレクトリの解決。

このファイルは scripts/lib/ に置かれることを前提にしている。
全スクリプトはここから PLUGIN_ROOT をインポートし、
.parent.parent.parent.parent のようなハードコードを避ける。
"""
from pathlib import Path

# scripts/lib/plugin_root.py → scripts/lib/ → scripts/ → <plugin_root>/
PLUGIN_ROOT: Path = Path(__file__).resolve().parent.parent.parent
