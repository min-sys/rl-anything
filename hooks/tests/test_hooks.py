"""observe hooks のスモークテスト。"""
import importlib
import json
import os
import sys
import time
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

# hooks/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common
import observe
import session_summary
import save_state
import restore_state
import subagent_observe
import workflow_context


@pytest.fixture
def tmp_data_dir(tmp_path):
    """テスト用の一時データディレクトリ。"""
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def patch_data_dir(tmp_data_dir):
    """common.DATA_DIR を一時ディレクトリに差し替える。"""
    with mock.patch.object(common, "DATA_DIR", tmp_data_dir):
        yield tmp_data_dir


class TestWorkflowContext:
    """workflow_context.py のテスト。"""

    def test_context_file_created(self, tmp_path):
        """Skill 呼び出し時に文脈ファイルが作成される。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "opsx:refine", "args": ""},
                "session_id": "sess-wf-001",
            }
            workflow_context.handle_pre_tool_use(event)

            ctx_path = tmp_path / "rl-anything-workflow-sess-wf-001.json"
            assert ctx_path.exists()
            ctx = json.loads(ctx_path.read_text())
            assert ctx["skill_name"] == "opsx:refine"
            assert ctx["session_id"] == "sess-wf-001"
            assert ctx["workflow_id"].startswith("wf-")
            assert len(ctx["workflow_id"]) == 11  # "wf-" + 8 hex chars
            assert "started_at" in ctx

    def test_context_overwritten_on_new_skill(self, tmp_path):
        """同一セッションで別の Skill が呼ばれると文脈が上書きされる。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event1 = {
                "tool_name": "Skill",
                "tool_input": {"skill": "opsx:refine"},
                "session_id": "sess-wf-002",
            }
            workflow_context.handle_pre_tool_use(event1)

            ctx_path = tmp_path / "rl-anything-workflow-sess-wf-002.json"
            ctx1 = json.loads(ctx_path.read_text())
            wf_id_1 = ctx1["workflow_id"]

            event2 = {
                "tool_name": "Skill",
                "tool_input": {"skill": "opsx:apply"},
                "session_id": "sess-wf-002",
            }
            workflow_context.handle_pre_tool_use(event2)

            ctx2 = json.loads(ctx_path.read_text())
            assert ctx2["skill_name"] == "opsx:apply"
            assert ctx2["workflow_id"] != wf_id_1

    def test_no_session_id_noop(self, tmp_path):
        """session_id がない場合は何もしない。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "test"},
                "session_id": "",
            }
            workflow_context.handle_pre_tool_use(event)
            assert not list(tmp_path.glob("rl-anything-workflow-*"))

    def test_no_skill_name_noop(self, tmp_path):
        """skill_name がない場合は何もしない。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "tool_name": "Skill",
                "tool_input": {},
                "session_id": "sess-wf-003",
            }
            workflow_context.handle_pre_tool_use(event)
            assert not list(tmp_path.glob("rl-anything-workflow-*"))


class TestReadWorkflowContext:
    """common.read_workflow_context() のテスト。"""

    def test_context_exists(self, tmp_path):
        """文脈ファイルが存在する場合、parent_skill と workflow_id を返す。"""
        ctx = {
            "skill_name": "opsx:refine",
            "session_id": "sess-rwc-001",
            "workflow_id": "wf-abc12345",
            "started_at": "2026-03-03T10:00:00+00:00",
        }
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-rwc-001.json"
            ctx_path.write_text(json.dumps(ctx))

            result = common.read_workflow_context("sess-rwc-001")
            assert result["parent_skill"] == "opsx:refine"
            assert result["workflow_id"] == "wf-abc12345"

    def test_context_not_exists(self, tmp_path):
        """文脈ファイルが存在しない場合、null を返す。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            result = common.read_workflow_context("sess-rwc-002")
            assert result["parent_skill"] is None
            assert result["workflow_id"] is None

    def test_context_corrupted(self, tmp_path):
        """文脈ファイルが破損している場合、null を返す。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-rwc-003.json"
            ctx_path.write_text("NOT VALID JSON{{{")

            result = common.read_workflow_context("sess-rwc-003")
            assert result["parent_skill"] is None
            assert result["workflow_id"] is None

    def test_context_expired(self, tmp_path):
        """24時間以上経過した文脈ファイルは無効。"""
        ctx = {
            "skill_name": "opsx:refine",
            "workflow_id": "wf-expired1",
        }
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-rwc-004.json"
            ctx_path.write_text(json.dumps(ctx))

            # mtime を25時間前に設定
            old_time = time.time() - (25 * 60 * 60)
            os.utime(ctx_path, (old_time, old_time))

            result = common.read_workflow_context("sess-rwc-004")
            assert result["parent_skill"] is None
            assert result["workflow_id"] is None


