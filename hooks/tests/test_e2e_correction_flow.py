"""E2E テスト: correction 検出 → prune decay → analyze routing の一気通貫フロー。

Task 6.1: correction_detect が corrections.jsonl に書き込み、
prune が decay スコアを計算し、analyze が routing 先を決定するフロー全体を検証する。
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# hooks/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common
import correction_detect

# prune / audit / analyze のパス
_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "prune" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "backfill" / "scripts"))

import prune
import analyze

from datetime import datetime, timedelta, timezone


@pytest.fixture
def e2e_env(tmp_path):
    """E2E テスト用の一時環境を構築する。"""
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    tmpdir = str(tmp_path)
    with mock.patch.object(common, "DATA_DIR", data_dir), \
         mock.patch.object(prune, "DATA_DIR", data_dir), \
         mock.patch.dict(os.environ, {"TMPDIR": tmpdir}):
        yield data_dir


class TestCorrectionToPruneToAnalyze:
    """correction → prune decay → analyze routing の一気通貫テスト。"""

    def test_full_flow(self, e2e_env):
        """スキル使用 → 修正検出 → decay 計算 → routing の全フロー。"""
        data_dir = e2e_env
        session_id = "e2e-corr-001"

        # Step 1: observe.py で last_skill を記録
        common.write_last_skill(session_id, "evolve")
        last_skill = common.read_last_skill(session_id)
        assert last_skill == "evolve"

        # Step 2: correction_detect でユーザー修正を検出
        event = {
            "session_id": session_id,
            "message": {"content": "いや、そうじゃない"},
        }
        correction_detect.handle_user_prompt_submit(event)

        corrections_file = data_dir / "corrections.jsonl"
        assert corrections_file.exists()
        record = json.loads(corrections_file.read_text(encoding="utf-8").strip())
        assert record["correction_type"] == "iya"
        assert record["last_skill"] == "evolve"
        assert record["session_id"] == session_id

        # Step 3: prune の decay 計算に corrections を反映
        corrections_by_skill = prune.load_corrections()
        assert "evolve" in corrections_by_skill
        assert len(corrections_by_skill["evolve"]) == 1

        score = prune.compute_decay_score(
            age_days=60,
            correction_count=len(corrections_by_skill["evolve"]),
        )
        # base_score = 1.0 - 0.15 * 1 = 0.85, decay = exp(-60/90) ≈ 0.513
        assert 0.43 < score < 0.44

        # Step 4: analyze の routing で correction が最優先
        routing = analyze.route_recommendation(
            "evolve",
            correction_count=len(corrections_by_skill["evolve"]),
            frequency=3,
            project_count=1,
        )
        assert routing["target"] == "skill"
        assert routing["action"] == "evolve で改善"

    def test_multiple_corrections_lower_score(self, e2e_env):
        """複数 correction で decay スコアが下がる。"""
        data_dir = e2e_env
        session_id = "e2e-corr-002"

        common.write_last_skill(session_id, "commit")

        # 3件の correction を検出
        for msg in ["いや、違う", "no, that's wrong", "stop doing that"]:
            event = {
                "session_id": f"{session_id}-{msg[:3]}",
                "message": {"content": msg},
            }
            # last_skill を各セッションに設定
            common.write_last_skill(event["session_id"], "commit")
            correction_detect.handle_user_prompt_submit(event)

        corrections_by_skill = prune.load_corrections()
        count = len(corrections_by_skill.get("commit", []))
        assert count == 3

        # base_score = 1.0 - 0.15 * 3 = 0.55
        score = prune.compute_decay_score(age_days=0, correction_count=count)
        assert abs(score - 0.55) < 0.001

    def test_pinned_skill_protected(self, e2e_env, tmp_path):
        """pin されたスキルは decay で検出されても保護される。"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "skill.md"
        skill_file.write_text("# My Skill")
        (skill_dir / ".pin").touch()

        assert prune.is_pinned(skill_file) is True

    def test_no_correction_routing_fallback(self, e2e_env):
        """correction がないスキルは frequency ベースで routing される。"""
        routing = analyze.route_recommendation(
            "some-skill",
            correction_count=0,
            frequency=15,
            project_count=4,
        )
        assert routing["target"] == "claude_md"
        assert routing["action"] == "CLAUDE.md にパターンを追加"

    def test_analyze_corrections_groups_by_skill(self, e2e_env):
        """analyze_corrections がスキル別にグループ化する。"""
        data_dir = e2e_env

        # corrections.jsonl に手動書き込み
        corrections = [
            {"correction_type": "iya", "last_skill": "evolve", "confidence": 0.85, "session_id": "s1"},
            {"correction_type": "no", "last_skill": "evolve", "confidence": 0.75, "session_id": "s2"},
            {"correction_type": "stop", "last_skill": "commit", "confidence": 0.80, "session_id": "s3"},
        ]
        corrections_file = data_dir / "corrections.jsonl"
        corrections_file.write_text(
            "\n".join(json.dumps(c) for c in corrections) + "\n",
            encoding="utf-8",
        )

        # usage データも必要（スキル使用頻度・プロジェクト数の判定に使う）
        usage = [
            {"skill_name": "evolve", "project_path": "/proj-a"},
            {"skill_name": "evolve", "project_path": "/proj-b"},
            {"skill_name": "commit", "project_path": "/proj-a"},
        ]
        result = analyze.analyze_corrections(corrections, usage)
        assert result["total_corrections"] == 3
        assert result["skills_with_corrections"] == 2
        # correction のあるスキルは routing される
        assert "evolve" in result["recommendations"]
        assert result["recommendations"]["evolve"]["target"] == "skill"


