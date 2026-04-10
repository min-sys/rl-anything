"""correction_detect hooks のユニットテスト。"""
import json
import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common
import correction_detect


@pytest.fixture
def tmp_data_dir(tmp_path):
    data_dir = tmp_path / "rl-anything"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def patch_data_dir(tmp_data_dir):
    with mock.patch.object(common, "DATA_DIR", tmp_data_dir):
        yield tmp_data_dir


class TestDetectCorrection:
    """common.detect_correction() のテスト。"""

    def test_iya_pattern(self):
        result = common.detect_correction("いや、そうじゃなくて optimize を使って")
        assert result is not None
        assert result[0] == "iya"
        assert result[1] == 0.85

    def test_chigau_pattern(self):
        result = common.detect_correction("違う、そのアプローチではない")
        assert result is not None
        assert result[0] == "chigau"
        assert result[1] == 0.85

    def test_souja_nakute_pattern(self):
        result = common.detect_correction("そうじゃなくてこっちを使う")
        assert result is not None
        assert result[0] == "souja-nakute"
        assert result[1] == 0.80

    def test_no_pattern(self):
        result = common.detect_correction("no, don't use that approach")
        assert result is not None
        assert result[0] == "no"
        assert result[1] == 0.70

    def test_dont_pattern(self):
        result = common.detect_correction("don't do that")
        assert result is not None
        assert result[0] == "dont"
        assert result[1] == 0.70

    def test_stop_pattern(self):
        result = common.detect_correction("stop doing that")
        assert result is not None
        assert result[0] == "stop"
        assert result[1] == 0.70

    def test_no_match(self):
        result = common.detect_correction("ありがとう、完璧です")
        assert result is None

    def test_empty_string(self):
        result = common.detect_correction("")
        assert result is None

    def test_question_excluded(self):
        """疑問文は除外される。"""
        result = common.detect_correction("いや、それでいいの？")
        assert result is None

    def test_question_mark_ascii(self):
        result = common.detect_correction("no, is that right?")
        assert result is None


class TestNewPatterns:
    """claude-reflect 由来のパターン検出テスト。"""

    def test_remember_explicit(self):
        result = common.detect_correction("remember: always use bun")
        assert result is not None
        assert result[0] == "remember"
        assert result[1] == 0.90

    def test_guardrail_dont_unless(self):
        result = common.detect_correction("don't add comments unless I ask")
        assert result is not None
        assert result[0] == "dont-unless-asked"
        assert result[1] == 0.90

    def test_guardrail_minimal_changes(self):
        result = common.detect_correction("minimal changes please")
        assert result is not None
        assert result[0] == "minimal-changes"

    def test_positive_perfect(self):
        result = common.detect_correction("perfect! that's what I wanted")
        assert result is not None
        assert result[0] == "perfect"
        assert result[1] == 0.70

    def test_positive_excellent(self):
        result = common.detect_correction("excellent work on this")
        assert result is not None
        assert result[0] == "keep-doing"

    def test_thats_wrong(self):
        result = common.detect_correction("that's wrong, use the other approach")
        assert result is not None
        assert result[0] == "thats-wrong"

    def test_i_told_you(self):
        result = common.detect_correction("I told you to use bun")
        assert result is not None
        assert result[0] == "I-told-you"
        assert result[1] == 0.85

    def test_use_x_not_y(self):
        result = common.detect_correction("use Python not JavaScript")
        assert result is not None
        assert result[0] == "use-X-not-Y"

    def test_actually_weak(self):
        result = common.detect_correction("actually, try the other way")
        assert result is not None
        assert result[0] == "actually"
        assert result[1] == 0.55

    def test_i_meant(self):
        result = common.detect_correction("I meant to use TypeScript")
        assert result is not None
        assert result[0] == "I-meant"


class TestFalsePositiveFilters:
    """偽陽性フィルタのテスト。"""

    def test_please_filtered(self):
        result = common.detect_correction("please help me fix this")
        assert result is None

    def test_can_you_filtered(self):
        result = common.detect_correction("can you fix this error?")
        assert result is None

    def test_error_description_filtered(self):
        result = common.detect_correction("error: could not connect to database")
        assert result is None

    def test_bug_report_filtered(self):
        result = common.detect_correction("the test is not passing")
        assert result is None

    def test_i_need_filtered(self):
        result = common.detect_correction("I need you to fix the API")
        assert result is None

    def test_ok_continuation_filtered(self):
        result = common.detect_correction("okay, so let me try again")
        assert result is None

    def test_remember_bypass(self):
        """remember: は偽陽性フィルタをバイパスする。"""
        result = common.detect_correction("remember: always use bun for package management")
        assert result is not None
        assert result[0] == "remember"


