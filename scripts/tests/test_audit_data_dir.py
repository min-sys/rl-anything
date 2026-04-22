#!/usr/bin/env python3
"""audit.py の DATA_DIR 統一 (rl_common.DATA_DIR への再エクスポート) の regression test。

fleet 構想 (issue #68) で各 PJ のデータ置き場を CLAUDE_PLUGIN_DATA env var で切り替える
ため、audit.py がハードコードしていた DATA_DIR を rl_common.py 参照に差し替えた。

このテストは以下を保証する:
1. audit.DATA_DIR と rl_common.DATA_DIR が同一オブジェクト (identity)
2. CLAUDE_PLUGIN_DATA 未設定時は従来通り ~/.claude/rl-anything/ を指す (regression)
3. CLAUDE_PLUGIN_DATA 指定時は env var のパスに切り替わる (fleet blocker 解消)
4. bloat_control.py の `from audit import DATA_DIR` が壊れない (既存コード互換)
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _import_audit(env: dict[str, str] | None = None) -> dict:
    """subprocess で audit module を import し DATA_DIR を返す。

    モジュールレベル評価なので env 切替を in-process で検証できず、subprocess 必須。
    """
    code = (
        "import sys, json; "
        f"sys.path.insert(0, {str(_REPO_ROOT / 'scripts' / 'lib')!r}); "
        f"sys.path.insert(0, {str(_REPO_ROOT / 'scripts')!r}); "
        "import audit, rl_common; "
        "print(json.dumps({"
        "'audit_dir': str(audit.DATA_DIR), "
        "'rl_common_dir': str(rl_common.DATA_DIR), "
        "'identity': audit.DATA_DIR is rl_common.DATA_DIR"
        "}))"
    )
    import json

    proc_env = os.environ.copy()
    # 未指定を強制するため CLAUDE_PLUGIN_DATA を明示削除
    proc_env.pop("CLAUDE_PLUGIN_DATA", None)
    if env:
        proc_env.update(env)

    result = subprocess.run(
        [sys.executable, "-c", code],
        env=proc_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"
    return json.loads(result.stdout.strip())


def test_audit_data_dir_is_rl_common_data_dir():
    """audit.DATA_DIR は rl_common.DATA_DIR と同一オブジェクト (真の源の一本化)。"""
    r = _import_audit()
    assert r["identity"] is True
    assert r["audit_dir"] == r["rl_common_dir"]


def test_audit_data_dir_default_without_env():
    """CLAUDE_PLUGIN_DATA 未設定時は ~/.claude/rl-anything/ を指す (regression)。"""
    r = _import_audit(env=None)
    expected = str(Path.home() / ".claude" / "rl-anything")
    assert r["audit_dir"] == expected, (
        f"期待 {expected} / 実際 {r['audit_dir']}. "
        "既存 audit コマンドの fallback が壊れている可能性"
    )


def test_audit_data_dir_env_override(tmp_path: Path):
    """CLAUDE_PLUGIN_DATA 指定時は env var のパスに切り替わる (fleet blocker 解消)。"""
    custom = tmp_path / "fleet-override"
    r = _import_audit(env={"CLAUDE_PLUGIN_DATA": str(custom)})
    assert r["audit_dir"] == str(custom), (
        f"期待 {custom} / 実際 {r['audit_dir']}. "
        "fleet の cross-project 切替ができない"
    )


def test_audit_data_dir_env_empty_string_falls_back():
    """CLAUDE_PLUGIN_DATA="" (空文字) 時は fallback に戻る (rl_common L19-20 の挙動)。"""
    r = _import_audit(env={"CLAUDE_PLUGIN_DATA": ""})
    expected = str(Path.home() / ".claude" / "rl-anything")
    assert r["audit_dir"] == expected


def test_bloat_control_import_audit_data_dir_compat():
    """bloat_control.py `from audit import DATA_DIR` が機能する (既存コード互換)。"""
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(_REPO_ROOT / 'scripts' / 'lib')!r}); "
        f"sys.path.insert(0, {str(_REPO_ROOT / 'scripts')!r}); "
        "from audit import DATA_DIR; "
        "print(str(DATA_DIR))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"bloat_control 経路が壊れた: {result.stderr}"
    assert result.stdout.strip()  # 空でないパス
