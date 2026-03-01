#!/usr/bin/env python3
"""rl-loop-orchestrator のテスト"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# run-loop.py はハイフン入りなので importlib で読み込む
import importlib.util
spec = importlib.util.spec_from_file_location(
    "run_loop",
    Path(__file__).parent.parent / "scripts" / "run-loop.py",
)
run_loop_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_loop_mod)


class TestGetBaselineScore:
    """ベースラインスコア取得のテスト"""

    def test_dry_run_returns_dummy(self):
        """dry-run 時はダミースコアを返す"""
        result = run_loop_mod.get_baseline_score("/dummy/path", dry_run=True)
        assert "integrated_score" in result
        assert isinstance(result["integrated_score"], float)
        assert 0.0 <= result["integrated_score"] <= 1.0

    def test_dry_run_has_scores_structure(self):
        """dry-run スコアに scores 構造がある"""
        result = run_loop_mod.get_baseline_score("/dummy/path", dry_run=True)
        assert "scores" in result
        assert "technical" in result["scores"]
        assert "domain_quality" in result["scores"]
        assert "structure" in result["scores"]


class TestScoreVariant:
    """バリエーションスコアリングのテスト"""

    def test_dry_run_returns_score(self):
        """dry-run 時はスコアを返す"""
        score = run_loop_mod.score_variant(
            "# テストスキル\nテスト内容", "/dummy/path", dry_run=True
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_different_content_different_scores(self):
        """異なる内容は異なるスコアを返す（確率的）"""
        scores = set()
        for i in range(10):
            score = run_loop_mod.score_variant(
                f"# スキル バリエーション {i}\n内容 {i * 100}",
                "/dummy/path",
                dry_run=True,
            )
            scores.add(score)
        # 10個中少なくとも2種類以上のスコアがあるはず
        assert len(scores) >= 2


class TestRunLoop:
    """メインループのテスト"""

    def test_dry_run_completes(self, tmp_path):
        """dry-run で1ループが完走する"""
        # テスト用スキルファイルを作成
        skill_file = tmp_path / "test-skill.md"
        skill_file.write_text(
            "---\ndescription: テストスキル\n---\n\n# テスト\nテスト内容です。\n",
            encoding="utf-8",
        )

        # OUTPUT_DIR を一時ディレクトリに差し替え
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch.object(run_loop_mod, "generate_variants") as mock_gen:

            # generate_variants のモック
            mock_gen.return_value = {
                "history": [{
                    "generation": 0,
                    "individuals": [
                        {
                            "id": "test_variant_0",
                            "content": "# 改善版スキル\n改善された内容。\n",
                        },
                        {
                            "id": "test_variant_1",
                            "content": "# 別の改善版\n別の改善された内容。\n",
                        },
                    ],
                }],
            }

            results = run_loop_mod.run_loop(
                target_path=str(skill_file),
                loops=1,
                population=2,
                dry_run=True,
                output_dir=str(output_dir),
            )

            assert len(results) == 1
            assert results[0]["dry_run"] is True
            assert "baseline_score" in results[0]
            assert "best_score" in results[0]

    def test_multiple_loops(self, tmp_path):
        """複数ループが実行される"""
        skill_file = tmp_path / "test-skill.md"
        skill_file.write_text("# テスト\nテスト", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch.object(run_loop_mod, "generate_variants") as mock_gen:

            mock_gen.return_value = {
                "history": [{
                    "generation": 0,
                    "individuals": [
                        {"id": "v0", "content": "# V0\n内容"},
                    ],
                }],
            }

            results = run_loop_mod.run_loop(
                target_path=str(skill_file),
                loops=3,
                population=1,
                dry_run=True,
                output_dir=str(output_dir),
            )

            assert len(results) == 3

    def test_history_file_created(self, tmp_path):
        """履歴ファイルが作成される"""
        skill_file = tmp_path / "test-skill.md"
        skill_file.write_text("# テスト\nテスト", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch.object(run_loop_mod, "generate_variants") as mock_gen:

            mock_gen.return_value = {
                "history": [{
                    "generation": 0,
                    "individuals": [
                        {"id": "v0", "content": "# V0\n内容"},
                    ],
                }],
            }

            run_loop_mod.run_loop(
                target_path=str(skill_file),
                loops=1,
                dry_run=True,
                output_dir=str(output_dir),
            )

            history_file = output_dir / "history.jsonl"
            assert history_file.exists()
            lines = history_file.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) >= 1
            record = json.loads(lines[0])
            assert "baseline_score" in record


class TestEdgeCases:
    """エッジケースのテスト"""

    def test_empty_variants(self, tmp_path):
        """バリエーションが空の場合"""
        skill_file = tmp_path / "test-skill.md"
        skill_file.write_text("# テスト\nテスト", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch.object(run_loop_mod, "generate_variants") as mock_gen:

            mock_gen.return_value = {"history": []}

            results = run_loop_mod.run_loop(
                target_path=str(skill_file),
                loops=1,
                dry_run=True,
                output_dir=str(output_dir),
            )

            # バリエーションなしでもクラッシュしない
            assert len(results) == 0

    def test_generate_variants_error(self, tmp_path):
        """バリエーション生成エラー時"""
        skill_file = tmp_path / "test-skill.md"
        skill_file.write_text("# テスト\nテスト", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch.object(run_loop_mod, "generate_variants") as mock_gen:

            mock_gen.return_value = {"error": "テストエラー"}

            results = run_loop_mod.run_loop(
                target_path=str(skill_file),
                loops=1,
                dry_run=True,
                output_dir=str(output_dir),
            )

            assert len(results) == 0
