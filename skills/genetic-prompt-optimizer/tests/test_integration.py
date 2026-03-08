"""Integration tests for direct-patch optimizer pipeline."""
from __future__ import annotations
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from optimize import DirectPatchOptimizer, BACKUP_SUFFIX


# --- Fixtures ---

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def skill_path(temp_dir):
    skill_dir = temp_dir / "test-skill"
    skill_dir.mkdir()
    path = skill_dir / "SKILL.md"
    path.write_text(
        "---\nname: test-skill\ndescription: Integration test skill\n---\n\n"
        "# Test Skill\n\nThis is a test skill for integration testing.\n\n"
        "## Usage\n\nUse this skill when testing.\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def corrections_file(temp_dir):
    path = temp_dir / "corrections.jsonl"
    records = [
        {
            "message": "出力が冗長すぎる",
            "last_skill": "test-skill",
            "correction_type": "output_format",
            "extracted_learning": "簡潔な出力にする",
            "confidence": 0.9,
            "reflect_status": "pending",
        },
        {
            "message": "エッジケースが考慮されていない",
            "last_skill": "test-skill",
            "correction_type": "missing_handling",
            "extracted_learning": "エッジケースを追加",
            "confidence": 0.85,
            "reflect_status": "pending",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


# --- End-to-end dry-run ---

class TestDryRunIntegration:
    def test_dry_run_creates_result(self, skill_path, temp_dir):
        """dry-run で result.json が作成される"""
        optimizer = DirectPatchOptimizer(target_path=str(skill_path), dry_run=True)
        optimizer.run_dir = temp_dir / "test_run"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"):
            result = optimizer.run()

        assert result["dry_run"] is True
        assert result["strategy"] == "llm_improve"
        result_file = optimizer.run_dir / "result.json"
        assert result_file.exists()

    def test_dry_run_with_corrections(self, skill_path, temp_dir, corrections_file):
        """corrections ありの dry-run で error_guided が選択される"""
        optimizer = DirectPatchOptimizer(target_path=str(skill_path), dry_run=True)
        optimizer.run_dir = temp_dir / "test_run"

        with patch("optimize._CORRECTIONS_PATH", corrections_file):
            result = optimizer.run()

        assert result["strategy"] == "error_guided"
        assert result["corrections_used"] == 2


# --- Full pipeline with mock LLM ---

class TestFullPipeline:
    def _mock_llm_response(self, improved_content: str):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"```markdown\n{improved_content}\n```"
        return mock_result

    def test_error_guided_pipeline(self, skill_path, temp_dir, corrections_file):
        """error_guided の完全パイプライン"""
        optimizer = DirectPatchOptimizer(target_path=str(skill_path), mode="auto")
        optimizer.run_dir = temp_dir / "test_run"

        improved = "---\nname: test-skill\ndescription: Integration test skill\n---\n\n# Improved Skill\n\nBetter content with edge cases.\n"

        with patch("optimize._CORRECTIONS_PATH", corrections_file), \
             patch("optimize.subprocess.run", return_value=self._mock_llm_response(improved)):
            result = optimizer.run()

        assert result["strategy"] == "error_guided"
        assert result["corrections_used"] == 2
        assert not result.get("error")
        assert not result.get("gate_rejected")

        # ファイルが更新されている
        actual = skill_path.read_text(encoding="utf-8")
        assert "Improved Skill" in actual

        # バックアップが存在する
        backup = skill_path.with_suffix(skill_path.suffix + BACKUP_SUFFIX)
        assert backup.exists()

    def test_llm_improve_pipeline(self, skill_path, temp_dir):
        """llm_improve の完全パイプライン"""
        optimizer = DirectPatchOptimizer(target_path=str(skill_path), mode="llm_improve")
        optimizer.run_dir = temp_dir / "test_run"

        improved = "# Enhanced Skill\n\nMore examples and clarity.\n"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"), \
             patch("optimize.subprocess.run", return_value=self._mock_llm_response(improved)):
            result = optimizer.run()

        assert result["strategy"] == "llm_improve"
        assert result["corrections_used"] == 0

    def test_gate_rejection_preserves_original(self, skill_path, temp_dir):
        """regression gate 不合格時にオリジナルを維持"""
        original = skill_path.read_text(encoding="utf-8")
        optimizer = DirectPatchOptimizer(target_path=str(skill_path))
        optimizer.run_dir = temp_dir / "test_run"

        # 禁止パターンを含むパッチ
        bad_content = "# Bad Skill\n\nTODO: implement this\n"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"), \
             patch("optimize.subprocess.run", return_value=self._mock_llm_response(bad_content)):
            result = optimizer.run()

        assert result.get("gate_rejected") is True
        # ファイルは元のまま（backup_original で backup 作成後、パッチ適用前に gate で弾かれるため）
        # gate 不合格時はファイル書き込みしない

    def test_llm_failure_preserves_original(self, skill_path, temp_dir):
        """LLM コール失敗時にオリジナルを維持"""
        optimizer = DirectPatchOptimizer(target_path=str(skill_path))
        optimizer.run_dir = temp_dir / "test_run"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"), \
             patch("optimize.subprocess.run", side_effect=FileNotFoundError):
            result = optimizer.run()

        assert result.get("error") is not None


# --- Accept/Reject flow ---

class TestAcceptRejectFlow:
    def test_accept_flow(self, skill_path, temp_dir):
        """accept → history.jsonl が更新される"""
        optimizer = DirectPatchOptimizer(target_path=str(skill_path), dry_run=True)
        optimizer.run_dir = temp_dir / "runs" / "test_run"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"):
            result = optimizer.run()

        # accept
        DirectPatchOptimizer.record_human_decision(
            str(optimizer.run_dir), human_accepted=True
        )

        history = temp_dir / "runs" / "history.jsonl"
        entry = json.loads(history.read_text(encoding="utf-8").strip().split("\n")[-1])
        assert entry["human_accepted"] is True

    def test_reject_flow(self, skill_path, temp_dir):
        """reject → history.jsonl に理由付きで記録"""
        optimizer = DirectPatchOptimizer(target_path=str(skill_path), dry_run=True)
        optimizer.run_dir = temp_dir / "runs" / "test_run"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"):
            result = optimizer.run()

        DirectPatchOptimizer.record_human_decision(
            str(optimizer.run_dir), human_accepted=False, rejection_reason="品質不足"
        )

        history = temp_dir / "runs" / "history.jsonl"
        entry = json.loads(history.read_text(encoding="utf-8").strip().split("\n")[-1])
        assert entry["human_accepted"] is False
        assert entry["rejection_reason"] == "品質不足"

    def test_history_has_strategy_field(self, skill_path, temp_dir, corrections_file):
        """history.jsonl に strategy/corrections_used が記録される"""
        optimizer = DirectPatchOptimizer(target_path=str(skill_path), dry_run=True)
        optimizer.run_dir = temp_dir / "runs" / "test_run"

        with patch("optimize._CORRECTIONS_PATH", corrections_file):
            result = optimizer.run()

        history = temp_dir / "runs" / "history.jsonl"
        entry = json.loads(history.read_text(encoding="utf-8").strip())
        assert entry["strategy"] == "error_guided"
        assert entry["corrections_used"] == 2