class TestShouldIncludeMessage:
    """should_include_message() のテスト。"""

    def test_normal_text(self):
        assert common.should_include_message("いや、違うよ") is True

    def test_xml_tag(self):
        assert common.should_include_message("<system-reminder>test</system-reminder>") is False

    def test_json(self):
        assert common.should_include_message('{"key": "value"}') is False

    def test_tool_result(self):
        assert common.should_include_message("tool_result: success") is False

    def test_session_continuation(self):
        assert common.should_include_message("This session is being continued from a previous") is False

    def test_empty(self):
        assert common.should_include_message("") is False

    def test_long_text_excluded(self):
        assert common.should_include_message("x" * 501) is False

    def test_remember_bypasses_length(self):
        assert common.should_include_message("remember: " + "x" * 500) is True


class TestCalculateConfidence:
    """calculate_confidence() のテスト。"""

    def test_short_text_boost(self):
        conf, _ = common.calculate_confidence(0.70, "short")
        assert conf == pytest.approx(0.80)  # +0.10

    def test_long_text_penalty(self):
        conf, _ = common.calculate_confidence(0.70, "x" * 301)
        assert conf == pytest.approx(0.55)  # -0.15

    def test_medium_text_penalty(self):
        conf, _ = common.calculate_confidence(0.70, "x" * 200)
        assert conf == pytest.approx(0.60)  # -0.10

    def test_multiple_patterns_high(self):
        conf, decay = common.calculate_confidence(0.70, "short", matched_count=3)
        assert conf == pytest.approx(0.90)  # 0.85 + 0.10 short boost, capped at 0.90
        assert decay == 120

    def test_i_told_you_flag(self):
        conf, decay = common.calculate_confidence(0.70, "short", has_i_told_you=True)
        assert conf == pytest.approx(0.90)  # 0.85 + 0.10, capped
        assert decay == 120

    def test_single_strong(self):
        conf, decay = common.calculate_confidence(0.55, "short", has_strong=True)
        assert conf == pytest.approx(0.80)  # max(0.55, 0.70) + 0.10
        assert decay == 60


class TestDetectAllPatterns:
    """detect_all_patterns() のテスト。"""

    def test_single_match(self):
        result = common.detect_all_patterns("いや、違うよ")
        assert "iya" in result

    def test_multiple_matches(self):
        result = common.detect_all_patterns("don't use npm, use bun not npm")
        assert "dont" in result
        assert "use-X-not-Y" in result

    def test_no_match(self):
        result = common.detect_all_patterns("ありがとう")
        assert result == []

    def test_question_excluded(self):
        result = common.detect_all_patterns("いや、それでいいの？")
        assert result == []


class TestDetectCorrectionReturnType:
    """detect_correction() 戻り値型の互換テスト (Task 1.6)。"""

    def test_tuple_return(self):
        result = common.detect_correction("いや、違う")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_unpack_backfill_style(self):
        """backfill.py の correction_type, _ = result アンパック。"""
        result = common.detect_correction("いや、違う")
        correction_type, _ = result
        assert correction_type == "iya"

    def test_index_access(self):
        """test_correction_detect.py の result[0] アクセス。"""
        result = common.detect_correction("いや、違う")
        assert result[0] == "iya"
        assert isinstance(result[1], float)


class TestLastSkill:
    """common.write_last_skill / read_last_skill のテスト。"""

    def test_write_and_read(self, tmp_path):
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            common.write_last_skill("sess-ls-001", "commit")
            result = common.read_last_skill("sess-ls-001")
            assert result == "commit"

    def test_read_nonexistent(self, tmp_path):
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            result = common.read_last_skill("sess-ls-none")
            assert result is None

    def test_read_expired(self, tmp_path):
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            common.write_last_skill("sess-ls-exp", "test")
            path = common.last_skill_path("sess-ls-exp")
            old_time = time.time() - (25 * 60 * 60)
            os.utime(path, (old_time, old_time))
            result = common.read_last_skill("sess-ls-exp")
            assert result is None


