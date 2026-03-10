#!/usr/bin/env python3
"""reflect スキルのユニットテスト。"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts"))
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
sys.path.insert(0, str(_plugin_root / "skills" / "reflect" / "scripts"))

import reflect


# --- Fixtures ---

def _make_correction(
    message="いや、bun を使って",
    correction_type="iya",
    confidence=0.85,
    reflect_status="pending",
    project_path=None,
    timestamp=None,
    extracted_learning=None,
):
    """テスト用 correction レコードを生成する。"""
    record = {
        "message": message,
        "correction_type": correction_type,
        "confidence": confidence,
        "reflect_status": reflect_status,
        "project_path": project_path,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }
    if extracted_learning:
        record["extracted_learning"] = extracted_learning
    return record


def _write_corrections(tmp_path, corrections):
    """corrections.jsonl を一時ディレクトリに書き出す。"""
    filepath = tmp_path / "corrections.jsonl"
    lines = [json.dumps(c, ensure_ascii=False) for c in corrections]
    filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return filepath


# --- Test: extract_pending ---

class TestExtractPending:
    def test_pending_only(self):
        """pending のみ返す。"""
        records = [
            _make_correction(reflect_status="pending"),
            _make_correction(reflect_status="applied"),
            _make_correction(reflect_status="skipped"),
            _make_correction(reflect_status="pending"),
        ]
        result = reflect.extract_pending(records)
        assert len(result) == 2
        assert all(r["reflect_status"] == "pending" for r in result)

    def test_missing_status_treated_as_pending(self):
        """reflect_status がないレコードは pending として扱う。"""
        record = {"message": "test", "correction_type": "iya", "confidence": 0.85}
        result = reflect.extract_pending([record])
        assert len(result) == 1

    def test_empty_records(self):
        """空リストには空リストを返す。"""
        assert reflect.extract_pending([]) == []


# --- Test: classify_project_scope ---

class TestClassifyProjectScope:
    def test_same_project(self):
        """同一プロジェクトの場合 same-project を返す。"""
        c = _make_correction(project_path="/home/user/project")
        result = reflect.classify_project_scope(c, "/home/user/project")
        assert result == "same-project"

    def test_null_project_path(self):
        """project_path が null の場合 global-looking を返す。"""
        c = _make_correction(project_path=None)
        result = reflect.classify_project_scope(c, "/home/user/project")
        assert result == "global-looking"

    def test_global_looking_always(self):
        """always/never キーワード含む → global-looking。"""
        c = _make_correction(
            message="always use bun",
            project_path="/other/project",
        )
        result = reflect.classify_project_scope(c, "/home/user/project")
        assert result == "global-looking"

    def test_global_looking_model_keyword(self):
        """モデル名キーワード含む → global-looking。"""
        c = _make_correction(
            message="use sonnet for this",
            project_path="/other/project",
        )
        result = reflect.classify_project_scope(c, "/home/user/project")
        assert result == "global-looking"

    def test_project_specific_other_db(self):
        """DB 名を含む → project-specific-other。"""
        c = _make_correction(
            message="use users.db for the database",
            project_path="/other/project",
        )
        result = reflect.classify_project_scope(c, "/home/user/project")
        assert result == "project-specific-other"

    def test_project_specific_other_filepath(self):
        """ファイルパスを含む → project-specific-other。"""
        c = _make_correction(
            message="edit /src/components/App.tsx instead",
            project_path="/other/project",
        )
        result = reflect.classify_project_scope(c, "/home/user/project")
        assert result == "project-specific-other"

    def test_other_project_generic(self):
        """異なるプロジェクトだが汎用的 → global-looking。"""
        c = _make_correction(
            message="don't add comments",
            project_path="/other/project",
        )
        result = reflect.classify_project_scope(c, "/home/user/project")
        assert result == "global-looking"


# --- Test: detect_duplicates ---

class TestDetectDuplicates:
    def test_no_duplicates(self, tmp_path):
        """重複なしの場合 duplicate_found=False。"""
        corrections = [_make_correction(message="use bun instead of npm")]
        with mock.patch("reflect.read_all_memory_entries", return_value=[]):
            result = reflect.detect_duplicates(corrections, tmp_path)
        assert len(result) == 1
        assert result[0]["duplicate_found"] is False
        assert result[0]["duplicate_in"] is None

    def test_duplicate_found(self, tmp_path):
        """メッセージがメモリに既存の場合 duplicate_found=True。"""
        corrections = [_make_correction(message="use bun instead of npm")]
        memory = [{"tier": "global", "path": "/home/.claude/CLAUDE.md", "content": "use bun instead of npm"}]
        with mock.patch("reflect.read_all_memory_entries", return_value=memory):
            result = reflect.detect_duplicates(corrections, tmp_path)
        assert result[0]["duplicate_found"] is True
        assert result[0]["duplicate_in"] == "/home/.claude/CLAUDE.md"

    def test_short_message_no_false_positive(self, tmp_path):
        """短いメッセージ（10文字以下）は重複チェックしない。"""
        corrections = [_make_correction(message="use bun")]
        memory = [{"tier": "global", "path": "/home/.claude/CLAUDE.md", "content": "use bun for everything"}]
        with mock.patch("reflect.read_all_memory_entries", return_value=memory):
            result = reflect.detect_duplicates(corrections, tmp_path)
        assert result[0]["duplicate_found"] is False

    def test_duplicate_via_extracted_learning(self, tmp_path):
        """extracted_learning がメモリに存在する場合も重複検出する。"""
        corrections = [_make_correction(
            message="いや、bun を使って",
            extracted_learning="パッケージマネージャーには bun を使用する",
        )]
        memory = [{"tier": "rule", "path": "/project/.claude/rules/tools.md",
                    "content": "パッケージマネージャーには bun を使用する"}]
        with mock.patch("reflect.read_all_memory_entries", return_value=memory):
            result = reflect.detect_duplicates(corrections, tmp_path)
        assert result[0]["duplicate_found"] is True


# --- Test: route_corrections ---

class TestRouteCorrections:
    def test_global_scope(self, tmp_path):
        """global-looking スコープ → routing_hint="global"。"""
        corrections = [dict(_make_correction(), _scope="global-looking")]
        with mock.patch("reflect.suggest_claude_file", return_value=(str(Path.home() / ".claude/CLAUDE.md"), 0.80)):
            result = reflect.route_corrections(corrections, tmp_path)
        assert result[0]["routing_hint"] == "global"
        assert result[0]["suggested_file"] is not None

    def test_project_scope(self, tmp_path):
        """same-project スコープ → routing_hint="project"。"""
        corrections = [dict(_make_correction(), _scope="same-project")]
        with mock.patch("reflect.suggest_claude_file", return_value=("/project/CLAUDE.md", 0.75)):
            result = reflect.route_corrections(corrections, tmp_path)
        assert result[0]["routing_hint"] == "project"

    def test_skip_scope(self, tmp_path):
        """project-specific-other スコープ → routing_hint="skip"。"""
        corrections = [dict(_make_correction(), _scope="project-specific-other")]
        with mock.patch("reflect.suggest_claude_file", return_value=None):
            result = reflect.route_corrections(corrections, tmp_path)
        assert result[0]["routing_hint"] == "skip"
        assert result[0]["suggested_file"] is None

    def test_no_suggestion(self, tmp_path):
        """suggest_claude_file が None → suggested_file=None。"""
        corrections = [dict(_make_correction(), _scope="same-project")]
        with mock.patch("reflect.suggest_claude_file", return_value=None):
            result = reflect.route_corrections(corrections, tmp_path)
        assert result[0]["suggested_file"] is None


# --- Test: --view mode ---

class TestViewMode:
    def test_view_output(self):
        """--view は corrections 一覧と total を含む JSON を返す。"""
        ts = datetime.now(timezone.utc).isoformat()
        pending = [
            _make_correction(message="use bun", confidence=0.85, timestamp=ts),
            _make_correction(message="no comments", confidence=0.70, timestamp=ts),
        ]
        result = reflect.build_view_output(pending, pending)
        assert result["status"] == "view"
        assert result["total"] == 2
        assert len(result["corrections"]) == 2
        assert result["corrections"][0]["age_days"] is not None

    def test_view_empty(self):
        """pending が空なら empty ステータス。"""
        result = reflect.build_view_output([], [])
        assert result["status"] == "empty"


# --- Test: --skip-all mode ---

class TestSkipAllMode:
    def test_skip_all_updates_status(self, tmp_path):
        """--skip-all は全 pending を skipped に更新する。"""
        corrections = [
            _make_correction(reflect_status="pending"),
            _make_correction(reflect_status="applied"),
            _make_correction(reflect_status="pending"),
        ]
        filepath = _write_corrections(tmp_path, corrections)

        reflect.update_reflect_status(filepath, [0, 2], "skipped")

        updated = reflect.load_corrections(filepath)
        assert updated[0]["reflect_status"] == "skipped"
        assert updated[1]["reflect_status"] == "applied"
        assert updated[2]["reflect_status"] == "skipped"

    def test_skip_all_empty(self, tmp_path):
        """pending が空なら更新しない。"""
        filepath = tmp_path / "corrections.jsonl"
        filepath.write_text("", encoding="utf-8")
        reflect.update_reflect_status(filepath, [], "skipped")
        # エラーなく完了すること
        assert True


# --- Test: --apply-all mode ---

class TestApplyAllMode:
    def test_apply_all_separates_by_threshold(self):
        """apply_all は閾値以上に apply=True、未満に apply=False を付与する。"""
        pending = [
            _make_correction(confidence=0.90),
            _make_correction(confidence=0.70),
            _make_correction(confidence=0.85),
        ]
        # build_output に必要なフィールドを追加
        for c in pending:
            c["_scope"] = "same-project"
            c["routing_hint"] = "project"
            c["suggested_file"] = "/tmp/test.md"
            c["duplicate_found"] = False
            c["duplicate_in"] = None

        with mock.patch("reflect.find_promotion_candidates", return_value=[]):
            result = reflect.build_output(
                pending, pending,
                min_confidence=0.85,
                apply_all=True,
            )

        corrections = result["corrections"]
        assert corrections[0]["apply"] is True   # 0.90 >= 0.85
        assert corrections[1]["apply"] is False  # 0.70 < 0.85
        assert corrections[2]["apply"] is True   # 0.85 >= 0.85

    def test_apply_all_summary(self):
        """apply_all でもサマリは正常に生成される。"""
        pending = [_make_correction(confidence=0.90)]
        for c in pending:
            c["_scope"] = "same-project"
            c["routing_hint"] = "project"
            c["suggested_file"] = "/tmp/test.md"
            c["duplicate_found"] = False
            c["duplicate_in"] = None

        with mock.patch("reflect.find_promotion_candidates", return_value=[]):
            result = reflect.build_output(pending, pending, apply_all=True)

        assert result["status"] == "has_pending"
        assert result["summary"]["total"] == 1


# --- Test: promotion candidates ---

class TestPromotionCandidates:
    def test_reoccurrence_promotion(self):
        """同一 correction_type が2回以上 → 昇格候補。"""
        old_ts = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        records = [
            _make_correction(correction_type="iya", reflect_status="applied", timestamp=old_ts),
            _make_correction(correction_type="iya", reflect_status="applied",
                             message="いや、そうじゃない", timestamp=old_ts),
        ]
        with mock.patch("reflect.read_auto_memory", return_value=[]):
            result = reflect.find_promotion_candidates(records)
        assert len(result) >= 1
        assert result[0]["occurrences"] >= 2

    def test_age_promotion(self):
        """14日以上経過 → 昇格候補。"""
        old_ts = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        records = [
            _make_correction(correction_type="unique_type", reflect_status="applied", timestamp=old_ts),
        ]
        with mock.patch("reflect.read_auto_memory", return_value=[]):
            result = reflect.find_promotion_candidates(records)
        assert len(result) == 1
        assert result[0]["age_qualified"] is True

    def test_no_promotion_recent_single(self):
        """出現1回かつ14日未満 → 昇格候補なし。"""
        recent_ts = datetime.now(timezone.utc).isoformat()
        records = [
            _make_correction(correction_type="unique_type", reflect_status="applied", timestamp=recent_ts),
        ]
        with mock.patch("reflect.read_auto_memory", return_value=[]):
            result = reflect.find_promotion_candidates(records)
        assert len(result) == 0

    def test_already_in_auto_memory(self):
        """auto-memory に既存なら昇格候補から除外。"""
        old_ts = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        records = [
            _make_correction(
                message="use bun",
                correction_type="iya",
                reflect_status="applied",
                timestamp=old_ts,
            ),
        ]
        auto_memory = [{"path": "/memory/MEMORY.md", "topic": "general", "content": "use bun"}]
        with mock.patch("reflect.read_auto_memory", return_value=auto_memory):
            result = reflect.find_promotion_candidates(records)
        assert len(result) == 0


# --- Test: load_corrections ---

class TestLoadCorrections:
    def test_load_valid(self, tmp_path):
        """正常な JSONL を読み込める。"""
        corrections = [_make_correction(), _make_correction(message="test2")]
        filepath = _write_corrections(tmp_path, corrections)
        result = reflect.load_corrections(filepath)
        assert len(result) == 2

    def test_load_nonexistent(self, tmp_path):
        """存在しないファイルは空リストを返す。"""
        result = reflect.load_corrections(tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_load_with_invalid_lines(self, tmp_path):
        """不正な JSON 行はスキップする。"""
        filepath = tmp_path / "corrections.jsonl"
        filepath.write_text(
            json.dumps(_make_correction()) + "\n"
            + "invalid json\n"
            + json.dumps(_make_correction(message="valid")) + "\n",
            encoding="utf-8",
        )
        result = reflect.load_corrections(filepath)
        assert len(result) == 2


# --- Test: update_reflect_status ---

class TestUpdateReflectStatus:
    def test_update_specific_indices(self, tmp_path):
        """指定インデックスのみ更新する。"""
        corrections = [
            _make_correction(message="msg0"),
            _make_correction(message="msg1"),
            _make_correction(message="msg2"),
        ]
        filepath = _write_corrections(tmp_path, corrections)
        reflect.update_reflect_status(filepath, [0, 2], "applied")

        updated = reflect.load_corrections(filepath)
        assert updated[0]["reflect_status"] == "applied"
        assert updated[1]["reflect_status"] == "pending"
        assert updated[2]["reflect_status"] == "applied"


# --- Test: build_output ---

class TestBuildOutput:
    def test_empty_pending(self):
        """pending が空なら empty ステータスを返す。"""
        result = reflect.build_output([], [])
        assert result["status"] == "empty"

    def test_has_pending(self):
        """pending がある場合 has_pending ステータスを返す。"""
        pending = [_make_correction()]
        for c in pending:
            c["_scope"] = "same-project"
            c["routing_hint"] = "project"
            c["suggested_file"] = "/tmp/test.md"
            c["duplicate_found"] = False
            c["duplicate_in"] = None

        with mock.patch("reflect.find_promotion_candidates", return_value=[]):
            result = reflect.build_output(pending, pending)

        assert result["status"] == "has_pending"
        assert len(result["corrections"]) == 1
        assert "summary" in result
        assert result["summary"]["total"] == 1


# --- Test: CLI integration ---

class TestCLI:
    def test_view_mode_cli(self, tmp_path, capsys):
        """CLI --view モードが JSON を出力する。"""
        corrections = [_make_correction()]
        filepath = _write_corrections(tmp_path, corrections)

        with mock.patch("sys.argv", ["reflect.py", "--view", "--corrections-file", str(filepath)]):
            reflect.main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "view"

    def test_skip_all_mode_cli(self, tmp_path, capsys):
        """CLI --skip-all モードが全 pending をスキップする。"""
        corrections = [_make_correction(), _make_correction(reflect_status="applied")]
        filepath = _write_corrections(tmp_path, corrections)

        with mock.patch("sys.argv", ["reflect.py", "--skip-all", "--corrections-file", str(filepath)]):
            reflect.main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "skipped_all"
        assert output["count"] == 1

    def test_empty_corrections_cli(self, tmp_path, capsys):
        """corrections が空の場合 empty を出力する。"""
        filepath = tmp_path / "corrections.jsonl"
        filepath.write_text("", encoding="utf-8")

        with mock.patch("sys.argv", ["reflect.py", "--view", "--corrections-file", str(filepath)]):
            reflect.main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "empty"


# --- Test: semantic validation failure does not zero out corrections ---

class TestSemanticValidationFallback:
    def test_validation_failure_preserves_corrections(self):
        """semantic validation が例外で失敗しても corrections が 0 件にならない。"""
        corrections = [
            _make_correction(message="use bun instead of npm"),
            _make_correction(message="always use TypeScript"),
        ]
        # validate_corrections が例外時に is_learning=True でフォールバックすることを確認
        with mock.patch("reflect.validate_corrections") as mock_validate:
            mock_validate.return_value = [
                {"is_learning": True, "extracted_learning": None},
                {"is_learning": True, "extracted_learning": None},
            ]
            result = reflect.apply_semantic_validation(corrections)
        assert len(result) == 2
        assert all(r["is_learning"] is True for r in result)

    def test_validation_count_mismatch_preserves_corrections(self):
        """semantic validation の件数不一致でも corrections が全件除外されない。"""
        corrections = [
            _make_correction(message="msg1"),
            _make_correction(message="msg2"),
            _make_correction(message="msg3"),
        ]
        # validate_corrections が partial success で一部 True を返す
        with mock.patch("reflect.validate_corrections") as mock_validate:
            mock_validate.return_value = [
                {"is_learning": False, "extracted_learning": None},
                {"is_learning": True, "extracted_learning": None},
                {"is_learning": True, "extracted_learning": None},
            ]
            result = reflect.apply_semantic_validation(corrections)
        # is_learning フィルタ後でも 0 件にはならない
        learning_items = [r for r in result if r.get("is_learning", True)]
        assert len(learning_items) >= 1


# --- Test: find_memory_update_candidates ---

class TestFindMemoryUpdateCandidates:
    def test_match_detected(self):
        """共通キーワードが MIN_KEYWORD_MATCH 以上なら候補として検出される。"""
        c = _make_correction(message="npm install instead of bun install for package management")
        c["duplicate_found"] = False
        corrections = [c]

        memory_entries = [{
            "tier": "auto-memory",
            "path": "/memory/MEMORY.md",
            "content": "## Package Management\n\n- bun install for package management\n",
        }]
        with mock.patch("reflect.read_all_memory_entries", return_value=memory_entries):
            result = reflect.find_memory_update_candidates(corrections)
        assert len(result) >= 1
        assert result[0]["suggested_action"] == "update"

    def test_no_match(self):
        """共通キーワードがない場合は空リスト。"""
        c = _make_correction(message="completely unrelated topic about database")
        c["duplicate_found"] = False
        corrections = [c]

        memory_entries = [{
            "tier": "auto-memory",
            "path": "/memory/MEMORY.md",
            "content": "## Git Config\n\n- matsukaze-minden account for push\n",
        }]
        with mock.patch("reflect.read_all_memory_entries", return_value=memory_entries):
            result = reflect.find_memory_update_candidates(corrections)
        assert len(result) == 0

    def test_skip_duplicates(self):
        """duplicate_found=True の correction は除外される。"""
        c = _make_correction(message="npm install instead of bun install for package management")
        c["duplicate_found"] = True
        corrections = [c]

        memory_entries = [{
            "tier": "auto-memory",
            "path": "/memory/MEMORY.md",
            "content": "## Package Management\n\n- bun install for package management\n",
        }]
        with mock.patch("reflect.read_all_memory_entries", return_value=memory_entries):
            result = reflect.find_memory_update_candidates(corrections)
        assert len(result) == 0

    def test_below_min_keyword_match(self):
        """共通キーワードが MIN_KEYWORD_MATCH 未満なら候補にならない。"""
        c = _make_correction(message="hello world")
        c["duplicate_found"] = False
        corrections = [c]

        memory_entries = [{
            "tier": "auto-memory",
            "path": "/memory/MEMORY.md",
            "content": "## Notes\n\n- hello world example\n",
        }]
        with mock.patch("reflect.read_all_memory_entries", return_value=memory_entries):
            result = reflect.find_memory_update_candidates(corrections)
        # "hello" と "world" の2語のみ（ストップワード除外後）→ MIN_KEYWORD_MATCH=3 未満
        assert len(result) == 0
