"""detect-deferred-task.py のテスト。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_SCRIPT = Path.home() / ".claude" / "hooks" / "detect-deferred-task.py"


def run_hook(input_data: dict) -> tuple[int, str]:
    """hook スクリプトを実行し (exit_code, stdout) を返す。"""
    proc = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout


class TestDeferralDetection:
    def test_detects_shimashoka(self):
        """「しましょうか」パターンを検出。"""
        rc, out = run_hook({
            "stop_hook_active": False,
            "last_assistant_message": "RAG検索品質改善のchangeを起こしましょうか？",
            "session_id": "test1",
        })
        assert rc == 0
        result = json.loads(out)
        assert result["decision"] == "block"

    def test_detects_atode(self):
        """「後で対応」パターンを検出。"""
        rc, out = run_hook({
            "stop_hook_active": False,
            "last_assistant_message": "テストの追加は後で対応しましょう。",
            "session_id": "test2",
        })
        assert rc == 0
        result = json.loads(out)
        assert result["decision"] == "block"

    def test_detects_jissouga_owattara(self):
        """「実装が終わったら」パターンを検出。"""
        rc, out = run_hook({
            "stop_hook_active": False,
            "last_assistant_message": "実装が終わったら別のchangeで対応しましょう",
            "session_id": "test3",
        })
        assert rc == 0
        result = json.loads(out)
        assert result["decision"] == "block"

    def test_detects_ikkaiskip(self):
        """「一旦スキップ」パターンを検出。"""
        rc, out = run_hook({
            "stop_hook_active": False,
            "last_assistant_message": "この問題は一旦スキップして先に進みましょう",
            "session_id": "test4",
        })
        assert rc == 0
        result = json.loads(out)
        assert result["decision"] == "block"

    def test_no_deferral(self):
        """先送りなしの通常メッセージは通過。"""
        rc, out = run_hook({
            "stop_hook_active": False,
            "last_assistant_message": "リファクタリングが完了しました。すべてのテストがパスしています。",
            "session_id": "test5",
        })
        assert rc == 0
        assert out == ""

    def test_stop_hook_active_skips(self):
        """stop_hook_active=true の場合はスキップ。"""
        rc, out = run_hook({
            "stop_hook_active": True,
            "last_assistant_message": "後で対応しましょう",
            "session_id": "test6",
        })
        assert rc == 0
        assert out == ""

    def test_empty_message_skips(self):
        """空メッセージはスキップ。"""
        rc, out = run_hook({
            "stop_hook_active": False,
            "last_assistant_message": "",
            "session_id": "test7",
        })
        assert rc == 0
        assert out == ""
