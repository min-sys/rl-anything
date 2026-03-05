"""migrate_project_field.py のユニットテスト。"""
import json
import sys
from pathlib import Path

import pytest

# プラグインルートを sys.path に追加
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from migrate_project_field import (
    build_fs_recovery,
    build_project_mapping,
    build_session_mapping,
    migrate_usage,
)


def _write_jsonl(path: Path, records: list) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- build_session_mapping ---


class TestBuildSessionMapping:
    def test_normal(self, tmp_path):
        sessions_file = tmp_path / "sessions.jsonl"
        _write_jsonl(sessions_file, [
            {"session_id": "s1", "project_name": "atlas"},
            {"session_id": "s2", "project_name": "bolt"},
        ])
        result = build_session_mapping(sessions_file)
        assert result == {"s1": "atlas", "s2": "bolt"}

    def test_last_wins_dedup(self, tmp_path):
        sessions_file = tmp_path / "sessions.jsonl"
        _write_jsonl(sessions_file, [
            {"session_id": "s1", "project_name": "alpha"},
            {"session_id": "s1", "project_name": "beta"},
        ])
        result = build_session_mapping(sessions_file)
        assert result == {"s1": "beta"}

    def test_null_project_name_skipped(self, tmp_path):
        sessions_file = tmp_path / "sessions.jsonl"
        _write_jsonl(sessions_file, [
            {"session_id": "s1", "project_name": None},
            {"session_id": "s2", "project_name": "atlas"},
        ])
        result = build_session_mapping(sessions_file)
        assert "s1" not in result
        assert result["s2"] == "atlas"

    def test_empty_file(self, tmp_path):
        sessions_file = tmp_path / "sessions.jsonl"
        sessions_file.write_text("", encoding="utf-8")
        result = build_session_mapping(sessions_file)
        assert result == {}

    def test_nonexistent_file(self, tmp_path):
        result = build_session_mapping(tmp_path / "nonexistent.jsonl")
        assert result == {}


# --- build_fs_recovery ---


class TestBuildFsRecovery:
    def test_consensus_success(self, tmp_path):
        """同ディレクトリ内の他セッションから consensus で補完される。"""
        tier1 = {"s1": "bar", "s2": "bar"}

        # ディレクトリ構造: projects/-Users-foo-bar/ に s1, s2, s3 のファイル
        proj_dir = tmp_path / "-Users-foo-bar"
        proj_dir.mkdir()
        (proj_dir / "s1.jsonl").write_text("{}", encoding="utf-8")
        (proj_dir / "s2.jsonl").write_text("{}", encoding="utf-8")
        (proj_dir / "s3.jsonl").write_text("{}", encoding="utf-8")

        result = build_fs_recovery(tier1, tmp_path)
        assert result == {"s3": "bar"}

    def test_no_consensus(self, tmp_path):
        """全セッションが未マッピングの場合は補完なし。"""
        tier1: dict = {}

        proj_dir = tmp_path / "-Users-foo-baz"
        proj_dir.mkdir()
        (proj_dir / "s1.jsonl").write_text("{}", encoding="utf-8")
        (proj_dir / "s2.jsonl").write_text("{}", encoding="utf-8")

        result = build_fs_recovery(tier1, tmp_path)
        assert result == {}

    def test_nonexistent_projects_dir(self, tmp_path):
        result = build_fs_recovery({}, tmp_path / "nonexistent")
        assert result == {}

    def test_multiple_projects_consensus(self, tmp_path):
        """多数決で最頻値が採用される。"""
        tier1 = {"s1": "foo", "s2": "foo", "s3": "bar"}

        proj_dir = tmp_path / "proj1"
        proj_dir.mkdir()
        for sid in ["s1", "s2", "s3", "s4"]:
            (proj_dir / f"{sid}.jsonl").write_text("{}", encoding="utf-8")

        result = build_fs_recovery(tier1, tmp_path)
        assert result == {"s4": "foo"}  # foo が多数


# --- build_project_mapping ---


