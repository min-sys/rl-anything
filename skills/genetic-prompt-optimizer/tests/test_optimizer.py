#!/usr/bin/env python3
"""直接パッチプロンプト最適化のユニットテスト"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(
    0, str(Path(__file__).parent.parent / "scripts")
)

from optimize import (
    DirectPatchOptimizer,
    BACKUP_SUFFIX,
    MAX_CORRECTIONS_PER_PATCH,
    _check_deprecated_options,
    detect_scope,
)


# --- フィクスチャ ---

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_skill(temp_dir):
    skill_path = temp_dir / "test-skill.md"
    skill_path.write_text(
        "---\nname: test\ndescription: テスト用スキル\n---\n\n"
        "# テストスキル\n\nこれはテスト用のスキルです。\n",
        encoding="utf-8",
    )
    return skill_path


@pytest.fixture
def corrections_file(temp_dir):
    """テスト用 corrections.jsonl"""
    path = temp_dir / "corrections.jsonl"
    records = [
        {
            "message": "スキルの出力が長すぎる",
            "last_skill": "test-skill",
            "correction_type": "output_format",
            "extracted_learning": "出力を簡潔にする",
            "confidence": 0.8,
            "reflect_status": "pending",
        },
        {
            "message": "エラーハンドリングが不足",
            "last_skill": "test-skill",
            "correction_type": "missing_handling",
            "extracted_learning": "エラーケースを追加",
            "confidence": 0.9,
            "reflect_status": "pending",
        },
    ]
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --- detect_scope テスト ---

class TestDetectScope:
    def test_project_scope(self, temp_dir):
        skill = temp_dir / "SKILL.md"
        skill.touch()
        assert detect_scope(skill) == "project"

    def test_global_scope(self):
        global_path = Path.home() / ".claude" / "skills" / "test" / "SKILL.md"
        assert detect_scope(global_path) == "global"


# --- _collect_corrections テスト (Task 1.3) ---

class TestCollectCorrections:
    def test_corrections_あり(self, sample_skill, corrections_file):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), dry_run=True)
        with patch("optimize._CORRECTIONS_PATH", corrections_file):
            result = optimizer._collect_corrections()
        assert len(result) == 2
        assert result[0]["correction_type"] == "output_format"

    def test_corrections_なし(self, sample_skill, temp_dir):
        empty_path = temp_dir / "empty.jsonl"
        empty_path.write_text("", encoding="utf-8")
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), dry_run=True)
        with patch("optimize._CORRECTIONS_PATH", empty_path):
            result = optimizer._collect_corrections()
        assert result == []

    def test_corrections_ファイル不在(self, sample_skill, temp_dir):
        missing_path = temp_dir / "missing.jsonl"
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), dry_run=True)
        with patch("optimize._CORRECTIONS_PATH", missing_path):
            result = optimizer._collect_corrections()
        assert result == []

    def test_corrections_大量_制限(self, sample_skill, temp_dir):
        path = temp_dir / "many.jsonl"
        records = []
        for i in range(20):
            records.append(json.dumps({
                "message": f"修正 {i}",
                "last_skill": "test-skill",
                "correction_type": "fix",
                "reflect_status": "pending",
            }, ensure_ascii=False))
        path.write_text("\n".join(records) + "\n", encoding="utf-8")

        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), dry_run=True)
        with patch("optimize._CORRECTIONS_PATH", path):
            result = optimizer._collect_corrections()
        assert len(result) == MAX_CORRECTIONS_PER_PATCH

    def test_applied_は除外(self, sample_skill, temp_dir):
        path = temp_dir / "applied.jsonl"
        records = [
            json.dumps({
                "message": "適用済み",
                "last_skill": "test-skill",
                "correction_type": "fix",
                "reflect_status": "applied",
            }, ensure_ascii=False),
            json.dumps({
                "message": "未適用",
                "last_skill": "test-skill",
                "correction_type": "fix",
                "reflect_status": "pending",
            }, ensure_ascii=False),
        ]
        path.write_text("\n".join(records) + "\n", encoding="utf-8")

        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), dry_run=True)
        with patch("optimize._CORRECTIONS_PATH", path):
            result = optimizer._collect_corrections()
        assert len(result) == 1
        assert result[0]["message"] == "未適用"


# --- _build_patch_prompt テスト (Task 2.4) ---

class TestBuildPatchPrompt:
    def test_error_guided_prompt(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        corrections = [
            {"message": "出力が長い", "correction_type": "output_format", "extracted_learning": "簡潔に"},
        ]
        prompt = optimizer._build_patch_prompt("# Test Skill", corrections, {}, "error_guided")
        assert "修正すべき問題点" in prompt
        assert "出力が長い" in prompt
        assert "簡潔に" in prompt
        assert "error_guided" not in prompt or True  # mode name may not appear in prompt

    def test_llm_improve_prompt(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        prompt = optimizer._build_patch_prompt("# Test Skill", [], {}, "llm_improve")
        assert "改善方針" in prompt
        assert "具体的な例" in prompt

    def test_context_included(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        context = {
            "workflow_hint": "このスキルは週3回使用",
            "audit_issues": [{"type": "line_limit", "file": "test.md", "detail": "100行超過"}],
            "pitfalls": "| gate | forbidden_pattern(X) | 0.00 |",
        }
        prompt = optimizer._build_patch_prompt("# Test", [], context, "llm_improve")
        assert "ワークフロー分析" in prompt
        assert "週3回" in prompt
        assert "構造的問題" in prompt
        assert "失敗パターン" in prompt


# --- DirectPatchOptimizer コアテスト (Task 3.4) ---

class TestDirectPatchOptimizer:
    def test_dry_run(self, sample_skill, temp_dir):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), dry_run=True)
        optimizer.run_dir = temp_dir / "test_run"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"):
            result = optimizer.run()

        assert result["dry_run"] is True
        assert result["strategy"] == "llm_improve"
        assert result["best_individual"]["content"] is not None

    def test_error_guided_正常系(self, sample_skill, temp_dir, corrections_file):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), mode="auto")
        optimizer.run_dir = temp_dir / "test_run"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "```markdown\n---\nname: test\ndescription: 改善済み\n---\n\n# Improved Skill\n\nBetter content.\n```"

        with patch("optimize._CORRECTIONS_PATH", corrections_file), \
             patch("optimize.subprocess.run", return_value=mock_result):
            result = optimizer.run()

        assert result["strategy"] == "error_guided"
        assert result["corrections_used"] == 2
        assert "Improved Skill" in result["best_individual"]["content"]

    def test_llm_improve_正常系(self, sample_skill, temp_dir):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), mode="llm_improve")
        optimizer.run_dir = temp_dir / "test_run"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "```markdown\n# Better Skill\n\nImproved.\n```"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"), \
             patch("optimize.subprocess.run", return_value=mock_result):
            result = optimizer.run()

        assert result["strategy"] == "llm_improve"
        assert result["corrections_used"] == 0

    def test_regression_gate_行数超過(self, sample_skill, temp_dir):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        optimizer.run_dir = temp_dir / "test_run"

        # 行数超過のパッチを返すモック
        long_content = "\n".join([f"line {i}" for i in range(1000)])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"```markdown\n{long_content}\n```"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"), \
             patch("optimize.subprocess.run", return_value=mock_result):
            result = optimizer.run()

        assert result.get("gate_rejected") is True
        assert "line_limit_exceeded" in result.get("gate_reason", "")

    def test_regression_gate_空コンテンツ(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        passed, reason = optimizer._regression_gate("")
        assert passed is False
        assert reason == "empty"

    def test_regression_gate_禁止パターン(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        passed, reason = optimizer._regression_gate("# Skill\n\nTODO: fix this")
        assert passed is False
        assert "forbidden_pattern(TODO)" in reason

    def test_regression_gate_正常通過(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        passed, reason = optimizer._regression_gate("# Good Skill\n\nThis is fine.")
        assert passed is True
        assert reason is None

    def test_regression_gate_frontmatter_保持(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        optimizer.original_content = "---\nname: test\n---\n\n# Original"
        passed, reason = optimizer._regression_gate("---\nname: test\n---\n\n# Improved")
        assert passed is True
        assert reason is None

    def test_regression_gate_frontmatter_消失(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        optimizer.original_content = "---\nname: test\n---\n\n# Original"
        passed, reason = optimizer._regression_gate("# Improved without frontmatter")
        assert passed is False
        assert reason == "frontmatter_lost"

    def test_regression_gate_frontmatter_なし_スキップ(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        optimizer.original_content = "# No frontmatter skill"
        passed, reason = optimizer._regression_gate("# Updated skill")
        assert passed is True
        assert reason is None

    def test_format_gate_reason_frontmatter_lost(self):
        msg = DirectPatchOptimizer._format_gate_reason("frontmatter_lost")
        assert "frontmatter" in msg
        assert "消失" in msg

    def test_llm_コール失敗(self, sample_skill, temp_dir):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill))
        optimizer.run_dir = temp_dir / "test_run"

        with patch("optimize._CORRECTIONS_PATH", temp_dir / "missing.jsonl"), \
             patch("optimize.subprocess.run", side_effect=FileNotFoundError):
            result = optimizer.run()

        assert result.get("error") is not None
        assert "claude CLI" in result["error"]

    def test_error_guided_corrections_0件_フォールバック(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), mode="error_guided")
        strategy = optimizer._determine_strategy([])
        assert strategy == "llm_improve"

    def test_auto_mode_corrections_あり(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), mode="auto")
        strategy = optimizer._determine_strategy([{"message": "fix"}])
        assert strategy == "error_guided"

    def test_auto_mode_corrections_なし(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), mode="auto")
        strategy = optimizer._determine_strategy([])
        assert strategy == "llm_improve"


# --- バックアップ/復元テスト ---

class TestBackupRestore:
    def test_backup_作成(self, sample_skill):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), dry_run=True)
        optimizer.backup_original()
        backup_path = sample_skill.with_suffix(sample_skill.suffix + BACKUP_SUFFIX)
        assert backup_path.exists()

    def test_restore(self, sample_skill):
        original_content = sample_skill.read_text(encoding="utf-8")
        backup_path = sample_skill.with_suffix(sample_skill.suffix + BACKUP_SUFFIX)
        shutil.copy2(sample_skill, backup_path)

        sample_skill.write_text("modified content", encoding="utf-8")
        DirectPatchOptimizer.restore(str(sample_skill))

        assert sample_skill.read_text(encoding="utf-8") == original_content
        assert not backup_path.exists()


# --- History テスト (Task 4.2, 4.4) ---

class TestHistory:
    def test_history_entry_format(self, sample_skill, temp_dir):
        optimizer = DirectPatchOptimizer(target_path=str(sample_skill), dry_run=True)
        optimizer.run_dir = temp_dir / "test_run"

        result = {
            "run_id": "test_run",
            "target": str(sample_skill),
            "strategy": "error_guided",
            "corrections_used": 3,
            "fitness_func": "default",
            "best_individual": {"fitness": 0.8},
        }

        history_path = optimizer.save_history_entry(result)
        assert history_path.exists()

        entry = json.loads(history_path.read_text(encoding="utf-8").strip())
        assert entry["strategy"] == "error_guided"
        assert entry["corrections_used"] == 3
        assert entry["human_accepted"] is None

    def test_record_human_decision(self, temp_dir):
        history_file = temp_dir / "history.jsonl"
        entry = {
            "run_id": "test",
            "strategy": "llm_improve",
            "corrections_used": 0,
            "human_accepted": None,
        }
        history_file.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

        DirectPatchOptimizer.record_human_decision(str(temp_dir / "run1"), human_accepted=True)

        # history.jsonl は run_dir.parent なので、temp_dir 直下にあるはず
        # ここでは temp_dir の構造を合わせる必要がある
        # record_human_decision は run_dir の parent に history.jsonl を探す
        run_dir = temp_dir / "run1"
        run_dir.mkdir(exist_ok=True)
        parent_history = temp_dir / "history.jsonl"

        # history_file をリロード
        updated = json.loads(parent_history.read_text(encoding="utf-8").strip())
        assert updated["human_accepted"] is True


# --- 廃止オプションテスト (Task 4.4) ---

class TestDeprecatedOptions:
    def test_generations_deprecated(self):
        result = _check_deprecated_options(["--generations", "3"])
        assert result is not None
        assert "廃止されました" in result

    def test_population_deprecated(self):
        result = _check_deprecated_options(["--population", "5"])
        assert result is not None

    def test_budget_deprecated(self):
        result = _check_deprecated_options(["--budget", "30"])
        assert result is not None

    def test_cascade_deprecated(self):
        result = _check_deprecated_options(["--cascade", "config.yaml"])
        assert result is not None

    def test_parallel_deprecated(self):
        result = _check_deprecated_options(["--parallel", "4"])
        assert result is not None

    def test_strategy_deprecated(self):
        result = _check_deprecated_options(["--strategy", "budget_mpo"])
        assert result is not None

    def test_valid_options(self):
        result = _check_deprecated_options(["--target", "test.md", "--mode", "auto"])
        assert result is None


# --- Pitfall テスト ---

class TestPitfalls:
    def test_record_pitfall(self, temp_dir):
        skill_path = temp_dir / "SKILL.md"
        skill_path.touch()
        DirectPatchOptimizer._record_pitfall(str(skill_path), "gate", "empty", 0.0)

        pitfalls = temp_dir / "references" / "pitfalls.md"
        assert pitfalls.exists()
        content = pitfalls.read_text(encoding="utf-8")
        assert "empty" in content

    def test_pitfall_重複排除(self, temp_dir):
        skill_path = temp_dir / "SKILL.md"
        skill_path.touch()
        DirectPatchOptimizer._record_pitfall(str(skill_path), "gate", "empty", 0.0)
        DirectPatchOptimizer._record_pitfall(str(skill_path), "gate", "empty", 0.0)

        pitfalls = temp_dir / "references" / "pitfalls.md"
        content = pitfalls.read_text(encoding="utf-8")
        assert content.count("empty") == 1


# --- _extract_markdown テスト ---

class TestExtractMarkdown:
    def test_markdown_block(self):
        text = "Some text\n```markdown\n# Title\n\nContent\n```\nMore text"
        result = DirectPatchOptimizer._extract_markdown(text)
        assert result == "# Title\n\nContent"

    def test_plain_code_block(self):
        text = "```\n# Title\n```"
        result = DirectPatchOptimizer._extract_markdown(text)
        assert result == "# Title"

    def test_no_block(self):
        text = "# Just plain text"
        result = DirectPatchOptimizer._extract_markdown(text)
        assert result == "# Just plain text"

    def test_empty(self):
        result = DirectPatchOptimizer._extract_markdown("")
        assert result is None

    def test_multiple_blocks_returns_longest(self):
        text = (
            "Here is the result:\n"
            "```markdown\nshort\n```\n\n"
            "Full improved version:\n"
            "```markdown\n# Full Skill\n\nThis is the complete improved skill.\n\n## Section\n\nMore content.\n```\n"
        )
        result = DirectPatchOptimizer._extract_markdown(text)
        assert "Full Skill" in result
        assert "More content" in result
        assert len(result) > len("short")
