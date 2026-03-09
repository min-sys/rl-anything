"""trigger_engine のユニットテスト。"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trigger_engine import (
    DEFAULT_TRIGGER_CONFIG,
    TriggerResult,
    _build_bloat_message,
    _count_sessions_since,
    _deep_merge,
    _evaluate_bloat,
    _evaluate_approval_rate_decline,
    _evaluate_self_evolution,
    _is_in_cooldown,
    _record_trigger,
    evaluate_corrections,
    evaluate_session_end,
    load_trigger_config,
    read_and_delete_pending_trigger,
    write_pending_trigger,
)


@pytest.fixture
def data_dir(tmp_path):
    """DATA_DIR を tmp_path に差し替える。"""
    with mock.patch("trigger_engine.DATA_DIR", tmp_path), mock.patch(
        "trigger_engine.EVOLVE_STATE_FILE", tmp_path / "evolve-state.json"
    ), mock.patch(
        "trigger_engine.PENDING_TRIGGER_FILE", tmp_path / "pending-trigger.json"
    ):
        yield tmp_path


def _write_state(data_dir: Path, state: dict) -> None:
    (data_dir / "evolve-state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )


def _write_sessions(data_dir: Path, records: list[dict]) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    (data_dir / "sessions.jsonl").write_text("\n".join(lines), encoding="utf-8")


def _write_corrections(data_dir: Path, records: list[dict]) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    (data_dir / "corrections.jsonl").write_text("\n".join(lines), encoding="utf-8")


# --- load_trigger_config ---


class TestLoadTriggerConfig:
    def test_default_when_no_config(self, data_dir):
        config = load_trigger_config({})
        assert config["enabled"] is True
        assert config["triggers"]["session_end"]["min_sessions"] == 10

    def test_user_override(self, data_dir):
        state = {"trigger_config": {"triggers": {"session_end": {"min_sessions": 5}}}}
        config = load_trigger_config(state)
        assert config["triggers"]["session_end"]["min_sessions"] == 5
        # Other defaults preserved
        assert config["triggers"]["session_end"]["max_days"] == 7
        assert config["cooldown_hours"] == 24

    def test_disabled(self, data_dir):
        state = {"trigger_config": {"enabled": False}}
        config = load_trigger_config(state)
        assert config["enabled"] is False


# --- Cooldown ---


class TestCooldown:
    def test_within_cooldown(self):
        now = datetime.now(timezone.utc)
        state = {
            "trigger_history": [
                {
                    "reason": "session_count",
                    "timestamp": now.isoformat(),
                }
            ]
        }
        assert _is_in_cooldown(state, "session_count", 24) is True

    def test_cooldown_expired(self):
        old = datetime.now(timezone.utc) - timedelta(hours=25)
        state = {
            "trigger_history": [
                {
                    "reason": "session_count",
                    "timestamp": old.isoformat(),
                }
            ]
        }
        assert _is_in_cooldown(state, "session_count", 24) is False

    def test_different_reason_not_affected(self):
        now = datetime.now(timezone.utc)
        state = {
            "trigger_history": [
                {"reason": "days_elapsed", "timestamp": now.isoformat()}
            ]
        }
        assert _is_in_cooldown(state, "session_count", 24) is False


# --- History recording and pruning ---


class TestHistoryRecording:
    def test_record_trigger(self):
        state = {"trigger_history": []}
        result = TriggerResult(
            triggered=True, reason="session_count", action="/rl-anything:evolve"
        )
        state = _record_trigger(state, result)
        assert len(state["trigger_history"]) == 1
        assert state["trigger_history"][0]["reason"] == "session_count"

    def test_pruning(self):
        state = {
            "trigger_history": [
                {"reason": "x", "timestamp": "2025-01-01T00:00:00+00:00"}
            ]
            * 105
        }
        result = TriggerResult(triggered=True, reason="y", action="test")
        state = _record_trigger(state, result)
        assert len(state["trigger_history"]) <= 100


# --- evaluate_session_end ---


class TestEvaluateSessionEnd:
    def test_session_count_threshold(self, data_dir):
        last_run = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        _write_state(data_dir, {"last_run_timestamp": last_run})
        # Write 10 sessions after last_run
        sessions = [
            {
                "session_id": f"s{i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(10)
        ]
        _write_sessions(data_dir, sessions)

        result = evaluate_session_end()
        assert result.triggered is True
        assert "session_count" in result.details.get("all_reasons", [])

    def test_days_elapsed_threshold(self, data_dir):
        last_run = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        _write_state(data_dir, {"last_run_timestamp": last_run})

        result = evaluate_session_end()
        assert result.triggered is True
        assert "days_elapsed" in result.details.get("all_reasons", [])

    def test_no_trigger(self, data_dir):
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_state(
            data_dir,
            {
                "last_run_timestamp": last_run,
                "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        result = evaluate_session_end()
        assert result.triggered is False

    def test_first_run_lower_threshold(self, data_dir):
        """evolve-state.json が空の場合、min_sessions=3 で判定。"""
        sessions = [
            {
                "session_id": f"s{i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(3)
        ]
        _write_sessions(data_dir, sessions)

        result = evaluate_session_end(state={})
        assert result.triggered is True

    def test_disabled_config(self, data_dir):
        state = {"trigger_config": {"enabled": False}}
        _write_state(data_dir, state)

        result = evaluate_session_end(state)
        assert result.triggered is False

    def test_audit_overdue_no_previous(self, data_dir):
        """last_audit_timestamp がない場合は audit overdue。"""
        _write_state(data_dir, {"last_run_timestamp": datetime.now(timezone.utc).isoformat()})

        result = evaluate_session_end()
        assert result.triggered is True
        assert "audit_overdue" in result.details.get("all_reasons", [])

    def test_audit_overdue_expired(self, data_dir):
        old_audit = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        _write_state(
            data_dir,
            {
                "last_run_timestamp": datetime.now(timezone.utc).isoformat(),
                "last_audit_timestamp": old_audit,
            },
        )

        result = evaluate_session_end()
        assert result.triggered is True
        assert "audit_overdue" in result.details.get("all_reasons", [])

    def test_audit_not_overdue(self, data_dir):
        recent_audit = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        _write_state(
            data_dir,
            {
                "last_run_timestamp": (
                    datetime.now(timezone.utc) - timedelta(hours=1)
                ).isoformat(),
                "last_audit_timestamp": recent_audit,
            },
        )

        result = evaluate_session_end()
        assert result.triggered is False


# --- evaluate_corrections ---


class TestEvaluateCorrections:
    def test_threshold_reached(self, data_dir):
        _write_state(data_dir, {"last_run_timestamp": "2025-01-01T00:00:00+00:00"})
        corrections = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_skill": "my-skill",
            }
            for _ in range(10)
        ]
        _write_corrections(data_dir, corrections)

        result = evaluate_corrections()
        assert result.triggered is True
        assert result.reason == "corrections_threshold"
        assert "my-skill" in result.details.get("top_skills", [])

    def test_below_threshold(self, data_dir):
        _write_state(data_dir, {"last_run_timestamp": "2025-01-01T00:00:00+00:00"})
        corrections = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_skill": "s",
            }
            for _ in range(5)
        ]
        _write_corrections(data_dir, corrections)

        result = evaluate_corrections()
        assert result.triggered is False

    def test_no_skill_fallback(self, data_dir):
        _write_state(data_dir, {"last_run_timestamp": "2025-01-01T00:00:00+00:00"})
        corrections = [
            {"timestamp": datetime.now(timezone.utc).isoformat(), "last_skill": ""}
            for _ in range(10)
        ]
        _write_corrections(data_dir, corrections)

        result = evaluate_corrections()
        assert result.triggered is True
        assert result.action == "/rl-anything:evolve"

    def test_cooldown_blocks(self, data_dir):
        now = datetime.now(timezone.utc)
        _write_state(
            data_dir,
            {
                "last_run_timestamp": "2025-01-01T00:00:00+00:00",
                "trigger_history": [
                    {
                        "reason": "corrections_threshold",
                        "timestamp": now.isoformat(),
                    }
                ],
            },
        )
        corrections = [
            {"timestamp": now.isoformat(), "last_skill": "s"} for _ in range(15)
        ]
        _write_corrections(data_dir, corrections)

        result = evaluate_corrections()
        assert result.triggered is False
        assert result.reason == "cooldown"

    def test_multiple_skills_top3(self, data_dir):
        _write_state(data_dir, {"last_run_timestamp": "2025-01-01T00:00:00+00:00"})
        now = datetime.now(timezone.utc).isoformat()
        corrections = []
        # skill-a: 5, skill-b: 3, skill-c: 2, skill-d: 1
        for skill, count in [("skill-a", 5), ("skill-b", 3), ("skill-c", 2), ("skill-d", 1)]:
            for _ in range(count):
                corrections.append({"timestamp": now, "last_skill": skill})
        _write_corrections(data_dir, corrections)

        result = evaluate_corrections()
        assert result.triggered is True
        top = result.details["top_skills"]
        assert len(top) == 3
        assert top[0] == "skill-a"


# --- Bloat trigger ---


def _bloat_result(warnings: list[dict]) -> dict:
    return {"warnings": warnings, "warning_count": len(warnings)}


def _memory_warning(lines=180, threshold=150):
    return {"type": "memory", "file": "MEMORY.md", "lines": lines, "threshold": threshold}


def _rules_warning(count=120, threshold=100):
    return {"type": "rules_count", "count": count, "threshold": threshold}


def _skills_warning(count=40, threshold=30):
    return {"type": "skills_count", "count": count, "threshold": threshold}


def _claude_md_warning(lines=200, threshold=150):
    return {"type": "claude_md", "file": "CLAUDE.md", "lines": lines, "threshold": threshold}


class TestBloatTrigger:
    """3.1 bloat トリガーのテスト"""

    def test_memory_exceeds_threshold(self, data_dir):
        """MEMORY.md 超過で bloat トリガー発火。"""
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_state(data_dir, {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        })
        bloat = _bloat_result([_memory_warning()])
        with mock.patch("trigger_engine._evaluate_bloat", return_value=bloat):
            result = evaluate_session_end(project_dir="/test/project")
        assert result.triggered is True
        assert "bloat" in result.details.get("all_reasons", [])
        assert "MEMORY.md" in result.message

    def test_rules_exceeds_threshold(self, data_dir):
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_state(data_dir, {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        })
        bloat = _bloat_result([_rules_warning()])
        with mock.patch("trigger_engine._evaluate_bloat", return_value=bloat):
            result = evaluate_session_end(project_dir="/test/project")
        assert result.triggered is True
        assert "bloat" in result.details.get("all_reasons", [])
        assert "rules" in result.message

    def test_skills_exceeds_threshold(self, data_dir):
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_state(data_dir, {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        })
        bloat = _bloat_result([_skills_warning()])
        with mock.patch("trigger_engine._evaluate_bloat", return_value=bloat):
            result = evaluate_session_end(project_dir="/test/project")
        assert result.triggered is True
        assert "skills" in result.message

    def test_claude_md_exceeds_threshold(self, data_dir):
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_state(data_dir, {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        })
        bloat = _bloat_result([_claude_md_warning()])
        with mock.patch("trigger_engine._evaluate_bloat", return_value=bloat):
            result = evaluate_session_end(project_dir="/test/project")
        assert result.triggered is True
        assert "CLAUDE.md" in result.message

    def test_multiple_bloat_types(self, data_dir):
        """複数種別同時検出。"""
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_state(data_dir, {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        })
        bloat = _bloat_result([_memory_warning(), _rules_warning(), _skills_warning(), _claude_md_warning()])
        with mock.patch("trigger_engine._evaluate_bloat", return_value=bloat):
            result = evaluate_session_end(project_dir="/test/project")
        assert result.triggered is True
        assert len(result.details["bloat_warnings"]) == 4
        assert "MEMORY.md" in result.message
        assert "rules" in result.message

    def test_no_bloat_detected(self, data_dir):
        """閾値以内では bloat トリガーは発火しない。"""
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_state(data_dir, {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        })
        with mock.patch("trigger_engine._evaluate_bloat", return_value=None):
            result = evaluate_session_end(project_dir="/test/project")
        assert result.triggered is False

    def test_bloat_check_error(self, data_dir):
        """bloat_check() 例外時はサイレントスキップ。"""
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_state(data_dir, {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        })
        with mock.patch("trigger_engine._evaluate_bloat", return_value=None):
            result = evaluate_session_end(project_dir="/test/project")
        assert result.triggered is False

    def test_import_error_handled(self):
        """ImportError 時は None を返す。"""
        config = {"triggers": {"bloat": {"enabled": True}}}
        with mock.patch.dict("sys.modules", {"scripts.bloat_control": None}):
            result = _evaluate_bloat("/test", config)
        assert result is None

    def test_project_dir_none_skips_bloat(self, data_dir):
        """project_dir=None の場合は bloat 評価をスキップ。"""
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_state(data_dir, {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        })
        with mock.patch("trigger_engine._evaluate_bloat") as mock_bloat:
            result = evaluate_session_end(project_dir=None)
        mock_bloat.assert_not_called()


class TestBloatCooldown:
    """3.2 bloat トリガーのクールダウンテスト。"""

    def test_bloat_cooldown_blocks(self, data_dir):
        now = datetime.now(timezone.utc)
        _write_state(data_dir, {
            "last_run_timestamp": (now - timedelta(hours=1)).isoformat(),
            "last_audit_timestamp": now.isoformat(),
            "trigger_history": [
                {"reason": "bloat", "timestamp": now.isoformat()},
            ],
        })
        # bloat は cooldown 内なので呼ばれても発火しない
        with mock.patch("trigger_engine._evaluate_bloat") as mock_bloat:
            result = evaluate_session_end(project_dir="/test/project")
        mock_bloat.assert_not_called()
        assert result.triggered is False

    def test_bloat_cooldown_expired(self, data_dir):
        now = datetime.now(timezone.utc)
        _write_state(data_dir, {
            "last_run_timestamp": (now - timedelta(hours=1)).isoformat(),
            "last_audit_timestamp": now.isoformat(),
            "trigger_history": [
                {"reason": "bloat", "timestamp": (now - timedelta(hours=25)).isoformat()},
            ],
        })
        bloat = _bloat_result([_memory_warning()])
        with mock.patch("trigger_engine._evaluate_bloat", return_value=bloat):
            result = evaluate_session_end(project_dir="/test/project")
        assert result.triggered is True
        assert "bloat" in result.details.get("all_reasons", [])


class TestBloatWithSessionCount:
    """3.3 bloat + session_count 複合トリガーのテスト。"""

    def test_both_triggers_fire(self, data_dir):
        last_run = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        _write_state(data_dir, {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
        })
        sessions = [
            {"session_id": f"s{i}", "timestamp": datetime.now(timezone.utc).isoformat()}
            for i in range(10)
        ]
        _write_sessions(data_dir, sessions)
        bloat = _bloat_result([_memory_warning()])
        with mock.patch("trigger_engine._evaluate_bloat", return_value=bloat):
            result = evaluate_session_end(project_dir="/test/project")
        assert result.triggered is True
        all_reasons = result.details.get("all_reasons", [])
        assert "session_count" in all_reasons
        assert "bloat" in all_reasons


class TestBloatDisabled:
    """3.4 bloat trigger disabled テスト。"""

    def test_bloat_disabled_in_config(self, data_dir):
        last_run = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        state = {
            "last_run_timestamp": last_run,
            "last_audit_timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger_config": {"triggers": {"bloat": {"enabled": False}}},
        }
        _write_state(data_dir, state)
        with mock.patch("trigger_engine._evaluate_bloat") as mock_bloat:
            # _evaluate_bloat will check config internally, but since cooldown check
            # happens first and _evaluate_bloat is called only if not in cooldown,
            # we need to let the real function check config
            mock_bloat.return_value = None
            result = evaluate_session_end(project_dir="/test/project")
        # _evaluate_bloat should return None since disabled
        assert "bloat" not in result.details.get("all_reasons", [])

    def test_bloat_disabled_via_evaluate_bloat(self):
        """_evaluate_bloat が config disabled で None を返す。"""
        config = {"triggers": {"bloat": {"enabled": False}}}
        result = _evaluate_bloat("/test", config)
        assert result is None


class TestBuildBloatMessage:
    def test_single_type(self):
        msg = _build_bloat_message({"warnings": [_memory_warning(180, 150)]})
        assert "MEMORY.md" in msg
        assert "180/150" in msg

    def test_multiple_types(self):
        msg = _build_bloat_message({"warnings": [_memory_warning(), _rules_warning()]})
        assert "MEMORY.md" in msg
        assert "rules" in msg

    def test_all_types(self):
        msg = _build_bloat_message({"warnings": [
            _memory_warning(), _rules_warning(), _skills_warning(), _claude_md_warning()
        ]})
        assert "MEMORY.md" in msg
        assert "rules" in msg
        assert "skills" in msg
        assert "CLAUDE.md" in msg


# --- Pending trigger file ---


class TestPendingTrigger:
    def test_write_and_read(self, data_dir):
        result = TriggerResult(
            triggered=True,
            reason="session_count",
            action="/rl-anything:evolve",
            message="test message",
        )
        write_pending_trigger(result)
        assert (data_dir / "pending-trigger.json").exists()

        data = read_and_delete_pending_trigger()
        assert data is not None
        assert data["reason"] == "session_count"
        assert not (data_dir / "pending-trigger.json").exists()

    def test_read_nonexistent(self, data_dir):
        assert read_and_delete_pending_trigger() is None

    def test_read_corrupt_file(self, data_dir):
        (data_dir / "pending-trigger.json").write_text("invalid json")
        assert read_and_delete_pending_trigger() is None
        assert not (data_dir / "pending-trigger.json").exists()


# --- Self-evolution trigger ---


def _write_outcomes(data_dir, outcomes):
    f = data_dir / "remediation-outcomes.jsonl"
    f.write_text("\n".join(json.dumps(o) for o in outcomes) + "\n")


def _make_outcome(
    issue_type="stale_ref",
    result="success",
    user_decision="approved",
    confidence_score=0.95,
    category="auto_fixable",
):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "issue_type": issue_type,
        "result": result,
        "user_decision": user_decision,
        "confidence_score": confidence_score,
        "category": category,
        "impact_scope": "file",
        "action": "test",
        "rationale": "test",
        "file": "test.md",
    }


class TestSelfEvolutionTrigger:
    """6.1-6.3: Self-evolution トリガーのテスト。"""

    def test_fp_threshold_reached(self, data_dir):
        """false positive rate が閾値を超えるとトリガー発火。"""
        outcomes = [_make_outcome() for _ in range(7)]
        outcomes += [_make_outcome(user_decision="rejected", result="rejected") for _ in range(5)]
        _write_outcomes(data_dir, outcomes)
        _write_state(data_dir, {
            "trigger_config": {
                "self_evolution": {
                    "false_positive_rate_threshold": 0.3,
                    "min_outcomes_per_type": 10,
                },
            },
        })

        result = _evaluate_self_evolution()
        assert result.triggered is True
        assert result.reason == "self_evolution"

    def test_fp_below_threshold(self, data_dir):
        """false positive rate が閾値未満ではトリガーしない。"""
        outcomes = [_make_outcome() for _ in range(10)]
        outcomes += [_make_outcome(user_decision="rejected", result="rejected") for _ in range(1)]
        _write_outcomes(data_dir, outcomes)
        _write_state(data_dir, {
            "trigger_config": {
                "self_evolution": {
                    "false_positive_rate_threshold": 0.3,
                    "min_outcomes_per_type": 10,
                },
            },
        })

        result = _evaluate_self_evolution()
        assert result.triggered is False

    def test_self_evolution_cooldown(self, data_dir):
        """self-evolution 72h クールダウンが機能する。"""
        now = datetime.now(timezone.utc)
        outcomes = [_make_outcome(user_decision="rejected", result="rejected") for _ in range(10)]
        _write_outcomes(data_dir, outcomes)
        _write_state(data_dir, {
            "trigger_config": {
                "self_evolution": {
                    "false_positive_rate_threshold": 0.3,
                    "min_outcomes_per_type": 5,
                    "self_evolution_cooldown_hours": 72,
                },
            },
            "trigger_history": [
                {"reason": "self_evolution", "timestamp": now.isoformat()},
            ],
        })

        result = _evaluate_self_evolution()
        assert result.triggered is False

    def test_insufficient_samples(self, data_dir):
        """サンプル不足ではトリガーしない。"""
        outcomes = [_make_outcome(user_decision="rejected", result="rejected") for _ in range(3)]
        _write_outcomes(data_dir, outcomes)
        _write_state(data_dir, {
            "trigger_config": {
                "self_evolution": {
                    "min_outcomes_per_type": 10,
                },
            },
        })

        result = _evaluate_self_evolution()
        assert result.triggered is False


class TestApprovalRateDeclineTrigger:
    """6.2: 承認率低下トリガーのテスト。"""

    def test_decline_detected(self, data_dir):
        """承認率が閾値以上低下するとトリガー発火。"""
        previous = [_make_outcome() for _ in range(10)]
        recent = [_make_outcome(user_decision="rejected", result="rejected") for _ in range(10)]
        _write_outcomes(data_dir, previous + recent)
        _write_state(data_dir, {
            "trigger_config": {
                "self_evolution": {
                    "approval_rate_decline_threshold": 0.2,
                    "decline_sample_size": 10,
                    "self_evolution_cooldown_hours": 72,
                },
            },
        })

        result = _evaluate_approval_rate_decline()
        assert result.triggered is True
        assert result.reason == "approval_rate_decline"

    def test_stable_rate(self, data_dir):
        """承認率が安定していればトリガーしない。"""
        outcomes = [_make_outcome() for _ in range(20)]
        _write_outcomes(data_dir, outcomes)
        _write_state(data_dir, {
            "trigger_config": {
                "self_evolution": {
                    "approval_rate_decline_threshold": 0.2,
                    "decline_sample_size": 10,
                },
            },
        })

        result = _evaluate_approval_rate_decline()
        assert result.triggered is False

    def test_insufficient_data(self, data_dir):
        """データ不足ではトリガーしない。"""
        outcomes = [_make_outcome() for _ in range(5)]
        _write_outcomes(data_dir, outcomes)
        _write_state(data_dir, {})

        result = _evaluate_approval_rate_decline()
        assert result.triggered is False
