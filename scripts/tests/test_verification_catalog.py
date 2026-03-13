"""Tests for verification_catalog and issue_schema verification extensions."""
import os
import sys
from pathlib import Path

import pytest

# ── path setup ────────────────────────────────────────
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.verification_catalog import (
    DATA_CONTRACT_MIN_PATTERNS,
    EXCLUDE_DIRS,
    LARGE_REPO_FILE_THRESHOLD,
    SIDE_EFFECT_MIN_PATTERNS,
    VERIFICATION_CATALOG,
    _detect_primary_language,
    _has_cross_module_pattern,
    _is_test_file,
    _iter_source_files,
    check_verification_installed,
    detect_data_contract_verification,
    detect_side_effect_verification,
    detect_verification_needs,
    get_rule_template,
)
from lib.issue_schema import (
    VERIFICATION_RULE_CANDIDATE,
    VRC_CATALOG_ID,
    VRC_DETECTION_CONFIDENCE,
    VRC_DESCRIPTION,
    VRC_EVIDENCE,
    VRC_RULE_FILENAME,
    VRC_RULE_TEMPLATE,
    make_verification_rule_issue,
)


# ── helpers ───────────────────────────────────────────

_PY_CROSS_MODULE = """\
from foo.bar import baz

result = {"key": baz()}
"""

_PY_NO_PATTERN = """\
x = 1
y = 2
"""

_TS_CROSS_MODULE = """\
import { fetchData } from "../api";

const result = {
  data: fetchData(),
};
"""


def _create_py_files(tmp_path: Path, count: int, cross_module: bool = True) -> None:
    """tmp_path に Python ファイルを count 個作成する。"""
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    content = _PY_CROSS_MODULE if cross_module else _PY_NO_PATTERN
    for i in range(count):
        (src / f"mod_{i}.py").write_text(content)


def _create_ts_files(tmp_path: Path, count: int) -> None:
    """tmp_path に TypeScript ファイルを count 個作成する。"""
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    for i in range(count):
        (src / f"mod_{i}.ts").write_text(_TS_CROSS_MODULE)


# ══════════════════════════════════════════════════════
# VERIFICATION_CATALOG 構造チェック
# ══════════════════════════════════════════════════════


class TestCatalogStructure:
    """カタログ定義の構造テスト。"""

    REQUIRED_FIELDS = {"id", "type", "description", "rule_template", "rule_filename", "applicability"}

    def test_required_fields_present(self):
        for entry in VERIFICATION_CATALOG:
            missing = self.REQUIRED_FIELDS - set(entry.keys())
            assert not missing, f"entry {entry.get('id')} missing fields: {missing}"

    def test_rule_filename_unique(self):
        filenames = [e["rule_filename"] for e in VERIFICATION_CATALOG]
        assert len(filenames) == len(set(filenames)), "duplicate rule_filename found"

    def test_id_unique(self):
        ids = [e["id"] for e in VERIFICATION_CATALOG]
        assert len(ids) == len(set(ids)), "duplicate id found"

    def test_conditional_has_detection_fn(self):
        for entry in VERIFICATION_CATALOG:
            if entry["applicability"] == "conditional":
                assert "detection_fn" in entry, f"{entry['id']} is conditional but has no detection_fn"


# ══════════════════════════════════════════════════════
# check_verification_installed
# ══════════════════════════════════════════════════════


class TestCheckVerificationInstalled:
    def test_installed_returns_true(self, tmp_path):
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "verify-data-contract.md").write_text("# rule")

        entry = {"rule_filename": "verify-data-contract.md"}
        assert check_verification_installed(entry, tmp_path) is True

    def test_not_installed_returns_false(self, tmp_path):
        entry = {"rule_filename": "verify-data-contract.md"}
        assert check_verification_installed(entry, tmp_path) is False

    def test_empty_filename_returns_false(self, tmp_path):
        entry = {"rule_filename": ""}
        assert check_verification_installed(entry, tmp_path) is False


# ══════════════════════════════════════════════════════
# detect_data_contract_verification
# ══════════════════════════════════════════════════════