class TestClassifyPrompt:
    """common.classify_prompt() のテスト。"""

    # --- 既存カテゴリ（英語） ---

    def test_spec_review(self):
        assert common.classify_prompt("review the spec requirements") == "spec-review"

    def test_code_exploration(self):
        assert common.classify_prompt("explore the codebase structure") == "code-exploration"

    def test_research(self):
        assert common.classify_prompt("research best practice for caching") == "research"

    def test_code_review(self):
        assert common.classify_prompt("review code changes in auth module") == "code-review"

    def test_implementation(self):
        assert common.classify_prompt("implement the new feature") == "implementation"

    def test_other(self):
        assert common.classify_prompt("hello world") == "other"

    def test_case_insensitive(self):
        assert common.classify_prompt("EXPLORE the CODEBASE") == "code-exploration"

    def test_empty_prompt(self):
        assert common.classify_prompt("") == "other"

    # --- 新カテゴリ（英語） ---

    def test_git_ops_merge(self):
        assert common.classify_prompt("merge the feature branch") == "git-ops"

    def test_git_ops_rebase(self):
        assert common.classify_prompt("rebase onto main") == "git-ops"

    def test_deploy_release(self):
        assert common.classify_prompt("deploy to production") == "deploy"

    def test_deploy_staging(self):
        assert common.classify_prompt("release to staging environment") == "deploy"

    def test_debug_fix(self):
        assert common.classify_prompt("fix the login bug") == "debug"

    def test_debug_error(self):
        assert common.classify_prompt("debug the error in auth") == "debug"

    def test_test_pytest(self):
        assert common.classify_prompt("run pytest on the module") == "test"

    def test_test_assert(self):
        assert common.classify_prompt("add assert for edge case") == "test"

    def test_config_setup(self):
        assert common.classify_prompt("update config for database") == "config"

    def test_config_env(self):
        assert common.classify_prompt("setup the env variables") == "config"

    def test_conversation_ok(self):
        assert common.classify_prompt("OK let's do it") == "conversation:approval"

    # --- 既存カテゴリ（日本語） ---

    def test_spec_review_jp(self):
        assert common.classify_prompt("仕様を確認してください") == "spec-review"

    def test_spec_review_jp_requirements(self):
        assert common.classify_prompt("要件を整理して") == "spec-review"

    def test_code_review_jp(self):
        assert common.classify_prompt("コードレビューして") == "code-review"

    def test_code_review_jp_diff(self):
        assert common.classify_prompt("差分を見て") == "code-review"

    def test_code_exploration_jp(self):
        assert common.classify_prompt("ファイル構造を教えて") == "code-exploration"

    def test_code_exploration_jp_read(self):
        assert common.classify_prompt("このファイル読んで") == "code-exploration"

    def test_research_jp(self):
        assert common.classify_prompt("ベストプラクティスを調べて") == "research"

    def test_research_jp_latest(self):
        assert common.classify_prompt("最新の方法を教えて") == "research"

    def test_implementation_jp(self):
        assert common.classify_prompt("この機能を実装して") == "implementation"

    def test_implementation_jp_create(self):
        assert common.classify_prompt("新しいコンポーネントを作って") == "implementation"

    # --- 新カテゴリ（日本語） ---

    def test_git_ops_jp_merge(self):
        assert common.classify_prompt("mainにマージして") == "git-ops"

    def test_git_ops_jp_commit(self):
        assert common.classify_prompt("コミットしてください") == "git-ops"

    def test_git_ops_jp_branch(self):
        assert common.classify_prompt("ブランチを切って") == "git-ops"

    def test_deploy_jp(self):
        assert common.classify_prompt("本番にデプロイして") == "deploy"

    def test_deploy_jp_release(self):
        assert common.classify_prompt("リリースの準備をして") == "deploy"

    def test_debug_jp_fix(self):
        assert common.classify_prompt("このバグを修正して") == "debug"

    def test_debug_jp_investigate(self):
        assert common.classify_prompt("エラーの原因を調査して") == "debug"

    def test_debug_jp_naose(self):
        assert common.classify_prompt("これ直して") == "debug"

    def test_test_jp(self):
        assert common.classify_prompt("テストを実行して") == "test"

    def test_test_jp_verify(self):
        assert common.classify_prompt("動作を検証して") == "test"

    def test_config_jp(self):
        assert common.classify_prompt("設定を変更して") == "config"

    def test_config_jp_readme(self):
        assert common.classify_prompt("README.mdを更新") == "config"

    def test_conversation_jp_please(self):
        assert common.classify_prompt("お願いします") == "conversation:confirmation"

    def test_conversation_jp_continue(self):
        assert common.classify_prompt("続けてください") == "conversation:confirmation"

    def test_conversation_jp_proceed(self):
        assert common.classify_prompt("進めて") == "conversation:confirmation"

    def test_conversation_jp_thanks(self):
        assert common.classify_prompt("ありがとう") == "conversation:thanks"

    # --- 優先順位テスト ---

    def test_priority_spec_over_code_review(self):
        """spec-review は code-review より優先される。"""
        assert common.classify_prompt("review the spec") == "spec-review"

    def test_priority_debug_over_implementation(self):
        """debug は implementation より優先される（'fix' キーワード）。"""
        assert common.classify_prompt("fix this broken feature") == "debug"

    def test_priority_git_ops_over_deploy(self):
        """git-ops は deploy より優先される（'push' キーワード）。"""
        assert common.classify_prompt("push to remote branch") == "git-ops"