class TestCorrectionDetectHook:
    """correction_detect.py のフックテスト。"""

    def test_japanese_correction_detected(self, patch_data_dir):
        event = {
            "session_id": "sess-cd-001",
            "message": {"content": "いや、そうじゃなくて skill-evolve を使って"},
        }
        correction_detect.handle_user_prompt_submit(event)

        corrections_file = patch_data_dir / "corrections.jsonl"
        assert corrections_file.exists()
        record = json.loads(corrections_file.read_text().strip())
        assert record["correction_type"] == "iya"
        assert record["confidence"] == 0.85
        assert record["session_id"] == "sess-cd-001"
        assert record["last_skill"] is None

    def test_english_correction_detected(self, patch_data_dir):
        event = {
            "session_id": "sess-cd-002",
            "message": {"content": "No, don't use that approach"},
        }
        correction_detect.handle_user_prompt_submit(event)

        corrections_file = patch_data_dir / "corrections.jsonl"
        assert corrections_file.exists()
        record = json.loads(corrections_file.read_text().strip())
        assert record["correction_type"] == "no"

    def test_question_not_detected(self, patch_data_dir):
        """疑問文は corrections に追記されない。"""
        event = {
            "session_id": "sess-cd-003",
            "message": {"content": "いや、それでいいの？"},
        }
        correction_detect.handle_user_prompt_submit(event)

        corrections_file = patch_data_dir / "corrections.jsonl"
        assert not corrections_file.exists()

    def test_no_correction_for_normal_text(self, patch_data_dir):
        event = {
            "session_id": "sess-cd-004",
            "message": {"content": "ありがとう、完璧です"},
        }
        correction_detect.handle_user_prompt_submit(event)

        corrections_file = patch_data_dir / "corrections.jsonl"
        assert not corrections_file.exists()

    def test_with_last_skill(self, patch_data_dir, tmp_path):
        """直前スキルが紐付けられる。"""
        with mock.patch.dict(os.environ, {"TMPDIR": str(tmp_path)}):
            common.write_last_skill("sess-cd-005", "commit")
            event = {
                "session_id": "sess-cd-005",
                "message": {"content": "いや、違うコマンドを使って"},
            }
            correction_detect.handle_user_prompt_submit(event)

        corrections_file = patch_data_dir / "corrections.jsonl"
        record = json.loads(corrections_file.read_text().strip())
        assert record["last_skill"] == "commit"

    def test_schema_compliance(self, patch_data_dir):
        """レコードが拡張スキーマに準拠する。"""
        event = {
            "session_id": "sess-cd-schema",
            "message": {"content": "いや、そうじゃなくて"},
        }
        correction_detect.handle_user_prompt_submit(event)

        corrections_file = patch_data_dir / "corrections.jsonl"
        record = json.loads(corrections_file.read_text().strip())
        # 全必須フィールドの存在チェック
        assert "correction_type" in record
        assert "matched_patterns" in record
        assert "message" in record
        assert "last_skill" in record
        assert "confidence" in record
        assert "sentiment" in record
        assert "decay_days" in record
        assert "guardrail" in record
        assert "reflect_status" in record
        assert "project_path" in record
        assert "timestamp" in record
        assert "session_id" in record
        # source フィールドは "hook" が MUST
        assert record["source"] == "hook"
        assert record["reflect_status"] == "pending"

    def test_silent_failure_on_bad_json(self, patch_data_dir, capsys):
        """不正 JSON でも exit 0（サイレント失敗）。"""
        # main() をテスト
        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "NOT VALID JSON{{{"
            correction_detect.main()
        captured = capsys.readouterr()
        assert "[rl-anything:correction] parse error" in captured.err

    def test_empty_session_id_noop(self, patch_data_dir):
        event = {
            "session_id": "",
            "message": {"content": "いや、違う"},
        }
        correction_detect.handle_user_prompt_submit(event)
        corrections_file = patch_data_dir / "corrections.jsonl"
        assert not corrections_file.exists()

    def test_content_as_list(self, patch_data_dir):
        """content がリスト形式でも処理できる。"""
        event = {
            "session_id": "sess-cd-list",
            "message": {
                "content": [
                    {"type": "text", "text": "いや、違うよ"}
                ]
            },
        }
        correction_detect.handle_user_prompt_submit(event)
        corrections_file = patch_data_dir / "corrections.jsonl"
        assert corrections_file.exists()