class TestDetectDataContractVerification:
    def test_above_threshold(self, tmp_path):
        _create_py_files(tmp_path, DATA_CONTRACT_MIN_PATTERNS + 1)
        result = detect_data_contract_verification(tmp_path)
        assert result["applicable"] is True
        assert len(result["evidence"]) >= DATA_CONTRACT_MIN_PATTERNS
        assert 0.0 < result["confidence"] <= 0.7

    def test_below_threshold(self, tmp_path):
        _create_py_files(tmp_path, DATA_CONTRACT_MIN_PATTERNS - 1)
        result = detect_data_contract_verification(tmp_path)
        assert result["applicable"] is False
        assert result["confidence"] == 0.0

    def test_no_pattern_files(self, tmp_path):
        _create_py_files(tmp_path, 5, cross_module=False)
        result = detect_data_contract_verification(tmp_path)
        assert result["applicable"] is False

    def test_nonexistent_dir(self, tmp_path):
        result = detect_data_contract_verification(tmp_path / "nonexistent")
        assert result["applicable"] is False
        assert result["confidence"] == 0.0

    def test_typescript_detection(self, tmp_path):
        _create_ts_files(tmp_path, DATA_CONTRACT_MIN_PATTERNS + 1)
        result = detect_data_contract_verification(tmp_path)
        assert result["applicable"] is True

    def test_evidence_max_10(self, tmp_path):
        _create_py_files(tmp_path, 15)
        result = detect_data_contract_verification(tmp_path)
        assert len(result["evidence"]) <= 10

    def test_llm_escalation_prompt_present(self, tmp_path):
        _create_py_files(tmp_path, DATA_CONTRACT_MIN_PATTERNS + 1)
        result = detect_data_contract_verification(tmp_path)
        assert "llm_escalation_prompt" in result

    def test_confidence_capped_at_07(self, tmp_path):
        _create_py_files(tmp_path, 10)
        result = detect_data_contract_verification(tmp_path)
        assert result["confidence"] <= 0.7


# ══════════════════════════════════════════════════════
# detect_verification_needs
# ══════════════════════════════════════════════════════


class TestDetectVerificationNeeds:
    def test_skips_installed(self, tmp_path):
        # ルールを設置 → スキップされる
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "verify-data-contract.md").write_text("# rule")
        _create_py_files(tmp_path, 5)

        needs = detect_verification_needs(tmp_path)
        assert len(needs) == 0

    def test_conditional_detected(self, tmp_path):
        _create_py_files(tmp_path, DATA_CONTRACT_MIN_PATTERNS + 1)
        needs = detect_verification_needs(tmp_path)
        assert len(needs) == 1
        assert needs[0]["id"] == "data-contract-verification"
        assert "detection_result" in needs[0]

    def test_conditional_not_detected(self, tmp_path):
        _create_py_files(tmp_path, 1)
        needs = detect_verification_needs(tmp_path)
        assert len(needs) == 0

    def test_nonexistent_dir(self, tmp_path):
        needs = detect_verification_needs(tmp_path / "nonexistent")
        assert needs == []


# ══════════════════════════════════════════════════════
# 言語判定
# ══════════════════════════════════════════════════════


class TestDetectPrimaryLanguage:
    def test_python_project(self, tmp_path):
        _create_py_files(tmp_path, 5)
        assert _detect_primary_language(tmp_path) == "python"

    def test_typescript_project(self, tmp_path):
        _create_ts_files(tmp_path, 5)
        assert _detect_primary_language(tmp_path) == "typescript"

    def test_equal_count_defaults_python(self, tmp_path):
        _create_py_files(tmp_path, 3)
        _create_ts_files(tmp_path, 3)
        assert _detect_primary_language(tmp_path) == "python"

    def test_empty_project(self, tmp_path):
        assert _detect_primary_language(tmp_path) == "python"


# ══════════════════════════════════════════════════════
# get_rule_template
# ══════════════════════════════════════════════════════


class TestGetRuleTemplate:
    def test_python_template(self, tmp_path):
        _create_py_files(tmp_path, 5)
        entry = VERIFICATION_CATALOG[0]
        template = get_rule_template(entry, tmp_path)
        assert "dictキー" in template

    def test_typescript_template(self, tmp_path):
        _create_ts_files(tmp_path, 5)
        entry = VERIFICATION_CATALOG[0]
        template = get_rule_template(entry, tmp_path)
        assert "interface/type" in template


