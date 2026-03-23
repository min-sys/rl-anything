"""gstack 連携機能のユニットテスト (TDD First)。

/cso × constitutional fitness, /retro global × audit, /autoplan × remediation 原則ベース判断
"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "rl"))
sys.path.insert(0, str(_plugin_root / "scripts" / "rl" / "fitness"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "evolve" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))


# =============================================================================
# 1. /cso × constitutional fitness 連携
# =============================================================================

class TestLoadCsoSignal:
    """_load_cso_signal() のテスト。"""

    def test_load_cso_signal_found(self, tmp_path):
        """skill-usage.jsonl に cso エントリがある場合 → 最新を返す。"""
        from constitutional import _load_cso_signal

        analytics_dir = tmp_path / "analytics"
        analytics_dir.mkdir()
        jsonl = analytics_dir / "skill-usage.jsonl"
        jsonl.write_text(
            '\n'.join([
                json.dumps({"skill": "retro", "outcome": "success", "ts": "2026-03-20T10:00:00Z"}),
                json.dumps({"skill": "cso", "outcome": "pass", "ts": "2026-03-21T10:00:00Z"}),
                json.dumps({"skill": "cso", "outcome": "fail", "ts": "2026-03-22T10:00:00Z"}),
            ]),
            encoding="utf-8",
        )
        result = _load_cso_signal(tmp_path)
        assert result is not None
        assert result["outcome"] == "fail"
        assert result["ts"] == "2026-03-22T10:00:00Z"

    def test_load_cso_signal_not_found(self, tmp_path):
        """cso エントリがない場合 → None。"""
        from constitutional import _load_cso_signal

        analytics_dir = tmp_path / "analytics"
        analytics_dir.mkdir()
        jsonl = analytics_dir / "skill-usage.jsonl"
        jsonl.write_text(
            json.dumps({"skill": "retro", "outcome": "success", "ts": "2026-03-20T10:00:00Z"}),
            encoding="utf-8",
        )
        result = _load_cso_signal(tmp_path)
        assert result is None

    def test_load_cso_signal_file_missing(self, tmp_path):
        """ファイル自体がない場合 → None (graceful degradation)。"""
        from constitutional import _load_cso_signal

        result = _load_cso_signal(tmp_path)
        assert result is None

    def test_load_cso_signal_malformed(self, tmp_path):
        """JSON が壊れている場合 → None (graceful degradation)。"""
        from constitutional import _load_cso_signal

        analytics_dir = tmp_path / "analytics"
        analytics_dir.mkdir()
        jsonl = analytics_dir / "skill-usage.jsonl"
        jsonl.write_text("not valid json {{{", encoding="utf-8")
        result = _load_cso_signal(tmp_path)
        assert result is None


# =============================================================================
# 2. /retro global × audit cross-project 連携
# =============================================================================

class TestLoadGlobalRetro:
    """_load_global_retro() のテスト。"""

    def test_load_global_retro_found(self, tmp_path):
        """global-*.json がある場合 → 最新の parsed dict を返す。"""
        from audit import _load_global_retro

        retros_dir = tmp_path / "retros"
        retros_dir.mkdir()
        old = {"type": "global", "date": "2026-03-20", "window": "7d",
               "projects": ["proj-a"], "totals": {"sessions": 10}}
        new = {"type": "global", "date": "2026-03-22", "window": "7d",
               "projects": ["proj-a", "proj-b"], "totals": {"sessions": 25, "streak": 3}}
        (retros_dir / "global-2026-03-20.json").write_text(
            json.dumps(old), encoding="utf-8")
        (retros_dir / "global-2026-03-22.json").write_text(
            json.dumps(new), encoding="utf-8")
        result = _load_global_retro(tmp_path)
        assert result is not None
        assert result["date"] == "2026-03-22"
        assert len(result["projects"]) == 2

    def test_load_global_retro_not_found(self, tmp_path):
        """ファイルがない場合 → None。"""
        from audit import _load_global_retro

        result = _load_global_retro(tmp_path)
        assert result is None

    def test_load_global_retro_malformed(self, tmp_path):
        """parse 不可の場合 → None。"""
        from audit import _load_global_retro

        retros_dir = tmp_path / "retros"
        retros_dir.mkdir()
        (retros_dir / "global-2026-03-22.json").write_text(
            "broken json {{", encoding="utf-8")
        result = _load_global_retro(tmp_path)
        assert result is None


# =============================================================================
# 3. /autoplan × remediation 原則ベース判断
# =============================================================================

class TestApplyPrinciples:
    """_apply_principles() のテスト。"""

    def test_apply_principles_matching(self):
        """stale_ref issue → completeness bonus 0.08。"""
        from remediation import _apply_principles

        issue = {"type": "stale_ref", "file": "CLAUDE.md", "detail": {}}
        bonus = _apply_principles(issue)
        assert bonus == pytest.approx(0.08)

    def test_apply_principles_multiple(self):
        """memory_duplicate → dry bonus 0.07。"""
        from remediation import _apply_principles

        issue = {"type": "memory_duplicate", "file": "MEMORY.md", "detail": {}}
        bonus = _apply_principles(issue)
        assert bonus == pytest.approx(0.07)

    def test_apply_principles_no_match(self):
        """該当原則なし → 0.0。"""
        from remediation import _apply_principles

        issue = {"type": "hooks_unconfigured", "file": "settings.json", "detail": {}}
        bonus = _apply_principles(issue)
        assert bonus == pytest.approx(0.0)


class TestPrinciplePromotion:
    """classify_issue() での原則ベース昇格テスト。"""

    def test_principle_promotion(self):
        """confidence 0.85 + bonus 0.08 = 0.93 → auto_fixable 昇格。"""
        from remediation import classify_issue

        # stale_ref は compute_confidence_score で 0.95 になるので、
        # line_limit_violation (excess <= 2, ratio <= 1.02 → 0.7) + completeness (0.08) ではなく
        # claudemd_phantom_ref (0.9 → auto_fixable は 0.9 以上だが原則なし) でもなく
        # split_candidate (0.70) + explicit_over_clever (0.05) = 0.75 ではまだ足りない
        # → 直接 confidence を制御するために calibration mock を使う
        # stale_memory は 0.6 → dry 0.07 = 0.67 では足りない
        # untagged_reference_candidates は 0.90 → 原則 pragmatic 0.06 → 0.96 → 既に auto_fixable
        #
        # アプローチ: split_candidate (0.70) は explicit_over_clever (0.05) で 0.75 = まだ proposable
        # line_limit_violation で ratio <= 1.10 → 0.7 + pragmatic 0.06 = 0.76 → proposable
        # ここでは TOOL_USAGE_RULE_CANDIDATE (0.85) + 原則外 → 原則テスト不可
        #
        # テスト方針: mock で confidence を制御
        issue = {"type": "stale_ref", "file": ".claude/rules/test.md", "detail": {}}
        with mock.patch("remediation.compute_confidence_score", return_value=0.85), \
             mock.patch("remediation.is_protected_skill", return_value=False):
            result = classify_issue(issue)
        # 0.85 + 0.08 (completeness for stale_ref) = 0.93 >= 0.9 → auto_fixable
        assert result["category"] == "auto_fixable"
        assert result["principle_promoted"] is True
        assert "completeness" in result["applied_principles"]

    def test_principle_no_promotion(self):
        """confidence 0.7 + bonus 0.05 = 0.75 → proposable 維持。"""
        from remediation import classify_issue

        issue = {"type": "split_candidate", "file": ".claude/rules/test.md", "detail": {}}
        with mock.patch("remediation.compute_confidence_score", return_value=0.7), \
             mock.patch("remediation.is_protected_skill", return_value=False):
            result = classify_issue(issue)
        # 0.7 + 0.05 (explicit_over_clever for split_candidate) = 0.75 < 0.9 → proposable
        assert result["category"] == "proposable"
        assert "principle_promoted" not in result

    def test_principle_high_confidence_skip(self):
        """confidence 0.91 → _apply_principles() 呼ばれない (既に auto_fixable)。"""
        from remediation import classify_issue

        issue = {"type": "stale_ref", "file": ".claude/rules/test.md", "detail": {}}
        with mock.patch("remediation.compute_confidence_score", return_value=0.91), \
             mock.patch("remediation.is_protected_skill", return_value=False), \
             mock.patch("remediation._apply_principles") as mock_apply:
            result = classify_issue(issue)
        # confidence 0.91 >= 0.9 → 原則チェックせず auto_fixable
        assert result["category"] == "auto_fixable"
        mock_apply.assert_not_called()
        assert "principle_promoted" not in result
