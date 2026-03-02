"""backfill スクリプトのテスト。"""
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# backfill.py をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# hooks/ もインポートパスに追加（common.py 用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "hooks"))

import common
import backfill


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


@pytest.fixture
def transcript_dir(tmp_path):
    """テスト用のトランスクリプトディレクトリ。"""
    d = tmp_path / "transcripts"
    d.mkdir()
    return d


def make_assistant_record(
    session_id: str,
    tool_blocks: list,
    timestamp: str = "2025-06-15T10:30:00Z",
) -> str:
    """assistant レコードの JSONL 行を生成する。"""
    record = {
        "type": "assistant",
        "message": {"content": tool_blocks},
        "timestamp": timestamp,
        "sessionId": session_id,
        "uuid": "test-uuid",
    }
    return json.dumps(record, ensure_ascii=False)


def make_skill_tool_use(skill_name: str, args: str = "") -> dict:
    return {
        "type": "tool_use",
        "name": "Skill",
        "input": {"skill": skill_name, "args": args},
    }


def make_agent_tool_use(subagent_type: str, prompt: str = "test") -> dict:
    return {
        "type": "tool_use",
        "name": "Agent",
        "input": {"subagent_type": subagent_type, "prompt": prompt},
    }


class TestParseTranscript:
    """parse_transcript() のテスト。"""

    def test_skill_extraction(self, transcript_dir):
        """Skill ツール呼び出しが抽出される。"""
        tf = transcript_dir / "sess-001.jsonl"
        lines = [
            make_assistant_record(
                "sess-001",
                [make_skill_tool_use("my-skill", "test.py")],
                "2025-06-15T10:30:00Z",
            )
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        results, errors = backfill.parse_transcript(tf)
        assert len(results) == 1
        assert results[0]["skill_name"] == "my-skill"
        assert results[0]["session_id"] == "sess-001"
        assert results[0]["timestamp"] == "2025-06-15T10:30:00Z"
        assert results[0]["source"] == "backfill"
        assert errors == 0

    def test_agent_extraction(self, transcript_dir):
        """Agent ツール呼び出しが抽出される。"""
        tf = transcript_dir / "sess-002.jsonl"
        lines = [
            make_assistant_record(
                "sess-002",
                [make_agent_tool_use("Explore", "codebase を探索")],
                "2025-06-15T11:00:00Z",
            )
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        results, errors = backfill.parse_transcript(tf)
        assert len(results) == 1
        assert results[0]["skill_name"] == "Agent:Explore"
        assert results[0]["subagent_type"] == "Explore"
        assert results[0]["prompt"] == "codebase を探索"
        assert results[0]["timestamp"] == "2025-06-15T11:00:00Z"
        assert results[0]["source"] == "backfill"

    def test_agent_prompt_truncated(self, transcript_dir):
        """Agent の prompt が 200 文字に切り詰められる。"""
        long_prompt = "あ" * 300
        tf = transcript_dir / "sess-003.jsonl"
        lines = [
            make_assistant_record("sess-003", [make_agent_tool_use("Explore", long_prompt)])
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        results, _ = backfill.parse_transcript(tf)
        assert len(results[0]["prompt"]) == 200

    def test_agent_missing_subagent_type(self, transcript_dir):
        """subagent_type が未指定の場合 'unknown' になる。"""
        tf = transcript_dir / "sess-004.jsonl"
        record = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Agent", "input": {"prompt": "test"}}
                ]
            },
            "timestamp": "2025-06-15T12:00:00Z",
            "sessionId": "sess-004",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        results, _ = backfill.parse_transcript(tf)
        assert results[0]["subagent_type"] == "unknown"
        assert results[0]["skill_name"] == "Agent:unknown"

    def test_agent_null_subagent_type(self, transcript_dir):
        """subagent_type が None の場合 'unknown' になる。"""
        tf = transcript_dir / "sess-005.jsonl"
        record = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Agent",
                        "input": {"subagent_type": None, "prompt": "test"},
                    }
                ]
            },
            "timestamp": "2025-06-15T12:00:00Z",
            "sessionId": "sess-005",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        results, _ = backfill.parse_transcript(tf)
        assert results[0]["subagent_type"] == "unknown"

    def test_invalid_json_skipped(self, transcript_dir):
        """不正 JSON 行はスキップされ errors がカウントされる。"""
        tf = transcript_dir / "sess-006.jsonl"
        lines = [
            "this is not valid json",
            make_assistant_record("sess-006", [make_skill_tool_use("valid-skill")]),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        results, errors = backfill.parse_transcript(tf)
        assert len(results) == 1
        assert results[0]["skill_name"] == "valid-skill"
        assert errors == 1

    def test_no_tool_use_skipped(self, transcript_dir):
        """tool_use のない assistant レコードはスキップ（エラーにならない）。"""
        tf = transcript_dir / "sess-007.jsonl"
        record = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hello"}]},
            "timestamp": "2025-06-15T12:00:00Z",
            "sessionId": "sess-007",
        }
        tf.write_text(json.dumps(record), encoding="utf-8")

        results, errors = backfill.parse_transcript(tf)
        assert len(results) == 0
        assert errors == 0

    def test_non_assistant_records_ignored(self, transcript_dir):
        """type != 'assistant' のレコードは無視される。"""
        tf = transcript_dir / "sess-008.jsonl"
        lines = [
            json.dumps({"type": "queue-operation", "timestamp": "2025-06-15T10:00:00Z", "sessionId": "sess-008"}),
            json.dumps({"type": "human", "timestamp": "2025-06-15T10:01:00Z", "sessionId": "sess-008"}),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        results, errors = backfill.parse_transcript(tf)
        assert len(results) == 0
        assert errors == 0

    def test_multiple_tool_uses_in_one_record(self, transcript_dir):
        """1つの assistant レコードに複数の tool_use がある場合、全て抽出される。"""
        tf = transcript_dir / "sess-009.jsonl"
        lines = [
            make_assistant_record(
                "sess-009",
                [
                    make_skill_tool_use("skill-a"),
                    make_agent_tool_use("Explore"),
                    make_skill_tool_use("skill-b"),
                ],
            )
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        results, _ = backfill.parse_transcript(tf)
        assert len(results) == 3
        assert results[0]["skill_name"] == "skill-a"
        assert results[1]["skill_name"] == "Agent:Explore"
        assert results[2]["skill_name"] == "skill-b"

    def test_timestamp_from_record(self, transcript_dir):
        """timestamp はレコードのトップレベル timestamp から取得される。"""
        tf = transcript_dir / "sess-010.jsonl"
        lines = [
            make_assistant_record("sess-010", [make_skill_tool_use("ts-test")], "2025-12-25T00:00:00Z"),
        ]
        tf.write_text("\n".join(lines), encoding="utf-8")

        results, _ = backfill.parse_transcript(tf)
        assert results[0]["timestamp"] == "2025-12-25T00:00:00Z"


class TestDeduplication:
    """重複防止のテスト。"""

    def test_already_backfilled_session_skipped(self, patch_data_dir, transcript_dir):
        """バックフィル済みセッションはスキップされる。"""
        # 既存バックフィルデータを作成
        usage_file = patch_data_dir / "usage.jsonl"
        existing = {"skill_name": "old", "session_id": "sess-001", "source": "backfill"}
        usage_file.write_text(json.dumps(existing) + "\n", encoding="utf-8")

        # トランスクリプトを作成
        tf = transcript_dir / "sess-001.jsonl"
        tf.write_text(
            make_assistant_record("sess-001", [make_skill_tool_use("new-skill")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["skipped_sessions"] == 1
        assert summary["sessions_processed"] == 0
        # 既存データが増えていないことを確認
        lines = usage_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_new_session_processed(self, patch_data_dir, transcript_dir):
        """新しいセッションは処理される。"""
        tf = transcript_dir / "sess-new.jsonl"
        tf.write_text(
            make_assistant_record("sess-new", [make_skill_tool_use("my-skill")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["sessions_processed"] == 1
        assert summary["skill_calls"] == 1

    def test_force_reprocesses_all(self, patch_data_dir, transcript_dir):
        """--force で既存バックフィルを削除して再処理する。"""
        usage_file = patch_data_dir / "usage.jsonl"
        existing_backfill = {"skill_name": "old", "session_id": "sess-001", "source": "backfill"}
        existing_realtime = {"skill_name": "realtime", "session_id": "sess-001", "source": "hook"}
        usage_file.write_text(
            json.dumps(existing_backfill) + "\n" + json.dumps(existing_realtime) + "\n",
            encoding="utf-8",
        )

        tf = transcript_dir / "sess-001.jsonl"
        tf.write_text(
            make_assistant_record("sess-001", [make_skill_tool_use("new-skill")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=True)

        assert summary["sessions_processed"] == 1
        assert summary["skipped_sessions"] == 0

        # リアルタイムデータは残り、新しいバックフィルデータが追加されている
        lines = usage_file.read_text(encoding="utf-8").strip().splitlines()
        records = [json.loads(l) for l in lines]
        sources = [r.get("source") for r in records]
        assert "hook" in sources  # リアルタイムデータは保持
        assert "backfill" in sources  # 新しいバックフィルデータ


class TestSummaryOutput:
    """サマリ出力のテスト。"""

    def test_summary_format(self, patch_data_dir, transcript_dir):
        """サマリが正しい形式で返される。"""
        tf1 = transcript_dir / "sess-a.jsonl"
        tf1.write_text(
            make_assistant_record("sess-a", [
                make_skill_tool_use("skill-1"),
                make_agent_tool_use("Explore"),
            ]),
            encoding="utf-8",
        )
        tf2 = transcript_dir / "sess-b.jsonl"
        tf2.write_text(
            "invalid json line\n"
            + make_assistant_record("sess-b", [make_skill_tool_use("skill-2")]),
            encoding="utf-8",
        )

        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["sessions_processed"] == 2
        assert summary["skill_calls"] == 2
        assert summary["agent_calls"] == 1
        assert summary["errors"] == 1
        assert summary["skipped_sessions"] == 0

    def test_empty_project(self, patch_data_dir, transcript_dir):
        """トランスクリプトが空のプロジェクト。"""
        with mock.patch.object(backfill, "resolve_project_dir", return_value=transcript_dir):
            summary = backfill.backfill(force=False)

        assert summary["sessions_processed"] == 0
        assert summary["skill_calls"] == 0
        assert summary["agent_calls"] == 0


class TestResolveProjectDir:
    """resolve_project_dir() のテスト。"""

    def test_exact_match(self, tmp_path):
        """完全一致でディレクトリが見つかる。"""
        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()
        encoded_dir = projects_dir / "-Users-foo-bar"
        encoded_dir.mkdir()

        with mock.patch.object(backfill, "CLAUDE_PROJECTS_DIR", projects_dir):
            result = backfill.resolve_project_dir("/Users/foo/bar")
        assert result == encoded_dir

    def test_partial_match(self, tmp_path):
        """部分一致で検索される。"""
        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()
        encoded_dir = projects_dir / "-Users-foo-bar"
        encoded_dir.mkdir()

        with mock.patch.object(backfill, "CLAUDE_PROJECTS_DIR", projects_dir):
            result = backfill.resolve_project_dir("/Users/foo/bar")
        assert result == encoded_dir

    def test_not_found_raises(self, tmp_path):
        """見つからない場合は FileNotFoundError。"""
        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()

        with mock.patch.object(backfill, "CLAUDE_PROJECTS_DIR", projects_dir):
            with pytest.raises(FileNotFoundError):
                backfill.resolve_project_dir("/nonexistent/path")