class TestObserve:
    """observe.py のテスト。"""

    def test_skill_usage_recorded(self, patch_data_dir):
        event = {
            "tool_name": "Skill",
            "tool_input": {"skill": "my-skill", "args": "test.py"},
            "tool_result": {},
            "session_id": "sess-001",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        assert usage_file.exists()
        record = json.loads(usage_file.read_text().strip())
        assert record["skill_name"] == "my-skill"
        assert record["session_id"] == "sess-001"

    def test_skill_usage_project_field(self, patch_data_dir):
        """Skill usage にプロジェクト名が記録される。"""
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": "/Users/foo/atlas-breeaders"}):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "my-skill", "args": ""},
                "tool_result": {},
                "session_id": "sess-proj-001",
            }
            observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["project"] == "atlas-breeaders"

    def test_skill_usage_project_null_when_unset(self, patch_data_dir):
        """CLAUDE_PROJECT_DIR 未設定時は project が null。"""
        with mock.patch.dict(os.environ, {}, clear=True):
            # CLAUDE_PROJECT_DIR を確実に削除
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "my-skill", "args": ""},
                "tool_result": {},
                "session_id": "sess-proj-002",
            }
            observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["project"] is None

    def test_skill_usage_project_null_when_empty(self, patch_data_dir):
        """CLAUDE_PROJECT_DIR が空文字列の場合は project が null。"""
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": ""}):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "my-skill", "args": ""},
                "tool_result": {},
                "session_id": "sess-proj-003",
            }
            observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["project"] is None

    def test_global_skill_registers(self, patch_data_dir):
        global_prefix = str(Path.home() / ".claude" / "skills")
        event = {
            "tool_name": "Skill",
            "tool_input": {"skill": f"{global_prefix}/my-global"},
            "tool_result": {},
            "session_id": "sess-002",
        }
        observe.handle_post_tool_use(event)

        registry_file = patch_data_dir / "usage-registry.jsonl"
        assert registry_file.exists()
        record = json.loads(registry_file.read_text().strip())
        assert "project_path" in record

    def test_error_recorded(self, patch_data_dir):
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "false"},
            "tool_result": {"is_error": True, "content": "exit code 1"},
            "session_id": "sess-003",
        }
        observe.handle_post_tool_use(event)

        errors_file = patch_data_dir / "errors.jsonl"
        assert errors_file.exists()
        record = json.loads(errors_file.read_text().strip())
        assert record["tool_name"] == "Bash"

    def test_error_project_field(self, patch_data_dir):
        """errors にプロジェクト名が記録される。"""
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": "/Users/foo/error-proj"}):
            event = {
                "tool_name": "Bash",
                "tool_input": {"command": "false"},
                "tool_result": {"is_error": True, "content": "fail"},
                "session_id": "sess-proj-003",
            }
            observe.handle_post_tool_use(event)

        errors_file = patch_data_dir / "errors.jsonl"
        record = json.loads(errors_file.read_text().strip())
        assert record["project"] == "error-proj"

    def test_non_skill_tool_no_usage(self, patch_data_dir):
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/x"},
            "tool_result": {},
            "session_id": "sess-004",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        assert not usage_file.exists()

    def test_write_failure_silent(self, tmp_data_dir):
        """JSONL 書き込み失敗時、例外を投げない。"""
        bad_dir = tmp_data_dir / "nonexistent_sub" / "deep"
        with mock.patch.object(common, "DATA_DIR", bad_dir):
            with mock.patch.object(common, "ensure_data_dir"):
                # ensure_data_dir を無効化して書き込み先を壊す
                event = {
                    "tool_name": "Skill",
                    "tool_input": {"skill": "test"},
                    "tool_result": {},
                    "session_id": "sess-005",
                }
                # 例外が出ないことを確認
                observe.handle_post_tool_use(event)

    def test_directory_auto_created(self, tmp_path):
        """ディレクトリが存在しない場合 MUST 自動作成する。"""
        new_dir = tmp_path / "new-rl-anything"
        with mock.patch.object(common, "DATA_DIR", new_dir):
            event = {
                "tool_name": "Skill",
                "tool_input": {"skill": "test"},
                "tool_result": {},
                "session_id": "sess-006",
            }
            observe.handle_post_tool_use(event)

        assert new_dir.exists()

    def test_agent_tool_usage_recorded(self, patch_data_dir):
        """Agent ツール呼び出しが usage.jsonl に記録される。"""
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": "codebase を探索してください",
            },
            "tool_result": {},
            "session_id": "sess-100",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        assert usage_file.exists()
        record = json.loads(usage_file.read_text().strip())
        assert record["skill_name"] == "Agent:Explore"
        assert record["subagent_type"] == "Explore"
        assert record["prompt"] == "codebase を探索してください"
        assert record["session_id"] == "sess-100"

    def test_agent_usage_project_field(self, patch_data_dir):
        """Agent usage にプロジェクト名が記録される。"""
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": "/Users/foo/my-project"}):
            event = {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "Explore", "prompt": "explore"},
                "tool_result": {},
                "session_id": "sess-proj-100",
            }
            observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["project"] == "my-project"

    def test_agent_tool_prompt_truncated(self, patch_data_dir):
        """Agent ツールの prompt が 200 文字に切り詰められる。"""
        long_prompt = "あ" * 300
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "general-purpose",
                "prompt": long_prompt,
            },
            "tool_result": {},
            "session_id": "sess-101",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert len(record["prompt"]) == 200

    def test_agent_tool_empty_prompt(self, patch_data_dir):
        """Agent ツールの prompt が空の場合、空文字列として記録される。"""
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "Explore",
                "prompt": "",
            },
            "tool_result": {},
            "session_id": "sess-102",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["prompt"] == ""

    def test_agent_tool_missing_subagent_type(self, patch_data_dir):
        """Agent ツールの subagent_type が未指定の場合、'unknown' として記録される。"""
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "prompt": "何かやって",
            },
            "tool_result": {},
            "session_id": "sess-103",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["skill_name"] == "Agent:unknown"
        assert record["subagent_type"] == "unknown"

    def test_agent_tool_null_subagent_type(self, patch_data_dir):
        """Agent ツールの subagent_type が None の場合、'unknown' として記録される。"""
        event = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": None,
                "prompt": "何かやって",
            },
            "tool_result": {},
            "session_id": "sess-104",
        }
        observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["subagent_type"] == "unknown"

    def test_agent_with_parent_skill(self, patch_data_dir, tmp_path):
        """ワークフロー文脈がある場合、parent_skill と workflow_id が付与される。"""
        ctx = {
            "skill_name": "opsx:refine",
            "session_id": "sess-110",
            "workflow_id": "wf-test1234",
            "started_at": "2026-03-03T10:00:00+00:00",
        }
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-110.json"
            ctx_path.write_text(json.dumps(ctx))

            event = {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "Explore", "prompt": "explore"},
                "tool_result": {},
                "session_id": "sess-110",
            }
            observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["parent_skill"] == "opsx:refine"
        assert record["workflow_id"] == "wf-test1234"

    def test_agent_without_parent_skill(self, patch_data_dir, tmp_path):
        """ワークフロー文脈がない場合、parent_skill と workflow_id は null。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "Explore", "prompt": "explore"},
                "tool_result": {},
                "session_id": "sess-111",
            }
            observe.handle_post_tool_use(event)

        usage_file = patch_data_dir / "usage.jsonl"
        record = json.loads(usage_file.read_text().strip())
        assert record["parent_skill"] is None
        assert record["workflow_id"] is None


class TestSubagentObserve:
    """subagent_observe.py のテスト。"""

    def test_subagent_stop_recorded(self, patch_data_dir):
        """SubagentStop イベントが subagents.jsonl に記録される。"""
        event = {
            "agent_type": "Explore",
            "agent_id": "agent-001",
            "last_assistant_message": "探索が完了しました",
            "agent_transcript_path": "/tmp/transcript.jsonl",
            "session_id": "sess-200",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        assert subagents_file.exists()
        record = json.loads(subagents_file.read_text().strip())
        assert record["agent_type"] == "Explore"
        assert record["agent_id"] == "agent-001"
        assert record["last_assistant_message"] == "探索が完了しました"
        assert record["agent_transcript_path"] == "/tmp/transcript.jsonl"
        assert record["session_id"] == "sess-200"
        assert "timestamp" in record

    def test_last_message_truncated(self, patch_data_dir):
        """last_assistant_message が 500 文字に切り詰められる。"""
        long_message = "あ" * 600
        event = {
            "agent_type": "general-purpose",
            "agent_id": "agent-002",
            "last_assistant_message": long_message,
            "agent_transcript_path": "/tmp/t.jsonl",
            "session_id": "sess-201",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert len(record["last_assistant_message"]) == 500

    def test_empty_last_message(self, patch_data_dir):
        """last_assistant_message が空の場合、空文字列として記録される。"""
        event = {
            "agent_type": "Explore",
            "agent_id": "agent-003",
            "last_assistant_message": "",
            "agent_transcript_path": "/tmp/t.jsonl",
            "session_id": "sess-202",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["last_assistant_message"] == ""

    def test_null_last_message(self, patch_data_dir):
        """last_assistant_message が null の場合、空文字列として記録される。"""
        event = {
            "agent_type": "Explore",
            "agent_id": "agent-004",
            "last_assistant_message": None,
            "agent_transcript_path": "/tmp/t.jsonl",
            "session_id": "sess-203",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["last_assistant_message"] == ""

    def test_nonexistent_transcript_path(self, patch_data_dir):
        """agent_transcript_path が存在しないパスでもパスのみ記録する。"""
        event = {
            "agent_type": "Explore",
            "agent_id": "agent-005",
            "last_assistant_message": "done",
            "agent_transcript_path": "/nonexistent/path/transcript.jsonl",
            "session_id": "sess-204",
        }
        subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["agent_transcript_path"] == "/nonexistent/path/transcript.jsonl"

    def test_write_failure_silent(self, tmp_data_dir):
        """書き込み失敗時、例外を投げない（MUST NOT block session）。"""
        bad_dir = tmp_data_dir / "nonexistent_sub" / "deep"
        with mock.patch.object(common, "DATA_DIR", bad_dir):
            with mock.patch.object(common, "ensure_data_dir"):
                event = {
                    "agent_type": "Explore",
                    "agent_id": "agent-006",
                    "last_assistant_message": "test",
                    "agent_transcript_path": "/tmp/t.jsonl",
                    "session_id": "sess-205",
                }
                subagent_observe.handle_subagent_stop(event)

    def test_parent_skill_attached(self, patch_data_dir, tmp_path):
        """ワークフロー文脈がある場合、parent_skill が subagents.jsonl に付与される。"""
        ctx = {
            "skill_name": "opsx:refine",
            "session_id": "sess-210",
            "workflow_id": "wf-sub12345",
        }
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-210.json"
            ctx_path.write_text(json.dumps(ctx))

            event = {
                "agent_type": "Explore",
                "agent_id": "agent-010",
                "last_assistant_message": "done",
                "agent_transcript_path": "/tmp/t.jsonl",
                "session_id": "sess-210",
            }
            subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["parent_skill"] == "opsx:refine"
        assert record["workflow_id"] == "wf-sub12345"

    def test_no_parent_skill(self, patch_data_dir, tmp_path):
        """ワークフロー文脈がない場合、parent_skill は null。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {
                "agent_type": "Explore",
                "agent_id": "agent-011",
                "last_assistant_message": "done",
                "agent_transcript_path": "/tmp/t.jsonl",
                "session_id": "sess-211",
            }
            subagent_observe.handle_subagent_stop(event)

        subagents_file = patch_data_dir / "subagents.jsonl"
        record = json.loads(subagents_file.read_text().strip())
        assert record["parent_skill"] is None
        assert record["workflow_id"] is None