class TestBuildProjectMapping:
    def test_tier1_plus_tier2(self, tmp_path):
        sessions_file = tmp_path / "sessions.jsonl"
        _write_jsonl(sessions_file, [
            {"session_id": "s1", "project_name": "atlas"},
        ])

        proj_dir = tmp_path / "projects" / "-proj"
        proj_dir.mkdir(parents=True)
        (proj_dir / "s1.jsonl").write_text("{}", encoding="utf-8")
        (proj_dir / "s2.jsonl").write_text("{}", encoding="utf-8")

        result = build_project_mapping(sessions_file, tmp_path / "projects")
        assert result["s1"] == "atlas"  # Tier 1
        assert result["s2"] == "atlas"  # Tier 2 consensus

    def test_tier2_does_not_overwrite_tier1(self, tmp_path):
        sessions_file = tmp_path / "sessions.jsonl"
        _write_jsonl(sessions_file, [
            {"session_id": "s1", "project_name": "original"},
        ])

        # Tier 2 が異なる値を返しても Tier 1 が優先
        result = build_project_mapping(sessions_file, tmp_path / "nonexistent")
        assert result["s1"] == "original"


# --- migrate_usage ---


class TestMigrateUsage:
    def test_mapped(self, tmp_path):
        usage_file = tmp_path / "usage.jsonl"
        _write_jsonl(usage_file, [
            {"session_id": "s1", "skill_name": "foo"},
        ])
        mapping = {"s1": "atlas"}
        result = migrate_usage(mapping, usage_file)

        assert result["total"] == 1
        assert result["mapped"] == 1
        assert result["unmapped"] == 0
        assert result["already_has_project"] == 0

        written = [json.loads(l) for l in usage_file.read_text().splitlines() if l.strip()]
        assert written[0]["project"] == "atlas"

    def test_unmapped(self, tmp_path):
        usage_file = tmp_path / "usage.jsonl"
        _write_jsonl(usage_file, [
            {"session_id": "s999", "skill_name": "foo"},
        ])
        result = migrate_usage({}, usage_file)
        assert result["unmapped"] == 1

        written = [json.loads(l) for l in usage_file.read_text().splitlines() if l.strip()]
        assert written[0]["project"] is None

    def test_already_has_project(self, tmp_path):
        usage_file = tmp_path / "usage.jsonl"
        _write_jsonl(usage_file, [
            {"session_id": "s1", "skill_name": "foo", "project": "existing"},
        ])
        mapping = {"s1": "different"}
        result = migrate_usage(mapping, usage_file)

        assert result["already_has_project"] == 1
        assert result["mapped"] == 0

        written = [json.loads(l) for l in usage_file.read_text().splitlines() if l.strip()]
        assert written[0]["project"] == "existing"  # 上書きされない

    def test_no_session_id(self, tmp_path):
        usage_file = tmp_path / "usage.jsonl"
        _write_jsonl(usage_file, [
            {"skill_name": "foo"},  # session_id なし
        ])
        result = migrate_usage({"s1": "atlas"}, usage_file)
        assert result["unmapped"] == 1

        written = [json.loads(l) for l in usage_file.read_text().splitlines() if l.strip()]
        assert written[0]["project"] is None

    def test_idempotent(self, tmp_path):
        """2回実行しても結果が変わらない。"""
        usage_file = tmp_path / "usage.jsonl"
        _write_jsonl(usage_file, [
            {"session_id": "s1", "skill_name": "foo"},
        ])
        mapping = {"s1": "atlas"}

        migrate_usage(mapping, usage_file)
        result2 = migrate_usage(mapping, usage_file)

        assert result2["already_has_project"] == 1
        assert result2["mapped"] == 0

    def test_dry_run(self, tmp_path):
        usage_file = tmp_path / "usage.jsonl"
        original_content = json.dumps({"session_id": "s1", "skill_name": "foo"}) + "\n"
        usage_file.write_text(original_content, encoding="utf-8")

        result = migrate_usage({"s1": "atlas"}, usage_file, dry_run=True)

        assert result["mapped"] == 1
        # ファイルが変更されていないこと
        assert usage_file.read_text(encoding="utf-8") == original_content


# --- backup ---


class TestBackup:
    def test_backup_created(self, tmp_path):
        """shutil.copy2 でバックアップが作成される。"""
        import shutil

        usage_file = tmp_path / "usage.jsonl"
        content = json.dumps({"session_id": "s1"}) + "\n"
        usage_file.write_text(content, encoding="utf-8")

        backup_path = usage_file.with_suffix(".jsonl.bak")
        shutil.copy2(str(usage_file), str(backup_path))

        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == content
