"""テスト用パス設定."""

import sys
from pathlib import Path

# scripts/ を import パスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