class TestSessionSummary:
    """session_summary.py のテスト。"""

    def test_session_summary_recorded(self, patch_data_dir):
        # まず usage を書き込む
        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"session_id": "sess-010", "skill_name": "a"}) + "\n"
            + json.dumps({"session_id": "sess-010", "skill_name": "b"}) + "\n"
        )

        event = {"session_id": "sess-010"}
        session_summary.handle_stop(event)

        sessions_file = patch_data_dir / "sessions.jsonl"
        assert sessions_file.exists()
        record = json.loads(sessions_file.read_text().strip())
        assert record["session_id"] == "sess-010"
        assert record["skill_count"] == 2
        assert record["error_count"] == 0


    def test_workflow_sequence_recorded(self, patch_data_dir, tmp_path):
        """ワークフローシーケンスが workflows.jsonl に書き出される。"""
        usage_file = patch_data_dir / "usage.jsonl"
        records = [
            {
                "session_id": "sess-wfs-001",
                "skill_name": "Agent:Explore",
                "workflow_id": "wf-seqtest1",
                "parent_skill": "opsx:refine",
                "prompt": "explore the codebase structure",
                "timestamp": "2026-03-03T10:00:00+00:00",
            },
            {
                "session_id": "sess-wfs-001",
                "skill_name": "Agent:Explore",
                "workflow_id": "wf-seqtest1",
                "parent_skill": "opsx:refine",
                "prompt": "review spec requirements",
                "timestamp": "2026-03-03T10:01:00+00:00",
            },
            {
                "session_id": "sess-wfs-001",
                "skill_name": "Agent:general-purpose",
                "workflow_id": "wf-seqtest1",
                "parent_skill": "opsx:refine",
                "prompt": "implement the changes",
                "timestamp": "2026-03-03T10:02:00+00:00",
            },
        ]
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {"session_id": "sess-wfs-001"}
            session_summary.handle_stop(event)

        workflows_file = patch_data_dir / "workflows.jsonl"
        assert workflows_file.exists()
        wf = json.loads(workflows_file.read_text().strip())
        assert wf["workflow_id"] == "wf-seqtest1"
        assert wf["skill_name"] == "opsx:refine"
        assert wf["step_count"] == 3
        assert len(wf["steps"]) == 3
        assert wf["steps"][0]["tool"] == "Agent:Explore"
        assert wf["steps"][0]["intent_category"] == "code-exploration"
        assert wf["steps"][1]["intent_category"] == "spec-review"
        assert wf["steps"][2]["intent_category"] == "implementation"
        assert wf["source"] == "trace"

    def test_no_workflow_no_record(self, patch_data_dir, tmp_path):
        """ワークフローがないセッションでは workflows.jsonl に何も書き出さない。"""
        usage_file = patch_data_dir / "usage.jsonl"
        usage_file.write_text(
            json.dumps({"session_id": "sess-wfs-002", "skill_name": "my-skill"}) + "\n"
        )

        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {"session_id": "sess-wfs-002"}
            session_summary.handle_stop(event)

        workflows_file = patch_data_dir / "workflows.jsonl"
        assert not workflows_file.exists()

    def test_context_file_cleanup(self, patch_data_dir, tmp_path):
        """セッション終了時に文脈ファイルが削除される。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            ctx_path = tmp_path / "rl-anything-workflow-sess-wfs-003.json"
            ctx_path.write_text('{"skill_name":"test"}')
            assert ctx_path.exists()

            event = {"session_id": "sess-wfs-003"}
            session_summary.handle_stop(event)

            assert not ctx_path.exists()

    def test_context_file_cleanup_not_exists(self, patch_data_dir, tmp_path):
        """文脈ファイルが存在しない場合、エラーは発生しない。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            event = {"session_id": "sess-wfs-004"}
            session_summary.handle_stop(event)  # no error