# ══════════════════════════════════════════════════════
# _iter_source_files / exclude dirs
# ══════════════════════════════════════════════════════


class TestIterSourceFiles:
    def test_excludes_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.py").write_text("x = 1")
        (tmp_path / "main.py").write_text("x = 1")

        files = list(_iter_source_files(tmp_path))
        names = [f.name for f in files]
        assert "main.py" in names
        assert "index.py" not in names

    def test_excludes_pycache(self, tmp_path):
        pc = tmp_path / "__pycache__"
        pc.mkdir()
        (pc / "cached.py").write_text("x = 1")
        (tmp_path / "real.py").write_text("x = 1")

        files = list(_iter_source_files(tmp_path))
        names = [f.name for f in files]
        assert "real.py" in names
        assert "cached.py" not in names


# ══════════════════════════════════════════════════════
# _has_cross_module_pattern
# ══════════════════════════════════════════════════════


class TestHasCrossModulePattern:
    def test_python_match(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text(_PY_CROSS_MODULE)
        assert _has_cross_module_pattern(f) is True

    def test_python_no_match(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text(_PY_NO_PATTERN)
        assert _has_cross_module_pattern(f) is False

    def test_typescript_match(self, tmp_path):
        f = tmp_path / "mod.ts"
        f.write_text(_TS_CROSS_MODULE)
        assert _has_cross_module_pattern(f) is True

    def test_unknown_extension(self, tmp_path):
        f = tmp_path / "mod.rb"
        f.write_text("require 'foo'\nhash = {a: 1}")
        assert _has_cross_module_pattern(f) is False

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "missing.py"
        assert _has_cross_module_pattern(f) is False


# ══════════════════════════════════════════════════════
# issue_schema: make_verification_rule_issue
# ══════════════════════════════════════════════════════


class TestMakeVerificationRuleIssue:
    def test_basic_structure(self):
        entry = {
            "id": "data-contract-verification",
            "rule_filename": "verify-data-contract.md",
            "rule_template": "# rule content",
            "description": "desc",
        }
        detection_result = {
            "evidence": ["a.py", "b.py"],
            "confidence": 0.6,
        }
        issue = make_verification_rule_issue(entry, detection_result)
        assert issue["type"] == VERIFICATION_RULE_CANDIDATE
        assert issue["source"] == "verification_catalog"
        assert issue["file"] == "verify-data-contract.md"
        assert issue["detail"][VRC_CATALOG_ID] == "data-contract-verification"
        assert issue["detail"][VRC_EVIDENCE] == ["a.py", "b.py"]
        assert issue["detail"][VRC_DETECTION_CONFIDENCE] == 0.6

    def test_with_project_dir(self):
        entry = {
            "id": "test",
            "rule_filename": "test-rule.md",
            "rule_template": "# test",
            "description": "test desc",
        }
        issue = make_verification_rule_issue(
            entry,
            {"evidence": [], "confidence": 0.5},
            project_dir_str="/home/user/project",
        )
        assert issue["file"] == "/home/user/project/.claude/rules/test-rule.md"

    def test_missing_fields_default(self):
        issue = make_verification_rule_issue({}, {})
        assert issue["detail"][VRC_CATALOG_ID] == ""
        assert issue["detail"][VRC_RULE_FILENAME] == ""
        assert issue["detail"][VRC_EVIDENCE] == []
        assert issue["detail"][VRC_DETECTION_CONFIDENCE] == 0.0


# ══════════════════════════════════════════════════════
# Side-effect helpers
# ══════════════════════════════════════════════════════

_DB_CODE = """\
from sqlalchemy.orm import Session

def save_item(session: Session, item):
    session.add(item)
    session.commit()
"""

_MQ_CODE = """\
import boto3

sqs = boto3.client("sqs")
sqs.send_message(QueueUrl="q", MessageBody="hi")
"""

_API_CODE = """\
import requests

def notify():
    requests.post("https://hook.example.com", json={"ok": True})
"""

_INNOCUOUS_CODE = """\
x = 1
y = 2
"""


def _create_side_effect_files(tmp_path, category, count):
    """category ('db'/'mq'/'api') のコードを count 個作成。"""
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    code = {"db": _DB_CODE, "mq": _MQ_CODE, "api": _API_CODE}[category]
    for i in range(count):
        (src / f"{category}_{i}.py").write_text(code)


# ══════════════════════════════════════════════════════
# detect_side_effect_verification
# ══════════════════════════════════════════════════════


class TestDetectSideEffectVerification:
    def test_db_above_threshold(self, tmp_path):
        _create_side_effect_files(tmp_path, "db", SIDE_EFFECT_MIN_PATTERNS + 1)
        result = detect_side_effect_verification(tmp_path)
        assert result["applicable"] is True
        assert "db" in result["detected_categories"]
        assert 0.0 < result["confidence"] <= 0.7

    def test_mq_above_threshold(self, tmp_path):
        _create_side_effect_files(tmp_path, "mq", SIDE_EFFECT_MIN_PATTERNS + 1)
        result = detect_side_effect_verification(tmp_path)
        assert result["applicable"] is True
        assert "mq" in result["detected_categories"]

    def test_api_above_threshold(self, tmp_path):
        _create_side_effect_files(tmp_path, "api", SIDE_EFFECT_MIN_PATTERNS + 1)
        result = detect_side_effect_verification(tmp_path)
        assert result["applicable"] is True
        assert "api" in result["detected_categories"]

    def test_below_threshold(self, tmp_path):
        _create_side_effect_files(tmp_path, "db", SIDE_EFFECT_MIN_PATTERNS - 1)
        result = detect_side_effect_verification(tmp_path)
        assert result["applicable"] is False

    def test_test_files_excluded(self, tmp_path):
        """テストファイルのみに副作用パターンがある場合は検出しない。"""
        src = tmp_path / "src"
        src.mkdir(exist_ok=True)
        for i in range(5):
            (src / f"test_handler_{i}.py").write_text(_DB_CODE)
        result = detect_side_effect_verification(tmp_path)
        assert result["applicable"] is False

    def test_test_dir_excluded(self, tmp_path):
        """__tests__/ 配下は除外される。"""
        tests_dir = tmp_path / "src" / "__tests__"
        tests_dir.mkdir(parents=True)
        for i in range(5):
            (tests_dir / f"handler_{i}.py").write_text(_DB_CODE)
        result = detect_side_effect_verification(tmp_path)
        assert result["applicable"] is False

    def test_empty_project(self, tmp_path):
        result = detect_side_effect_verification(tmp_path)
        assert result["applicable"] is False

    def test_nonexistent_dir(self, tmp_path):
        result = detect_side_effect_verification(tmp_path / "nonexistent")
        assert result["applicable"] is False

    def test_confidence_capped_at_07(self, tmp_path):
        _create_side_effect_files(tmp_path, "db", 10)
        result = detect_side_effect_verification(tmp_path)
        assert result["confidence"] <= 0.7

    def test_evidence_is_plain_path_list(self, tmp_path):
        """evidence はプレーンなファイルパスリスト（カテゴリプレフィクスなし）。"""
        _create_side_effect_files(tmp_path, "db", SIDE_EFFECT_MIN_PATTERNS + 1)
        result = detect_side_effect_verification(tmp_path)
        for path in result["evidence"]:
            assert ":" not in path or path.count(":") == 0 or "/" in path.split(":")[0]
            # プレーンパスであること — "db: path" 形式でないこと
            assert not path.startswith("db:") and not path.startswith("mq:") and not path.startswith("api:")

    def test_detected_categories_field(self, tmp_path):
        """detected_categories が別フィールドとして存在する。"""
        _create_side_effect_files(tmp_path, "db", 2)
        _create_side_effect_files(tmp_path, "api", 2)
        result = detect_side_effect_verification(tmp_path)
        assert "detected_categories" in result
        cats = result["detected_categories"]
        assert isinstance(cats, list)
        if result["applicable"]:
            assert "db" in cats
            assert "api" in cats

    def test_llm_escalation_prompt(self, tmp_path):
        _create_side_effect_files(tmp_path, "db", SIDE_EFFECT_MIN_PATTERNS + 1)
        result = detect_side_effect_verification(tmp_path)
        assert "llm_escalation_prompt" in result
        assert "副作用" in result["llm_escalation_prompt"]

    def test_multiple_categories(self, tmp_path):
        """複数カテゴリが同時に検出される。"""
        _create_side_effect_files(tmp_path, "db", 2)
        _create_side_effect_files(tmp_path, "mq", 2)
        result = detect_side_effect_verification(tmp_path)
        assert result["applicable"] is True
        assert "db" in result["detected_categories"]
        assert "mq" in result["detected_categories"]


# ══════════════════════════════════════════════════════
# _is_test_file
# ══════════════════════════════════════════════════════


class TestIsTestFile:
    def test_python_test_prefix(self):
        assert _is_test_file(Path("src/test_handler.py")) is True

    def test_python_test_suffix(self):
        assert _is_test_file(Path("src/handler_test.py")) is True

    def test_ts_test_suffix(self):
        assert _is_test_file(Path("src/handler.test.ts")) is True

    def test_tsx_test_suffix(self):
        assert _is_test_file(Path("src/component.test.tsx")) is True

    def test_tests_dir(self):
        assert _is_test_file(Path("src/__tests__/handler.py")) is True

    def test_normal_file(self):
        assert _is_test_file(Path("src/handler.py")) is False


# ══════════════════════════════════════════════════════
# check_verification_installed: content-aware
# ══════════════════════════════════════════════════════


class TestCheckVerificationInstalledContentAware:
    def test_filename_match(self, tmp_path):
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "verify-side-effects.md").write_text("# rule")
        entry = {"id": "side-effect-verification", "rule_filename": "verify-side-effects.md"}
        assert check_verification_installed(entry, tmp_path) is True

    def test_content_keyword_ja(self, tmp_path):
        """verify-side-effects.md は無いが、verification.md に「副作用」があるケース。"""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "verification.md").write_text("# 検証ルール\n副作用も確認する。")
        entry = {"id": "side-effect-verification", "rule_filename": "verify-side-effects.md"}
        assert check_verification_installed(entry, tmp_path) is True

    def test_content_keyword_en(self, tmp_path):
        """'side effect' キーワードでマッチ。"""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "testing.md").write_text("Check for side effect in tests.")
        entry = {"id": "side-effect-verification", "rule_filename": "verify-side-effects.md"}
        assert check_verification_installed(entry, tmp_path) is True

    def test_no_match(self, tmp_path):
        """ファイルもキーワードもない。"""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "other.md").write_text("# Some other rule")
        entry = {"id": "side-effect-verification", "rule_filename": "verify-side-effects.md"}
        assert check_verification_installed(entry, tmp_path) is False

    def test_non_side_effect_entry_skips_content_check(self, tmp_path):
        """data-contract-verification は content-aware チェックをしない。"""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "other.md").write_text("副作用チェック")
        entry = {"id": "data-contract-verification", "rule_filename": "verify-data-contract.md"}
        assert check_verification_installed(entry, tmp_path) is False


# ══════════════════════════════════════════════════════
# side-effect-verification カタログエントリの構造確認
# ══════════════════════════════════════════════════════


class TestSideEffectCatalogEntry:
    def test_entry_exists(self):
        ids = [e["id"] for e in VERIFICATION_CATALOG]
        assert "side-effect-verification" in ids

    def test_rule_template_3_lines(self):
        entry = next(e for e in VERIFICATION_CATALOG if e["id"] == "side-effect-verification")
        lines = entry["rule_template"].strip().split("\n")
        assert len(lines) <= 3

    def test_language_independent_template(self, tmp_path):
        """side-effect-verification は言語非依存テンプレートを返す。"""
        entry = next(e for e in VERIFICATION_CATALOG if e["id"] == "side-effect-verification")
        _create_py_files(tmp_path, 5)
        py_template = get_rule_template(entry, tmp_path)
        # TypeScript プロジェクトでも同一テンプレート
        ts_dir = tmp_path / "ts_proj"
        ts_dir.mkdir()
        _create_ts_files(ts_dir, 5)
        ts_template = get_rule_template(entry, ts_dir)
        assert py_template == ts_template