class TestSessionTitle:
    """hookSpecificOutput.sessionTitle 出力のテスト (CC v2.1.94+)."""

    def test_session_title_on_remember(self, patch_data_dir, capsys):
        """explicit パターン（remember:）で sessionTitle を JSON 出力する。"""
        event = {
            "session_id": "sess-st-001",
            "message": {"content": "remember: always use bun"},
        }
        correction_detect.handle_user_prompt_submit(event)
        captured = capsys.readouterr()
        out = captured.out.strip()
        assert out.startswith("{"), f"expected JSON output, got: {out!r}"
        data = json.loads(out)
        assert "hookSpecificOutput" in data
        assert "sessionTitle" in data["hookSpecificOutput"]
        title = data["hookSpecificOutput"]["sessionTitle"]
        assert "remember" in title

    def test_session_title_on_guardrail(self, patch_data_dir, capsys):
        """guardrail パターンで sessionTitle を出力する。"""
        event = {
            "session_id": "sess-st-002",
            "message": {"content": "don't add comments unless I ask"},
        }
        correction_detect.handle_user_prompt_submit(event)
        captured = capsys.readouterr()
        out = captured.out.strip()
        data = json.loads(out)
        assert "hookSpecificOutput" in data
        assert "sessionTitle" in data["hookSpecificOutput"]

    def test_no_session_title_on_regular_correction(self, patch_data_dir, capsys):
        """通常の correction パターン（iya）では sessionTitle を出力しない。"""
        event = {
            "session_id": "sess-st-003",
            "message": {"content": "いや、そうじゃなくて"},
        }
        correction_detect.handle_user_prompt_submit(event)
        captured = capsys.readouterr()
        out = captured.out.strip()
        # 通常 correction は sessionTitle を emit しない
        # trigger message（plain text）は許容、JSON sessionTitle は不可
        if out.startswith("{"):
            data = json.loads(out)
            assert "sessionTitle" not in data.get("hookSpecificOutput", {})

    def test_no_session_title_on_positive(self, patch_data_dir, capsys):
        """positive パターンでも sessionTitle は出さない（ノイズ防止）。"""
        event = {
            "session_id": "sess-st-pos",
            "message": {"content": "perfect! that's exactly what I wanted"},
        }
        correction_detect.handle_user_prompt_submit(event)
        captured = capsys.readouterr()
        out = captured.out.strip()
        if out.startswith("{"):
            data = json.loads(out)
            assert "sessionTitle" not in data.get("hookSpecificOutput", {})

    def test_no_output_on_no_match(self, patch_data_dir, capsys):
        """correction パターン非該当時は一切出力しない。"""
        event = {
            "session_id": "sess-st-004",
            "message": {"content": "hello world"},
        }
        correction_detect.handle_user_prompt_submit(event)
        captured = capsys.readouterr()
        assert captured.out.strip() == ""

    def test_session_title_length_cap(self, patch_data_dir, capsys):
        """sessionTitle は 80 chars 以内に収まる。"""
        long_message = "remember: " + ("とても長い指示 " * 20)
        event = {
            "session_id": "sess-st-005",
            "message": {"content": long_message},
        }
        correction_detect.handle_user_prompt_submit(event)
        captured = capsys.readouterr()
        data = json.loads(captured.out.strip())
        title = data["hookSpecificOutput"]["sessionTitle"]
        assert len(title) <= 80

    def test_session_title_ascii_json_safe(self, patch_data_dir, capsys):
        """日本語を含む title も UTF-8 JSON として往復できる。"""
        event = {
            "session_id": "sess-st-006",
            "message": {"content": "remember: 常に bun を使う"},
        }
        correction_detect.handle_user_prompt_submit(event)
        captured = capsys.readouterr()
        out = captured.out.strip()
        data = json.loads(out)  # round-trip parse
        title = data["hookSpecificOutput"]["sessionTitle"]
        assert "bun" in title