class TestSaveState:
    """save_state.py のテスト。"""

    def test_checkpoint_saved(self, patch_data_dir):
        event = {
            "session_id": "sess-020",
            "evolve_state": {"generation": 3},
        }
        save_state.handle_pre_compact(event)

        checkpoint_file = patch_data_dir / "checkpoint.json"
        assert checkpoint_file.exists()
        data = json.loads(checkpoint_file.read_text())
        assert data["session_id"] == "sess-020"
        assert data["evolve_state"]["generation"] == 3

    def test_work_context_saved(self, patch_data_dir):
        """正常系: work_context が checkpoint に保存される。"""
        git_outputs = {
            ("rev-parse", "--abbrev-ref", "HEAD"): "feature/test\n",
            ("log", "--oneline", "-5"): "abc1234 fix: something\ndef5678 feat: another\n",
            ("status", "--short"): " M file1.py\n?? file2.py\n",
        }

        def fake_run(args, **kwargs):
            key = tuple(args[1:])  # skip "git"
            stdout = git_outputs.get(key, "")
            result = mock.MagicMock()
            result.returncode = 0
            result.stdout = stdout
            return result

        with mock.patch("save_state.subprocess.run", side_effect=fake_run):
            save_state.handle_pre_compact({"session_id": "sess-wc-01"})

        data = json.loads((patch_data_dir / "checkpoint.json").read_text())
        wc = data["work_context"]
        assert wc["git_branch"] == "feature/test"
        assert len(wc["recent_commits"]) == 2
        assert "abc1234 fix: something" in wc["recent_commits"]
        assert len(wc["uncommitted_files"]) == 2

    def test_work_context_git_failure(self, patch_data_dir):
        """git コマンド失敗時に空のフォールバック値で保存される。"""
        def fake_run(args, **kwargs):
            raise FileNotFoundError("git not found")

        with mock.patch("save_state.subprocess.run", side_effect=fake_run):
            save_state.handle_pre_compact({"session_id": "sess-wc-02"})

        data = json.loads((patch_data_dir / "checkpoint.json").read_text())
        wc = data["work_context"]
        assert wc["git_branch"] == ""
        assert wc["recent_commits"] == []
        assert wc["uncommitted_files"] == []

    def test_work_context_uncommitted_limit(self, patch_data_dir):
        """uncommitted_files が _MAX_UNCOMMITTED_FILES を超える場合に切り詰められる。"""
        many_files = "\n".join(f" M file{i}.py" for i in range(50))

        def fake_run(args, **kwargs):
            key = tuple(args[1:])
            outputs = {
                ("rev-parse", "--abbrev-ref", "HEAD"): "main\n",
                ("log", "--oneline", "-5"): "",
                ("status", "--short"): many_files + "\n",
            }
            result = mock.MagicMock()
            result.returncode = 0
            result.stdout = outputs.get(key, "")
            return result

        with mock.patch("save_state.subprocess.run", side_effect=fake_run):
            save_state.handle_pre_compact({"session_id": "sess-wc-03"})

        data = json.loads((patch_data_dir / "checkpoint.json").read_text())
        assert len(data["work_context"]["uncommitted_files"]) == 30


