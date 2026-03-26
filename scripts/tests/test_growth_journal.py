#!/usr/bin/env python3
"""growth_journal のテスト — 結晶化イベント記録・照会 + backfill。"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from growth_journal import (
    JOURNAL_FILENAME,
    emit_crystallization,
    query_crystallizations,
    count_crystallized_rules,
    backfill_from_git_log,
)


# ── emit_crystallization ────────────────────────────────────────


class TestEmitCrystallization:
    def test_emit_writes_jsonl(self, tmp_path):
        """正常に JSONL 1 行を追記。"""
        with mock.patch("growth_journal._data_dir", return_value=tmp_path):
            emit_crystallization(
                project="test-proj",
                targets=[".claude/rules/verify.md"],
                evidence_count=3,
                phase="structured_nurturing",
            )

        journal = tmp_path / JOURNAL_FILENAME
        assert journal.exists()
        lines = journal.read_text().strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["type"] == "crystallization"
        assert record["project"] == "test-proj"
        assert record["targets"] == [".claude/rules/verify.md"]
        assert record["evidence_count"] == 3
        assert record["phase"] == "structured_nurturing"
        assert "ts" in record

    def test_emit_appends(self, tmp_path):
        """複数回呼ぶと追記される。"""
        with mock.patch("growth_journal._data_dir", return_value=tmp_path):
            emit_crystallization("p", ["a.md"], 1, "bootstrap")
            emit_crystallization("p", ["b.md"], 2, "bootstrap")

        journal = tmp_path / JOURNAL_FILENAME
        lines = journal.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_emit_creates_directory(self, tmp_path):
        """ディレクトリ未存在でも作成。"""
        nested = tmp_path / "deep" / "dir"
        with mock.patch("growth_journal._data_dir", return_value=nested):
            emit_crystallization("p", ["a.md"], 1, "bootstrap")
        assert (nested / JOURNAL_FILENAME).exists()


# ── query_crystallizations ──────────────────────────────────────


class TestQueryCrystallizations:
    def _write_events(self, tmp_path, events):
        journal = tmp_path / JOURNAL_FILENAME
        journal.parent.mkdir(parents=True, exist_ok=True)
        with open(journal, "w") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")

    def test_query_all(self, tmp_path):
        """全件取得。"""
        events = [
            {"type": "crystallization", "project": "p1", "ts": "2026-03-20T00:00:00Z", "targets": ["a.md"]},
            {"type": "crystallization", "project": "p2", "ts": "2026-03-21T00:00:00Z", "targets": ["b.md"]},
        ]
        self._write_events(tmp_path, events)
        with mock.patch("growth_journal._data_dir", return_value=tmp_path):
            result = query_crystallizations()
        assert len(result) == 2

    def test_query_by_project(self, tmp_path):
        """プロジェクトフィルタ。"""
        events = [
            {"type": "crystallization", "project": "p1", "ts": "2026-03-20T00:00:00Z", "targets": ["a.md"]},
            {"type": "crystallization", "project": "p2", "ts": "2026-03-21T00:00:00Z", "targets": ["b.md"]},
        ]
        self._write_events(tmp_path, events)
        with mock.patch("growth_journal._data_dir", return_value=tmp_path):
            result = query_crystallizations(project="p1")
        assert len(result) == 1
        assert result[0]["project"] == "p1"

    def test_query_by_since(self, tmp_path):
        """時間範囲フィルタ。"""
        events = [
            {"type": "crystallization", "project": "p1", "ts": "2026-03-10T00:00:00Z", "targets": ["a.md"]},
            {"type": "crystallization", "project": "p1", "ts": "2026-03-25T00:00:00Z", "targets": ["b.md"]},
        ]
        self._write_events(tmp_path, events)
        with mock.patch("growth_journal._data_dir", return_value=tmp_path):
            result = query_crystallizations(since="2026-03-20T00:00:00Z")
        assert len(result) == 1

    def test_query_missing_file(self, tmp_path):
        """ファイル未存在 → 空リスト。"""
        with mock.patch("growth_journal._data_dir", return_value=tmp_path):
            result = query_crystallizations()
        assert result == []


# ── count_crystallized_rules ────────────────────────────────────


class TestCountCrystallizedRules:
    def test_count_distinct_targets(self, tmp_path):
        """distinct target パスの数。"""
        events = [
            {"type": "crystallization", "project": "p1", "ts": "2026-03-20T00:00:00Z", "targets": ["a.md", "b.md"]},
            {"type": "crystallization", "project": "p1", "ts": "2026-03-21T00:00:00Z", "targets": ["b.md", "c.md"]},
        ]
        journal = tmp_path / JOURNAL_FILENAME
        with open(journal, "w") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")
        with mock.patch("growth_journal._data_dir", return_value=tmp_path):
            count = count_crystallized_rules(project="p1")
        assert count == 3  # a.md, b.md, c.md


# ── backfill_from_git_log ───────────────────────────────────────


class TestBackfillFromGitLog:
    def test_backfill_parses_git_output(self, tmp_path):
        """git log 出力をパースして結晶化イベントを生成。"""
        git_output = (
            "abc1234|2026-03-10T10:00:00+00:00|feat(evolve): rule 生成\n"
            "def5678|2026-03-15T12:00:00+00:00|fix: typo修正\n"
            "ghi9012|2026-03-20T14:00:00+00:00|refactor(reflect): rule 更新\n"
        )
        with mock.patch("growth_journal._data_dir", return_value=tmp_path):
            with mock.patch("growth_journal._run_git_log", return_value=git_output):
                count = backfill_from_git_log("/fake/project")

        # evolve と reflect のコミットのみ (2件)、typo修正は除外
        assert count == 2
        journal = tmp_path / JOURNAL_FILENAME
        lines = journal.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_backfill_deduplicates(self, tmp_path):
        """既存イベントとの重複排除。"""
        # 既存イベントを書き込み
        existing = {"type": "crystallization", "ts": "2026-03-10T10:00:00+00:00", "source": "backfill", "commit": "abc1234", "project": "proj", "targets": []}
        journal = tmp_path / JOURNAL_FILENAME
        journal.write_text(json.dumps(existing) + "\n")

        git_output = "abc1234|2026-03-10T10:00:00+00:00|feat(evolve): rule 生成\n"
        with mock.patch("growth_journal._data_dir", return_value=tmp_path):
            with mock.patch("growth_journal._run_git_log", return_value=git_output):
                count = backfill_from_git_log("/fake/project")

        assert count == 0  # 重複のため追加なし
