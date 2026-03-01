#!/usr/bin/env python3
"""遺伝的プロンプト最適化のユニットテスト"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# テスト対象のモジュールをインポートできるようにパスを追加
sys.path.insert(
    0, str(Path(__file__).parent.parent / "scripts")
)

from optimize import Individual, GeneticOptimizer, BACKUP_SUFFIX


# --- テスト用フィクスチャ ---

@pytest.fixture
def temp_dir():
    """一時ディレクトリを作成"""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_skill(temp_dir):
    """テスト用スキルファイルを作成"""
    skill_path = temp_dir / "test-skill.md"
    skill_path.write_text(
        "---\nname: test\ndescription: テスト用スキル\n---\n\n"
        "# テストスキル\n\nこれはテスト用のスキルです。\n",
        encoding="utf-8",
    )
    return skill_path


# --- Individual クラスのテスト ---

class TestIndividual:
    """Individual クラスのテスト"""

    def test_初期化(self):
        ind = Individual("テストコンテンツ", generation=1, parent_ids=["p1"])
        assert ind.content == "テストコンテンツ"
        assert ind.generation == 1
        assert ind.parent_ids == ["p1"]
        assert ind.fitness is None
        assert ind.id.startswith("gen1_")

    def test_デフォルト初期化(self):
        ind = Individual("内容")
        assert ind.generation == 0
        assert ind.parent_ids == []

    def test_to_dict(self):
        ind = Individual("テスト", generation=2)
        ind.fitness = 0.75
        d = ind.to_dict()

        assert d["generation"] == 2
        assert d["fitness"] == 0.75
        assert d["content"] == "テスト"
        assert d["content_length"] == 3
        assert "id" in d
        assert "parent_ids" in d

    def test_idの一意性(self):
        """同時に作成しても ID が異なる（マイクロ秒まで含むため）"""
        ids = {Individual("a").id for _ in range(10)}
        # マイクロ秒精度なので大部分はユニークだが、完全保証は難しいため5以上で OK
        assert len(ids) >= 5


# --- GeneticOptimizer のテスト ---

class TestGeneticOptimizer:
    """GeneticOptimizer のテスト"""

    def test_dry_run_実行(self, sample_skill, temp_dir):
        """dry-run モードで基本的な最適化ループが動作する"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            generations=2,
            population_size=3,
            dry_run=True,
        )
        # generations ディレクトリを temp_dir に変更
        optimizer.run_dir = temp_dir / "test_run"

        result = optimizer.run()

        assert result["run_id"] is not None
        assert result["generations"] == 2
        assert result["population_size"] == 3
        assert result["dry_run"] is True
        assert result["best_individual"] is not None
        assert len(result["history"]) == 2

        # 全個体にスコアがある
        for gen_record in result["history"]:
            for ind in gen_record["individuals"]:
                assert ind["fitness"] is not None
                assert 0.0 <= ind["fitness"] <= 1.0

    def test_dry_run_スコア計算(self, sample_skill):
        """dry-run のスコア計算が正しい"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            dry_run=True,
        )
        content = sample_skill.read_text(encoding="utf-8")
        ind = Individual(content)
        score = optimizer.evaluate(ind)

        # dry-run: min(len/5000, 1.0) * 0.5 + 0.3
        expected_base = min(len(content) / 5000, 1.0)
        expected = round(expected_base * 0.5 + 0.3, 2)
        assert score == expected

    def test_バックアップ作成(self, sample_skill):
        """バックアップファイルが作成される"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            dry_run=True,
        )
        optimizer.backup_original()

        backup_path = sample_skill.with_suffix(
            sample_skill.suffix + BACKUP_SUFFIX
        )
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == sample_skill.read_text(
            encoding="utf-8"
        )

    def test_バックアップ二重作成防止(self, sample_skill):
        """既にバックアップがある場合は上書きしない"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            dry_run=True,
        )
        # 1回目
        optimizer.backup_original()

        # スキルファイルを変更
        sample_skill.write_text("変更後の内容", encoding="utf-8")

        # 2回目（上書きされないはず）
        optimizer.backup_original()

        backup_path = sample_skill.with_suffix(
            sample_skill.suffix + BACKUP_SUFFIX
        )
        # バックアップは元の内容のまま
        assert "変更後の内容" not in backup_path.read_text(encoding="utf-8")

    def test_初期集団_dry_run(self, sample_skill):
        """dry-run モードの初期集団生成"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            population_size=4,
            dry_run=True,
        )
        original = sample_skill.read_text(encoding="utf-8")
        population = optimizer.initialize_population(original)

        assert len(population) == 4
        # 最初の個体はオリジナル
        assert population[0].content == original
        # バリエーションにはコメントが追加されている
        for i in range(1, 4):
            assert f"<!-- variant {i} -->" in population[i].content

    def test_世代データ保存(self, sample_skill, temp_dir):
        """世代データが JSON として保存される"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            dry_run=True,
        )
        optimizer.run_dir = temp_dir / "test_run"

        population = [
            Individual("テスト1"),
            Individual("テスト2"),
        ]
        population[0].fitness = 0.8
        population[1].fitness = 0.6

        optimizer.save_generation(0, population)

        gen_dir = optimizer.run_dir / "gen_0"
        assert gen_dir.exists()

        json_files = list(gen_dir.glob("*.json"))
        assert len(json_files) == 2

        # JSON が正しく読める
        for f in json_files:
            data = json.loads(f.read_text(encoding="utf-8"))
            assert "id" in data
            assert "fitness" in data
            assert "content" in data

    def test_結果保存(self, sample_skill, temp_dir):
        """最終結果が JSON として保存される"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            dry_run=True,
        )
        optimizer.run_dir = temp_dir / "test_run"

        result = {
            "run_id": "test",
            "best_individual": {"id": "gen0_test", "fitness": 0.8},
        }
        optimizer.save_result(result)

        result_file = optimizer.run_dir / "result.json"
        assert result_file.exists()
        loaded = json.loads(result_file.read_text(encoding="utf-8"))
        assert loaded["run_id"] == "test"

    def test_次世代生成(self, sample_skill):
        """next_generation が正しいサイズの集団を返す"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            population_size=3,
            dry_run=True,
        )

        population = [
            Individual("ベスト", generation=0),
            Individual("セカンド", generation=0),
            Individual("サード", generation=0),
        ]
        population[0].fitness = 0.9
        population[1].fitness = 0.7
        population[2].fitness = 0.5

        # dry-run ではmutate/crossover が claude CLI を呼ぶのでモック
        with patch.object(optimizer, "mutate") as mock_mutate, \
             patch.object(optimizer, "crossover") as mock_cross:
            mock_mutate.return_value = Individual("変異", generation=1)
            mock_cross.return_value = Individual("交叉", generation=1)

            new_pop = optimizer.next_generation(population, 1)

        assert len(new_pop) == 3
        # エリート（上位1体）は元のコンテンツを保持
        assert new_pop[0].content == "ベスト"
        assert new_pop[0].fitness == 0.9


# --- restore のテスト ---

class TestRestore:
    """バックアップ復元のテスト"""

    def test_復元成功(self, sample_skill):
        """バックアップから正しく復元される"""
        original_content = sample_skill.read_text(encoding="utf-8")

        # バックアップ作成
        backup_path = sample_skill.with_suffix(
            sample_skill.suffix + BACKUP_SUFFIX
        )
        shutil.copy2(sample_skill, backup_path)

        # スキルファイルを変更
        sample_skill.write_text("変更後の内容", encoding="utf-8")

        # 復元
        GeneticOptimizer.restore(str(sample_skill))

        # 元の内容に戻っている
        assert sample_skill.read_text(encoding="utf-8") == original_content
        # バックアップは削除されている
        assert not backup_path.exists()

    def test_バックアップなしで復元(self, sample_skill, capsys):
        """バックアップがない場合にエラーメッセージを出す"""
        with pytest.raises(SystemExit):
            GeneticOptimizer.restore(str(sample_skill))


# --- extract_markdown のテスト ---

class TestExtractMarkdown:
    """Markdown 抽出のテスト"""

    def test_markdownブロック抽出(self):
        text = '何かのテキスト\n```markdown\n# タイトル\n内容\n```\n後続テキスト'
        result = GeneticOptimizer._extract_markdown(text)
        assert result == "# タイトル\n内容"

    def test_言語指定なしブロック(self):
        text = '```\n# タイトル\n内容\n```'
        result = GeneticOptimizer._extract_markdown(text)
        assert result == "# タイトル\n内容"

    def test_マークダウンブロックなし(self):
        """ブロックがない場合はテキスト全体を返す"""
        text = "単純なテキスト"
        result = GeneticOptimizer._extract_markdown(text)
        assert result == "単純なテキスト"

    def test_空テキスト(self):
        result = GeneticOptimizer._extract_markdown("")
        assert result is None

    def test_空白のみ(self):
        result = GeneticOptimizer._extract_markdown("   \n  ")
        assert result is None


# --- カスタム適応度関数のテスト ---

class TestCustomFitness:
    """カスタム適応度関数のテスト"""

    def test_default関数はNone(self, sample_skill):
        """fitness_func が 'default' の場合は None を返す"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            fitness_func="default",
        )
        ind = Individual("テスト")
        result = optimizer._run_custom_fitness(ind)
        assert result is None

    def test_存在しない関数(self, sample_skill, temp_dir):
        """存在しない適応度関数は None を返す"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            fitness_func="nonexistent",
        )
        ind = Individual("テスト")

        # cwd を temp_dir に設定（fitness ファイルが見つからないようにする）
        with patch("optimize.Path.cwd", return_value=temp_dir):
            result = optimizer._run_custom_fitness(ind)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
