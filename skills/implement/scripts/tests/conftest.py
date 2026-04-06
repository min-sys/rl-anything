"""skills/implement/scripts/tests の sys.path 設定。

scripts/rl/fitness/telemetry.py との名前衝突を防ぐため、
正しい telemetry モジュールを sys.modules に事前登録する。
"""
import importlib.util
import sys
from pathlib import Path

_impl_scripts = Path(__file__).resolve().parent.parent
_telemetry_path = _impl_scripts / "telemetry.py"

# skills/implement/scripts/ を最優先に
if str(_impl_scripts) not in sys.path:
    sys.path.insert(0, str(_impl_scripts))

# 正しい telemetry を sys.modules["telemetry"] に登録する。
# scripts/rl/fitness/ が sys.path に入っていると誤ったモジュールが
# import されるため、ここで正しいモジュールをキャッシュしておく。
_spec = importlib.util.spec_from_file_location("telemetry", _telemetry_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["telemetry"] = _mod
_spec.loader.exec_module(_mod)