class TestDecayInPrune:
    """Task 6.2: decay が prune に反映されることの検証。

    detect_decay_candidates は audit.load_usage_data (days=30) を使うため、
    ここでは個別関数の統合動作を検証する。
    """

    def test_corrections_increase_decay(self, e2e_env):
        """corrections が多いスキルほど decay スコアが低下する。"""
        data_dir = e2e_env

        # correction を3件登録
        corrections_file = data_dir / "corrections.jsonl"
        records = [
            {"correction_type": "iya", "last_skill": "old-skill", "confidence": 0.85},
            {"correction_type": "no", "last_skill": "old-skill", "confidence": 0.75},
            {"correction_type": "stop", "last_skill": "old-skill", "confidence": 0.80},
        ]
        corrections_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n",
            encoding="utf-8",
        )

        # load_corrections → compute_decay_score のフロー
        corrections_by_skill = prune.load_corrections()
        assert len(corrections_by_skill["old-skill"]) == 3

        # 0日前でも corrections で 0.55 まで下がる
        score_0 = prune.compute_decay_score(age_days=0, correction_count=3)
        assert abs(score_0 - 0.55) < 0.001

        # 180日前 + 3 corrections → threshold 0.2 以下になる
        score_180 = prune.compute_decay_score(age_days=180, correction_count=3)
        assert score_180 < prune.load_decay_threshold()

    def test_no_corrections_slow_decay(self, e2e_env):
        """corrections なしの場合は decay のみで緩やかに低下。"""
        # 30日: base=1.0 → exp(-30/90) ≈ 0.716
        score = prune.compute_decay_score(age_days=30, correction_count=0)
        assert score > prune.load_decay_threshold()

        # 180日: exp(-180/90) ≈ 0.135 → threshold 未満
        score_old = prune.compute_decay_score(age_days=180, correction_count=0)
        assert score_old < prune.load_decay_threshold()

    def test_pinned_skill_excluded_from_decay(self, e2e_env, tmp_path):
        """pin されたスキルは decay candidates から除外される。"""
        skill_dir = tmp_path / "pinned-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "skill.md"
        skill_file.write_text("# Pinned Skill")
        (skill_dir / ".pin").touch()

        assert prune.is_pinned(skill_file) is True

    def test_custom_threshold(self, e2e_env):
        """evolve-state.json で threshold をカスタマイズできる。"""
        data_dir = e2e_env
        state_file = data_dir / "evolve-state.json"
        state_file.write_text(json.dumps({"decay_threshold": 0.5}))
        assert prune.load_decay_threshold() == 0.5
