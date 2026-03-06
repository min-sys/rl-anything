"""hardcoded_detector のユニットテスト。"""
import sys
from pathlib import Path

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))

from hardcoded_detector import compute_confidence_score, detect_hardcoded_values


@pytest.fixture
def tmp_md(tmp_path):
    """一時 Markdown ファイルを作成するヘルパー。"""
    def _create(content: str) -> str:
        f = tmp_path / "test.md"
        f.write_text(content, encoding="utf-8")
        return str(f)
    return _create


# ---------- パターン検出テスト ----------

class TestDetectPatterns:
    def test_slack_id(self, tmp_md):
        path = tmp_md("slack_app_id: A04K8RZLM3Q")
        results = detect_hardcoded_values(path)
        assert len(results) >= 1
        slack = [r for r in results if r["pattern_type"] == "slack_id"]
        assert len(slack) == 1
        assert slack[0]["matched"] == "A04K8RZLM3Q"
        assert slack[0]["line"] == 1

    def test_aws_arn(self, tmp_md):
        path = tmp_md("resource: arn:aws:lambda:ap-northeast-1:123456789012:function:my-func")
        results = detect_hardcoded_values(path)
        arn = [r for r in results if r["pattern_type"] == "aws_arn"]
        assert len(arn) == 1
        assert "arn:aws:lambda" in arn[0]["matched"]

    def test_api_key_xoxb(self, tmp_md):
        path = tmp_md("token: xoxb-1234567890-abcdefghij")
        results = detect_hardcoded_values(path)
        api = [r for r in results if r["pattern_type"] == "api_key"]
        assert len(api) == 1
        assert api[0]["matched"].startswith("xoxb-")

    def test_api_key_akia(self, tmp_md):
        path = tmp_md("aws_key: AKIAIOSFODNN7EXAMPLE")
        results = detect_hardcoded_values(path)
        api = [r for r in results if r["pattern_type"] == "api_key"]
        assert len(api) == 1

    def test_service_url(self, tmp_md):
        path = tmp_md("webhook: https://hooks.slack.com/services/T00000000/B00000000/xxxx")
        results = detect_hardcoded_values(path)
        url = [r for r in results if r["pattern_type"] == "service_url"]
        assert len(url) == 1

    def test_numeric_id(self, tmp_md):
        path = tmp_md("account: 123456789012")
        results = detect_hardcoded_values(path)
        num = [r for r in results if r["pattern_type"] == "numeric_id"]
        assert len(num) >= 1

    def test_result_format(self, tmp_md):
        path = tmp_md("slack_app_id: A04K8RZLM3Q")
        results = detect_hardcoded_values(path)
        assert len(results) >= 1
        r = results[0]
        assert "line" in r
        assert "matched" in r
        assert "pattern_type" in r
        assert "context" in r
        assert "confidence_score" in r
        assert isinstance(r["confidence_score"], float)


# ---------- 許容パターン除外テスト ----------

class TestExclusions:
    def test_placeholder_dollar_brace(self, tmp_md):
        path = tmp_md("export SLACK_APP_ID=${SLACK_APP_ID}")
        results = detect_hardcoded_values(path)
        assert len(results) == 0

    def test_placeholder_angle_bracket(self, tmp_md):
        path = tmp_md("app_id: <YOUR_APP_ID>")
        results = detect_hardcoded_values(path)
        assert len(results) == 0

    def test_dummy_sequential(self, tmp_md):
        path = tmp_md("例: A0123456789")
        results = detect_hardcoded_values(path)
        assert len(results) == 0

    def test_dummy_zeros(self, tmp_md):
        path = tmp_md("account: 000000000000")
        results = detect_hardcoded_values(path)
        assert len(results) == 0

    def test_localhost_url(self, tmp_md):
        path = tmp_md("url: http://localhost:3000/api/test")
        results = detect_hardcoded_values(path)
        assert len(results) == 0

    def test_example_com_url(self, tmp_md):
        path = tmp_md("url: https://api.example.com/v1/test")
        results = detect_hardcoded_values(path)
        assert len(results) == 0

    def test_version_number(self, tmp_md):
        path = tmp_md("version: 202401011234")
        results = detect_hardcoded_values(path)
        num = [r for r in results if r["pattern_type"] == "numeric_id"]
        assert len(num) == 0

    def test_semver(self, tmp_md):
        path = tmp_md("version: v1.2.3")
        results = detect_hardcoded_values(path)
        assert len(results) == 0

    def test_arithmetic(self, tmp_md):
        path = tmp_md("timeout = 1000 * 60 * 24")
        results = detect_hardcoded_values(path)
        assert len(results) == 0

    def test_timestamp_10digit(self, tmp_md):
        path = tmp_md("created_at: 1704067200")
        results = detect_hardcoded_values(path)
        num = [r for r in results if r["pattern_type"] == "numeric_id"]
        assert len(num) == 0

    def test_iso_date_adjacent(self, tmp_md):
        path = tmp_md("date: 2024-01-01 1704067200123")
        results = detect_hardcoded_values(path)
        num = [r for r in results if r["pattern_type"] == "numeric_id"]
        assert len(num) == 0


