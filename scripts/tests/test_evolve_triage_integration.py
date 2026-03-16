"""evolve.py の skill triage 統合テスト + discover eval_set フィールドテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))


class TestDiscoverEvalSetFields:
    """Task 5.2: discover の eval_set_path/eval_set_status フィールド検証。"""

    def test_missed_skill_has_eval_set_fields(self, tmp_path):
        """eval set 未生成の missed skill にフィールドが付与される。"""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "skills" / "discover" / "scripts"))
        import discover
        from importlib import reload
        reload(discover)

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "## Skills\n"
            "- /test-skill: テスト。Trigger: テスト, test\n"
        )

        sessions = [
            {"session_id": f"s{i}", "user_prompts": ["テストを実行したい"], "project": tmp_path.name}
            for i in range(3)
        ]
        usage = []

        with mock.patch("telemetry_query.query_sessions", return_value=sessions), \
             mock.patch("telemetry_query.query_usage", return_value=usage):
            result = discover.detect_missed_skills(project_root=tmp_path)

        assert len(result["missed"]) > 0
        entry = result["missed"][0]
        assert "eval_set_path" in entry
        assert "eval_set_status" in entry

    def test_eval_set_status_available_when_file_exists(self, tmp_path):
        """eval set ファイルが存在する場合 status=available。"""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "skills" / "discover" / "scripts"))
        import discover
        from importlib import reload
        reload(discover)

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "## Skills\n"
            "- /test-skill: テスト。Trigger: テスト, test\n"
        )

        # eval set ファイルを作成
        eval_dir = Path.home() / ".claude" / "rl-anything" / "eval-sets"
        eval_dir.mkdir(parents=True, exist_ok=True)
        eval_file = eval_dir / "test-skill.json"
        eval_file.write_text("[]")

        sessions = [
            {"session_id": f"s{i}", "user_prompts": ["テストを実行したい"], "project": tmp_path.name}
            for i in range(3)
        ]
        usage = []

        try:
            with mock.patch("telemetry_query.query_sessions", return_value=sessions), \
                 mock.patch("telemetry_query.query_usage", return_value=usage):
                result = discover.detect_missed_skills(project_root=tmp_path)

            if result["missed"]:
                entry = result["missed"][0]
                assert entry["eval_set_status"] == "available"
                assert entry["eval_set_path"] is not None
        finally:
            if eval_file.exists():
                eval_file.unlink()


class TestEvolveTriageIntegration:
    """Task 4.5 + 6.1: evolve 統合テスト。"""

    def test_triage_phase_included_in_evolve(self):
        """triage 結果が phases["skill_triage"] に含まれる。"""
        from skill_triage import triage_all_skills

        result = triage_all_skills(
            sessions=[],
            usage=[],
            missed_skills=[],
            project_root=None,
        )
        # スキルなしの場合は skipped
        assert result["skipped"]

    def test_triage_issues_converted_to_schema(self):
        """triage 結果が issue_schema に変換できる。"""
        from issue_schema import make_skill_triage_issue, SKILL_TRIAGE_CREATE, SKILL_TRIAGE_UPDATE

        create_result = {
            "action": "CREATE",
            "skill": "new-skill",
            "confidence": 0.85,
            "evidence": {"missed_sessions": 5},
        }
        issue = make_skill_triage_issue(create_result)
        assert issue["type"] == SKILL_TRIAGE_CREATE
        assert issue["source"] == "skill_triage"

        update_result = {
            "action": "UPDATE",
            "skill": "existing-skill",
            "confidence": 0.75,
            "evidence": {"missed_sessions": 3, "near_miss_count": 2},
        }
        issue = make_skill_triage_issue(update_result)
        assert issue["type"] == SKILL_TRIAGE_UPDATE

    def test_ok_result_not_converted_to_issue(self):
        """OK 判定は issue に変換されない。"""
        from issue_schema import make_skill_triage_issue

        ok_result = {"action": "OK", "skill": "commit", "confidence": 0.90}
        issue = make_skill_triage_issue(ok_result)
        assert issue == {}

    def test_graceful_degradation_no_sessions(self, tmp_path):
        """データ不足時は triage がスキップされる。"""
        from skill_triage import triage_all_skills

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "## Skills\n"
            "- /my-skill: テスト。Trigger: test\n"
        )

        result = triage_all_skills(
            sessions=[],
            usage=[],
            missed_skills=[],
            project_root=tmp_path,
        )
        # スキルはあるがデータなし → skipped=False, OK に分類
        assert not result["skipped"]
        assert len(result["OK"]) > 0

    def test_e2e_create_update_flow(self, tmp_path):
        """E2E: discover missed → triage → issue 変換フロー。"""
        from skill_triage import triage_all_skills
        from issue_schema import make_skill_triage_issue

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "## Skills\n"
            "- /existing-skill: 既存スキル。Trigger: existing, 既存\n"
        )

        sessions = [
            {"session_id": f"s{i}", "user_prompts": [f"既存のスキルを使いたい {i}"]}
            for i in range(5)
        ]
        usage = [
            {"session_id": "s0", "skill_name": "existing-skill"},
        ]
        missed = [
            {"skill": "existing-skill", "triggers_matched": ["既存"], "session_count": 3},
            {"skill": "new-skill", "triggers_matched": ["new"], "session_count": 4},
        ]

        result = triage_all_skills(
            sessions=sessions,
            usage=usage,
            missed_skills=missed,
            project_root=tmp_path,
        )

        # CREATE/UPDATE/OK のいずれかに分類される
        all_actions = result["CREATE"] + result["UPDATE"] + result["OK"]
        assert len(all_actions) > 0

        # issue 変換
        issues = []
        for action in ("CREATE", "UPDATE", "SPLIT", "MERGE"):
            for triage in result.get(action, []):
                issue = make_skill_triage_issue(triage)
                if issue:
                    issues.append(issue)
        # CREATE の new-skill がある
        create_issues = [i for i in issues if i["type"] == "skill_triage_create"]
        assert len(create_issues) > 0