class TestRestoreState:
    """restore_state.py のテスト。"""

    def test_checkpoint_restored(self, patch_data_dir, capsys):
        checkpoint = {
            "session_id": "sess-030",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "evolve_state": {"generation": 5},
        }
        (patch_data_dir / "checkpoint.json").write_text(json.dumps(checkpoint))

        restore_state.handle_session_start({})

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())
        assert result["restored"] is True
        assert result["checkpoint"]["evolve_state"]["generation"] == 5

    def test_no_checkpoint_noop(self, patch_data_dir, capsys):
        restore_state.handle_session_start({})

        captured = capsys.readouterr()
        assert captured.out.strip() == ""

    def test_work_context_restored_with_summary(self, patch_data_dir, capsys):
        """work_context 付き checkpoint の復元でサマリーが出力される。"""
        checkpoint = {
            "session_id": "sess-040",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "evolve_state": {},
            "work_context": {
                "git_branch": "feature/x",
                "recent_commits": ["abc1234 fix: something"],
                "uncommitted_files": ["path/to/file1"],
            },
        }
        (patch_data_dir / "checkpoint.json").write_text(json.dumps(checkpoint))

        restore_state.handle_session_start({})

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # 最初の行は JSON 出力
        result = json.loads(lines[0])
        assert result["restored"] is True
        # 残りの行はサマリー
        summary = "\n".join(lines[1:])
        assert "[rl-anything:restore_state] 作業コンテキスト復元:" in summary
        assert "ブランチ: feature/x" in summary
        assert "abc1234 fix: something" in summary
        assert "path/to/file1" in summary

    def test_work_context_missing_backward_compat(self, patch_data_dir, capsys):
        """work_context なしの旧 checkpoint でもエラーが発生しない。"""
        checkpoint = {
            "session_id": "sess-050",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "evolve_state": {"generation": 2},
        }
        (patch_data_dir / "checkpoint.json").write_text(json.dumps(checkpoint))

        restore_state.handle_session_start({})

        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())
        assert result["restored"] is True
        # work_context サマリーは出力されない
        assert "作業コンテキスト復元" not in captured.out


# --- discover.py / prune.py のワークフロートレーシング関連テスト ---

# discover/prune のインポートパスを追加
_plugin_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "prune" / "scripts"))
sys.path.insert(0, str(_plugin_root / "skills" / "discover" / "scripts"))

import discover as _discover_mod