# ---------- インライン抑制テスト ----------

class TestSuppression:
    def test_suppressed_line(self, tmp_md):
        path = tmp_md("slack_app_id: A04K8RZLM3Q <!-- rl-allow: hardcoded -->")
        results = detect_hardcoded_values(path)
        assert len(results) == 0

    def test_suppression_only_affects_same_line(self, tmp_md):
        path = tmp_md("<!-- rl-allow: hardcoded -->\nslack_app_id: A04K8RZLM3Q")
        results = detect_hardcoded_values(path)
        slack = [r for r in results if r["pattern_type"] == "slack_id"]
        assert len(slack) == 1
        assert slack[0]["line"] == 2


# ---------- エラーハンドリングテスト ----------

class TestErrorHandling:
    def test_nonexistent_file(self):
        results = detect_hardcoded_values("/nonexistent/file.md")
        assert results == []

    def test_binary_file(self, tmp_path):
        f = tmp_path / "binary.md"
        f.write_bytes(b"some\x00binary\x00content")
        results = detect_hardcoded_values(str(f))
        assert results == []

    def test_permission_error(self, tmp_path):
        f = tmp_path / "noperm.md"
        f.write_text("A04K8RZLM3Q")
        f.chmod(0o000)
        try:
            results = detect_hardcoded_values(str(f))
            assert results == []
        finally:
            f.chmod(0o644)


# ---------- confidence_score テスト ----------

class TestConfidenceScore:
    def test_api_key_confidence(self):
        assert compute_confidence_score("api_key") == 0.85

    def test_aws_arn_confidence(self):
        assert compute_confidence_score("aws_arn") == 0.75

    def test_slack_id_confidence(self):
        assert compute_confidence_score("slack_id") == 0.65

    def test_service_url_confidence(self):
        assert compute_confidence_score("service_url") == 0.55

    def test_numeric_id_confidence(self):
        assert compute_confidence_score("numeric_id") == 0.45

    def test_unknown_type_confidence(self):
        assert compute_confidence_score("unknown") == 0.5

    def test_detection_includes_confidence(self, tmp_md):
        path = tmp_md("slack_app_id: A04K8RZLM3Q")
        results = detect_hardcoded_values(path)
        assert results[0]["confidence_score"] == 0.65


# ---------- extra_patterns / extra_allowlist テスト ----------

class TestExtensibility:
    def test_extra_pattern(self, tmp_md):
        path = tmp_md("custom_id: CUST-12345-ABCDE")
        extra = [{"name": "custom_id", "regex": r"CUST-\d{5}-[A-Z]{5}", "confidence": 0.7}]
        results = detect_hardcoded_values(path, extra_patterns=extra)
        custom = [r for r in results if r["pattern_type"] == "custom_id"]
        assert len(custom) == 1
        assert custom[0]["confidence_score"] == 0.7

    def test_extra_allowlist(self, tmp_md):
        path = tmp_md("slack_app_id: A04K8RZLM3Q")
        results = detect_hardcoded_values(path, extra_allowlist=[r"A04K8RZLM3Q"])
        assert len(results) == 0

    def test_extra_pattern_with_compiled_regex(self, tmp_md):
        import re
        path = tmp_md("token: MY-SECRET-TOKEN-123")
        extra = [{"name": "my_token", "regex": re.compile(r"MY-SECRET-TOKEN-\d+"), "confidence": 0.9}]
        results = detect_hardcoded_values(path, extra_patterns=extra)
        assert len([r for r in results if r["pattern_type"] == "my_token"]) == 1
