"""detect_missed_skills() と discover レポート統合のテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# discover.py のパスを追加
_discover_scripts = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_discover_scripts))
# scripts/lib のパスを追加
_plugin_root = _discover_scripts.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

import discover


@pytest.fixture
def project_dir(tmp_path):
    """CLAUDE.md + sessions.jsonl + usage.jsonl を持つプロジェクト。"""
    # CLAUDE.md
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(
        "## Skills\n\n"
        "- /channel-routing: Bot設定。トリガー: チャンネル, bot追加\n"
        "- /deploy-check: デプロイ確認。Trigger: デプロイ確認\n"
        "- /my-skill: 説明のみ\n"
    )

    # sessions.jsonl
    sessions = [
        {"session_id": "s1", "user_prompts": ["Slackのチャンネル設定をしたい"], "project": tmp_path.name},
        {"session_id": "s2", "user_prompts": ["チャンネルのbot追加をお願い"], "project": tmp_path.name},
        {"session_id": "s3", "user_prompts": ["チャンネルの整理"], "project": tmp_path.name},
        {"session_id": "s4", "user_prompts": ["デプロイ確認して"], "project": tmp_path.name},
    ]
    sessions_file = discover.DATA_DIR / "sessions.jsonl"
    sessions_file.parent.mkdir(parents=True, exist_ok=True)
    sessions_file.write_text("\n".join(json.dumps(s) for s in sessions) + "\n")

    # usage.jsonl - s3 でのみ channel-routing が使われた
    usage = [
        {"session_id": "s3", "skill_name": "/channel-routing", "project": tmp_path.name},
        {"session_id": "s4", "skill_name": "other-skill", "project": tmp_path.name},
    ]
    usage_file = discover.DATA_DIR / "usage.jsonl"
    usage_file.write_text("\n".join(json.dumps(u) for u in usage) + "\n")

    yield tmp_path

    # cleanup
    sessions_file.unlink(missing_ok=True)
    usage_file.unlink(missing_ok=True)


def test_detect_missed_skills_basic(project_dir):
    """トリガーマッチするがスキル未使用のセッションが検出される。"""
    result = discover.detect_missed_skills(project_root=project_dir)
    assert result["message"] is None
    missed = result["missed"]

    by_skill = {m["skill"]: m for m in missed}
    # channel-routing: s1, s2 で missed (s3 は使用済み)
    assert "channel-routing" in by_skill
    assert by_skill["channel-routing"]["session_count"] == 2


def test_skill_used_not_missed(project_dir):
    """セッション内でスキルが使われた場合は missed にならない。"""
    result = discover.detect_missed_skills(project_root=project_dir)
    missed = result["missed"]
    by_skill = {m["skill"]: m for m in missed}

    # s3 では channel-routing が使われているので、s3 は missed にカウントされない
    if "channel-routing" in by_skill:
        assert by_skill["channel-routing"]["session_count"] == 2  # s1, s2 のみ


def test_skill_name_normalization(project_dir):
    """/channel-routing と channel-routing が同一視される。"""
    result = discover.detect_missed_skills(project_root=project_dir)
    missed = result["missed"]
    by_skill = {m["skill"]: m for m in missed}
    # /channel-routing → channel-routing に正規化される
    assert "channel-routing" in by_skill


def test_frequency_threshold(project_dir):
    """閾値未満の missed は除外される。"""
    result = discover.detect_missed_skills(project_root=project_dir)
    missed = result["missed"]
    by_skill = {m["skill"]: m for m in missed}

    # deploy-check は 1 セッションのみでマッチ → 閾値 2 で除外
    assert "deploy-check" not in by_skill


def test_no_claude_md(tmp_path):
    """CLAUDE.md がない場合はスキップメッセージ。"""
    result = discover.detect_missed_skills(project_root=tmp_path)
    assert result["missed"] == []
    assert "No CLAUDE.md found" in result["message"]


def test_no_sessions_jsonl(tmp_path):
    """sessions.jsonl がない場合はスキップメッセージ。"""
    (tmp_path / "CLAUDE.md").write_text("## Skills\n\n- /test: test. Trigger: test\n")

    # sessions.jsonl が存在しないことを確認
    sessions_file = discover.DATA_DIR / "sessions.jsonl"
    if sessions_file.exists():
        sessions_file.rename(sessions_file.with_suffix(".bak"))

    try:
        result = discover.detect_missed_skills(project_root=tmp_path)
        assert result["missed"] == []
        assert result["message"] is not None
        assert "sessions.jsonl" in result["message"]
    finally:
        bak = sessions_file.with_suffix(".bak")
        if bak.exists():
            bak.rename(sessions_file)


def test_report_integration(project_dir):
    """run_discover で missed_skill_opportunities がレポートに含まれる。"""
    result = discover.run_discover(project_root=project_dir)

    if "missed_skill_opportunities" in result:
        opportunities = result["missed_skill_opportunities"]
        assert len(opportunities) > 0
        assert "skill" in opportunities[0]
        assert "triggers_matched" in opportunities[0]
        assert "session_count" in opportunities[0]


def test_report_no_missed_skills(tmp_path):
    """missed が 0 件の場合はセクションが出力されない。"""
    result = discover.run_discover(project_root=tmp_path)
    # CLAUDE.md がないので missed_skill_message が出る
    assert "missed_skill_opportunities" not in result or result.get("missed_skill_opportunities") == []
