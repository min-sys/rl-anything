"""E2E: session_summary → trigger_engine → pending-trigger.json → restore_state → メッセージ出力。"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

_hooks_dir = Path(__file__).resolve().parent.parent
_plugin_root = _hooks_dir.parent
sys.path.insert(0, str(_hooks_dir))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

import trigger_engine


@pytest.fixture
def data_dir(tmp_path):
    with mock.patch("trigger_engine.DATA_DIR", tmp_path), mock.patch(
        "trigger_engine.EVOLVE_STATE_FILE", tmp_path / "evolve-state.json"
    ), mock.patch(
        "trigger_engine.PENDING_TRIGGER_FILE", tmp_path / "pending-trigger.json"
    ), mock.patch(
        "trigger_engine.SNOOZE_FILE", tmp_path / "trigger-snooze.json"
    ):
        yield tmp_path


class TestE2ETriggerFlow:
    def test_full_flow_session_end(self, data_dir):
        """session_summary → trigger_engine → pending → restore_state の一連フロー。"""
        # Step 1: Setup evolve state (8 days ago, recent audit)
        old_ts = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        state = {
            "last_run_timestamp": old_ts,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (data_dir / "evolve-state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

        # Step 2: Evaluate session end (simulating session_summary hook)
        result = trigger_engine.evaluate_session_end()
        assert result.triggered is True
        assert "days_elapsed" in result.details.get("all_reasons", [])

        # Step 3: Write pending trigger (what session_summary._evaluate_trigger does)
        trigger_engine.write_pending_trigger(result)
        assert (data_dir / "pending-trigger.json").exists()

        # Step 4: Read and deliver (what restore_state._deliver_pending_trigger does)
        data = trigger_engine.read_and_delete_pending_trigger()
        assert data is not None
        assert data["triggered"] is True
        assert "/rl-anything:evolve" in data["message"]

        # Step 5: File should be deleted after delivery
        assert not (data_dir / "pending-trigger.json").exists()

    def test_no_trigger_no_pending(self, data_dir):
        """条件未達 → pending-trigger.json なし → restore_state は何もしない。"""
        state = {
            "last_run_timestamp": datetime.now(timezone.utc).isoformat(),
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (data_dir / "evolve-state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

        result = trigger_engine.evaluate_session_end()
        assert result.triggered is False

        # No pending file written
        assert not (data_dir / "pending-trigger.json").exists()

        # Restore state sees nothing
        data = trigger_engine.read_and_delete_pending_trigger()
        assert data is None

    def test_audit_overdue_triggers(self, data_dir):
        """audit overdue → /rl-anything:audit を提案。"""
        state = {
            "last_run_timestamp": datetime.now(timezone.utc).isoformat(),
            # No last_audit_timestamp → overdue
        }
        (data_dir / "evolve-state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

        result = trigger_engine.evaluate_session_end()
        assert result.triggered is True
        assert "audit_overdue" in result.details.get("all_reasons", [])
        assert "/rl-anything:audit" in result.message

    def test_corrections_flow(self, data_dir):
        """corrections 閾値到達 → メッセージ出力。"""
        (data_dir / "evolve-state.json").write_text(
            json.dumps({"last_run_timestamp": "2025-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        now = datetime.now(timezone.utc).isoformat()
        corrections = [
            json.dumps({"timestamp": now, "last_skill": "my-skill"})
            for _ in range(10)
        ]
        (data_dir / "corrections.jsonl").write_text(
            "\n".join(corrections), encoding="utf-8"
        )

        result = trigger_engine.evaluate_corrections()
        assert result.triggered is True
        assert "my-skill" in result.message

    def test_snooze_suppresses_delivery(self, data_dir):
        """スヌーズ中は pending-trigger を配信しない（ファイルは残る）。"""
        # pending-trigger を作成
        pending = {
            "triggered": True,
            "reason": "days_elapsed",
            "action": "/rl-anything:evolve",
            "message": "前回 evolve から 15.6 日経過",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (data_dir / "pending-trigger.json").write_text(
            json.dumps(pending), encoding="utf-8"
        )

        # スヌーズ設定（24時間後まで）
        trigger_engine.snooze_trigger(hours=24)
        assert (data_dir / "trigger-snooze.json").exists()

        # 配信されない（None）+ ファイルが残る
        data = trigger_engine.read_and_delete_pending_trigger()
        assert data is None
        assert (data_dir / "pending-trigger.json").exists()

    def test_snooze_expired_delivers(self, data_dir):
        """スヌーズ期限切れなら通常通り配信する。"""
        pending = {
            "triggered": True,
            "reason": "days_elapsed",
            "action": "/rl-anything:evolve",
            "message": "前回 evolve から 15.6 日経過",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (data_dir / "pending-trigger.json").write_text(
            json.dumps(pending), encoding="utf-8"
        )

        # 過去のスヌーズ（既に期限切れ）
        expired = {
            "snoozed_until": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }
        (data_dir / "trigger-snooze.json").write_text(
            json.dumps(expired), encoding="utf-8"
        )

        # 期限切れなので配信される
        data = trigger_engine.read_and_delete_pending_trigger()
        assert data is not None
        assert data["triggered"] is True
        # スヌーズファイルもクリーンアップ
        assert not (data_dir / "trigger-snooze.json").exists()

    def test_snooze_clears_on_evolve_run(self, data_dir):
        """evolve 実行でスヌーズが自動解除される。"""
        trigger_engine.snooze_trigger(hours=48)
        assert (data_dir / "trigger-snooze.json").exists()

        trigger_engine.clear_snooze()
        assert not (data_dir / "trigger-snooze.json").exists()

    def test_cooldown_prevents_repeated_trigger(self, data_dir):
        """クールダウン中は同一条件の再トリガーを防止。"""
        old_ts = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        state = {
            "last_run_timestamp": old_ts,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (data_dir / "evolve-state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

        # First trigger fires
        r1 = trigger_engine.evaluate_session_end()
        assert r1.triggered is True

        # Second trigger is blocked by cooldown
        r2 = trigger_engine.evaluate_session_end()
        assert r2.triggered is False