def _load_skills_discover():
    """skills/discover/scripts/discover.py をロードする。"""
    return _discover_mod


class TestDiscoverContextualization:
    """discover.py の contextualized/ad-hoc 分類テスト。"""

    def test_ad_hoc_only_counted(self, patch_data_dir):
        """ad-hoc レコードのみがスキル候補としてカウントされる。

        Agent:Explore は組み込み Agent のため agent_usage_summary に分類される。
        """
        discover = _load_skills_discover()

        usage_file = patch_data_dir / "usage.jsonl"
        records = []
        # contextualized: 15回（parent_skill あり）
        for i in range(15):
            records.append({
                "skill_name": "Agent:Explore",
                "parent_skill": "opsx:refine",
                "workflow_id": f"wf-ctx{i:04d}",
                "prompt": "explore",
            })
        # ad-hoc: 6回（parent_skill なし、backfill でない）
        for i in range(6):
            records.append({
                "skill_name": "Agent:Explore",
                "prompt": "explore manually",
            })
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.object(discover, "DATA_DIR", patch_data_dir):
            with mock.patch.object(discover, "SUPPRESSION_FILE", patch_data_dir / "suppress.jsonl"):
                patterns = discover.detect_behavior_patterns(threshold=5)

        # Agent:Explore は組み込み Agent → agent_usage_summary に分離
        summary = [p for p in patterns if p["type"] == "agent_usage_summary"]
        assert len(summary) == 1
        assert summary[0]["count"] == 6  # ad-hoc のみ

    def test_backfill_excluded_as_unknown(self, patch_data_dir):
        """backfill データは unknown として除外される。"""
        discover = _load_skills_discover()

        usage_file = patch_data_dir / "usage.jsonl"
        records = []
        # backfill: 10回
        for i in range(10):
            records.append({
                "skill_name": "Agent:Explore",
                "source": "backfill",
                "prompt": "explore",
            })
        # ad-hoc: 3回（閾値未満）
        for i in range(3):
            records.append({
                "skill_name": "Agent:Explore",
                "prompt": "explore",
            })
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.object(discover, "DATA_DIR", patch_data_dir):
            with mock.patch.object(discover, "SUPPRESSION_FILE", patch_data_dir / "suppress.jsonl"):
                patterns = discover.detect_behavior_patterns(threshold=5)

        # ad-hoc 3回は閾値5未満なので候補なし
        assert len(patterns) == 0


class TestPruneParentSkill:
    """prune.py の parent_skill 経由カウントテスト。"""

    def test_parent_skill_prevents_zero_invocation(self, patch_data_dir):
        """parent_skill 経由で使用されているスキルは淘汰候補にならない。"""
        import prune
        import audit

        usage_file = patch_data_dir / "usage.jsonl"
        # opsx:refine を直接呼んだ記録はないが、parent_skill として参照されている
        records = [
            {
                "skill_name": "Agent:Explore",
                "parent_skill": "opsx:refine",
                "workflow_id": "wf-prune001",
                "timestamp": "2026-03-03T10:00:00+00:00",
            },
        ]
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.object(audit, "DATA_DIR", patch_data_dir):
            usage_records = audit.load_usage_data(days=30)

        used_skills = set()
        for rec in usage_records:
            used_skills.add(rec.get("skill_name", ""))
            parent = rec.get("parent_skill")
            if parent:
                used_skills.add(parent)

        assert "opsx:refine" in used_skills

    def test_no_usage_detected(self, patch_data_dir):
        """直接呼び出しも parent_skill 参照もないスキルは淘汰候補。"""
        import audit

        usage_file = patch_data_dir / "usage.jsonl"
        records = [
            {
                "skill_name": "Agent:Explore",
                "timestamp": "2026-03-03T10:00:00+00:00",
            },
        ]
        usage_file.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )

        with mock.patch.object(audit, "DATA_DIR", patch_data_dir):
            usage_records = audit.load_usage_data(days=30)

        used_skills = set()
        for rec in usage_records:
            used_skills.add(rec.get("skill_name", ""))
            parent = rec.get("parent_skill")
            if parent:
                used_skills.add(parent)

        assert "some-unused-skill" not in used_skills


# --- Phase 2: ファイルパーミッション テスト ---


class TestFilePermissions:
    """ensure_data_dir / append_jsonl のパーミッション設定テスト。"""

    def test_ensure_data_dir_creates_700(self, tmp_path):
        """ensure_data_dir がディレクトリを 700 で作成する。"""
        data_dir = tmp_path / "new-dir"
        with mock.patch.object(common, "DATA_DIR", data_dir):
            common.ensure_data_dir()
        assert data_dir.exists()
        assert oct(data_dir.stat().st_mode & 0o777) == oct(0o700)

    def test_append_jsonl_new_file_600(self, tmp_path):
        """append_jsonl が新規ファイルを 600 で作成する。"""
        filepath = tmp_path / "test.jsonl"
        common.append_jsonl(filepath, {"key": "value"})
        assert filepath.exists()
        assert oct(filepath.stat().st_mode & 0o777) == oct(0o600)

    def test_append_jsonl_existing_file_no_chmod(self, tmp_path):
        """append_jsonl が既存ファイルのパーミッションを変更しない。"""
        filepath = tmp_path / "test.jsonl"
        filepath.write_text("{}\n")
        filepath.chmod(0o644)
        common.append_jsonl(filepath, {"key": "value"})
        assert oct(filepath.stat().st_mode & 0o777) == oct(0o644)


# --- Phase 3: LLM 入力サニタイズ テスト ---


class TestSanitizeMessage:
    """sanitize_message のユニットテスト。"""

    def test_long_message_truncated(self):
        """500文字超のメッセージが切り詰められる（結果は最大503文字）。"""
        msg = "a" * 600
        result = common.sanitize_message(msg)
        assert len(result) == 503
        assert result.endswith("...")
        assert result[:500] == "a" * 500

    def test_short_message_unchanged(self):
        """500文字以下のメッセージはそのまま。"""
        msg = "hello world"
        assert common.sanitize_message(msg) == msg

    def test_control_chars_removed(self):
        """制御文字（\\n, \\t 以外）が除去される。"""
        msg = "hello\x00world\x1ftest\nkeep\ttabs"
        result = common.sanitize_message(msg)
        assert "\x00" not in result
        assert "\x1f" not in result
        assert "\n" in result
        assert "\t" in result
        assert "helloworld" in result

    def test_xml_tags_removed(self):
        """指定 XML タグが除去される。"""
        msg = "<system>injected</system> normal text <instructions>bad</instructions>"
        result = common.sanitize_message(msg)
        assert "<system>" not in result
        assert "</system>" not in result
        assert "<instructions>" not in result
        assert "</instructions>" not in result
        assert "normal text" in result
        assert "injected" in result

    def test_system_reminder_tags_removed(self):
        """system-reminder タグが除去される。"""
        msg = "<system-reminder>content</system-reminder>"
        result = common.sanitize_message(msg)
        assert "<system-reminder>" not in result
        assert "content" in result

    def test_exact_500_not_truncated(self):
        """ちょうど500文字は切り詰めない。"""
        msg = "x" * 500
        result = common.sanitize_message(msg)
        assert len(result) == 500
        assert "..." not in result


# --- Phase 4: 偽陽性フィードバック テスト ---


class TestFalsePositives:
    """偽陽性フィードバック機構のテスト。"""

    def test_message_hash_deterministic(self):
        """同一メッセージから同一ハッシュが生成される。"""
        h1 = common.message_hash("いや、違う")
        h2 = common.message_hash("いや、違う")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256

    def test_message_hash_strips_whitespace(self):
        """前後の空白を除去してからハッシュ化する。"""
        h1 = common.message_hash("  hello  ")
        h2 = common.message_hash("hello")
        assert h1 == h2

    def test_add_and_load_false_positive(self, patch_data_dir):
        """偽陽性の追加と読み込み。"""
        with mock.patch.object(common, "FALSE_POSITIVES_FILE", patch_data_dir / "false_positives.jsonl"):
            common.add_false_positive("いや、違う", "iya")
            hashes = common.load_false_positives()
            assert common.message_hash("いや、違う") in hashes

    def test_detect_correction_excludes_false_positive(self, patch_data_dir):
        """偽陽性として報告済みのメッセージは検出されない。"""
        fp_file = patch_data_dir / "false_positives.jsonl"
        msg = "いや、そうじゃなくて"
        record = {"message_hash": common.message_hash(msg), "original_type": "iya", "timestamp": "2026-01-01T00:00:00+00:00"}
        fp_file.write_text(json.dumps(record) + "\n")
        with mock.patch.object(common, "FALSE_POSITIVES_FILE", fp_file):
            result = common.detect_correction(msg)
            assert result is None

    def test_detect_correction_works_without_false_positives(self, patch_data_dir):
        """false_positives.jsonl が存在しなくても正常に検出する。"""
        with mock.patch.object(common, "FALSE_POSITIVES_FILE", patch_data_dir / "nonexistent.jsonl"):
            result = common.detect_correction("いや、違う")
            assert result is not None
            assert result[0] == "iya"

    def test_cleanup_removes_old_entries(self, patch_data_dir):
        """180日超のエントリがクリーンアップされる。"""
        fp_file = patch_data_dir / "false_positives.jsonl"
        old_ts = (datetime(2025, 1, 1, tzinfo=timezone.utc)).isoformat()
        new_ts = datetime.now(timezone.utc).isoformat()
        lines = [
            json.dumps({"message_hash": "old_hash", "original_type": "iya", "timestamp": old_ts}),
            json.dumps({"message_hash": "new_hash", "original_type": "no", "timestamp": new_ts}),
        ]
        fp_file.write_text("\n".join(lines) + "\n")
        with mock.patch.object(common, "FALSE_POSITIVES_FILE", fp_file):
            removed = common.cleanup_false_positives()
        assert removed == 1
        remaining = fp_file.read_text()
        assert "new_hash" in remaining
        assert "old_hash" not in remaining

    def test_load_false_positives_corrupt_file(self, patch_data_dir):
        """破損ファイルでも空セットを返す（サイレント続行）。"""
        fp_file = patch_data_dir / "false_positives.jsonl"
        fp_file.write_text("not json at all\n{invalid}\n")
        with mock.patch.object(common, "FALSE_POSITIVES_FILE", fp_file):
            hashes = common.load_false_positives()
            assert isinstance(hashes, set)
            assert len(hashes) == 0
