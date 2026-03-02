#!/usr/bin/env python3
"""遺伝的プロンプト最適化のユニットテスト"""

import json
import shutil
import subprocess
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

    def test_strategy_field(self):
        """strategy フィールドの初期値とシリアライズ"""
        ind = Individual("テスト")
        assert ind.strategy is None
        assert ind.to_dict()["strategy"] is None

        ind.strategy = "mutation"
        assert ind.to_dict()["strategy"] == "mutation"

    def test_cot_reasons_field(self):
        """cot_reasons フィールドの初期値とシリアライズ"""
        ind = Individual("テスト")
        assert ind.cot_reasons is None
        assert ind.to_dict()["cot_reasons"] is None

        ind.cot_reasons = {"clarity": {"score": 0.8, "reason": "clear"}}
        d = ind.to_dict()
        assert d["cot_reasons"]["clarity"]["score"] == 0.8

    def test_idの一意性(self):
        """同時に作成しても ID が異なる（マイクロ秒まで含むため）"""
        ids = {Individual("a").id for _ in range(10)}
        # マイクロ秒精度なので大部分はユニークだが、完全保証は難しいため5以上で OK
        assert len(ids) >= 5


# --- テレメトリのテスト ---

class TestTelemetry:
    """strategy / cot_reasons / human_accepted / rejection_reason のテスト"""

    def test_mutate_sets_strategy(self, sample_skill, temp_dir):
        """mutate() が strategy = 'mutation' を設定する"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            generations=1,
            population_size=2,
            dry_run=True,
        )
        ind = Individual("テスト", generation=0)
        # dry_run でも mutate はフォールバックで返す
        result = optimizer.mutate(ind, 1)
        assert result.strategy == "mutation"

    def test_crossover_sets_strategy(self, sample_skill, temp_dir):
        """crossover() が strategy = 'crossover' を設定する"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            generations=1,
            population_size=2,
            dry_run=True,
        )
        p1 = Individual("親1", generation=0)
        p2 = Individual("親2", generation=0)
        result = optimizer.crossover(p1, p2, 1)
        assert result.strategy == "crossover"

    def test_elite_sets_strategy(self, sample_skill, temp_dir):
        """next_generation() のエリートが strategy = 'elite' を持つ"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            generations=1,
            population_size=3,
            dry_run=True,
        )
        pop = [Individual(f"個体{i}", generation=0) for i in range(3)]
        for i, ind in enumerate(pop):
            ind.fitness = 0.9 - i * 0.1
        new_pop = optimizer.next_generation(pop, 1)
        assert new_pop[0].strategy == "elite"

    def test_history_jsonl_creation(self, sample_skill, temp_dir):
        """save_history_entry が history.jsonl にエントリを書く"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            generations=1,
            population_size=2,
            dry_run=True,
        )
        optimizer.run_dir = temp_dir / "test_run"
        optimizer.run_dir.mkdir(parents=True)

        result = {"run_id": "test", "best_individual": {"fitness": 0.8, "strategy": "elite"}}
        path = optimizer.save_history_entry(result, human_accepted=True)

        assert path.exists()
        entry = json.loads(path.read_text().strip())
        assert entry["human_accepted"] is True
        assert entry["rejection_reason"] is None

    def test_record_human_decision_reject(self, sample_skill, temp_dir):
        """record_human_decision が rejection_reason を記録する"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            generations=1,
            population_size=2,
            dry_run=True,
        )
        optimizer.run_dir = temp_dir / "test_run"
        optimizer.run_dir.mkdir(parents=True)

        result = {"run_id": "test", "best_individual": {"fitness": 0.5}}
        optimizer.save_history_entry(result)

        GeneticOptimizer.record_human_decision(
            str(optimizer.run_dir), human_accepted=False, rejection_reason="品質不足"
        )

        history_file = optimizer.run_dir.parent / "history.jsonl"
        entry = json.loads(history_file.read_text().strip())
        assert entry["human_accepted"] is False
        assert entry["rejection_reason"] == "品質不足"

    def test_to_dict_includes_telemetry(self):
        """to_dict() に strategy と cot_reasons が含まれる"""
        ind = Individual("test")
        ind.strategy = "crossover"
        ind.cot_reasons = {"clarity": {"score": 0.9, "reason": "very clear"}}
        d = ind.to_dict()
        assert "strategy" in d
        assert "cot_reasons" in d
        assert d["strategy"] == "crossover"
        assert d["cot_reasons"]["clarity"]["score"] == 0.9


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


# --- CoT 評価のテスト ---

class TestCoTEvaluation:
    """Chain-of-Thought 評価のテスト"""

    def test_正常JSON(self):
        """正常な CoT JSON レスポンスをパースできる"""
        response = json.dumps({
            "clarity": {"score": 0.8, "reason": "手順が明確"},
            "completeness": {"score": 0.7, "reason": "エッジケース不足"},
            "structure": {"score": 0.9, "reason": "見出し階層が適切"},
            "practicality": {"score": 0.75, "reason": "コード例あり"},
            "total": 0.79,
        })
        score, cot = GeneticOptimizer._parse_cot_response(response)
        assert score == 0.79
        assert cot is not None
        assert cot["clarity"]["score"] == 0.8
        assert cot["clarity"]["reason"] == "手順が明確"

    def test_JSONブロック付きレスポンス(self):
        """```json ... ``` で囲まれたレスポンスをパースできる"""
        response = (
            "評価結果:\n```json\n"
            '{"clarity": {"score": 0.6, "reason": "曖昧"}, '
            '"completeness": {"score": 0.5, "reason": "不足"}, '
            '"structure": {"score": 0.7, "reason": "OK"}, '
            '"practicality": {"score": 0.8, "reason": "良い"}, '
            '"total": 0.65}\n```'
        )
        score, cot = GeneticOptimizer._parse_cot_response(response)
        assert score == 0.65
        assert cot is not None

    def test_total無しJSON(self):
        """total がない場合、各基準の平均を計算する"""
        response = json.dumps({
            "clarity": {"score": 0.8, "reason": "明確"},
            "completeness": {"score": 0.6, "reason": "不足"},
            "structure": {"score": 0.8, "reason": "良い"},
            "practicality": {"score": 0.8, "reason": "実用的"},
        })
        score, cot = GeneticOptimizer._parse_cot_response(response)
        assert score == pytest.approx(0.75, abs=0.01)
        assert cot is not None
        assert cot["total"] == 0.75

    def test_不正JSON(self):
        """不正な JSON の場合、正規表現フォールバックで数値を抽出"""
        response = "スコアは 0.72 です"
        score, cot = GeneticOptimizer._parse_cot_response(response)
        assert score == 0.72
        assert cot is None

    def test_空出力(self):
        """空の出力の場合、デフォルト 0.5 を返す"""
        score, cot = GeneticOptimizer._parse_cot_response("")
        assert score == 0.5
        assert cot is None

    def test_スコアの範囲制限(self):
        """スコアが 0.0〜1.0 にクランプされる"""
        response = json.dumps({
            "clarity": {"score": 0.8, "reason": "OK"},
            "completeness": {"score": 0.7, "reason": "OK"},
            "structure": {"score": 0.9, "reason": "OK"},
            "practicality": {"score": 0.75, "reason": "OK"},
            "total": 1.5,
        })
        score, cot = GeneticOptimizer._parse_cot_response(response)
        assert score == 1.0


# --- Pairwise Comparison のテスト ---

class TestPairwiseComparison:
    """Pairwise Comparison のテスト"""

    def test_dry_run_高スコアが勝つ(self, sample_skill):
        """dry-run では絶対スコアの高い方が選ばれる"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            dry_run=True,
        )
        a = Individual("スキルA")
        a.fitness = 0.8
        b = Individual("スキルB")
        b.fitness = 0.6

        winner = optimizer.pairwise_compare(a, b)
        assert winner is a

    def test_dry_run_同スコアはAが勝つ(self, sample_skill):
        """dry-run で同スコアの場合は a が選ばれる"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            dry_run=True,
        )
        a = Individual("スキルA")
        a.fitness = 0.7
        b = Individual("スキルB")
        b.fitness = 0.7

        winner = optimizer.pairwise_compare(a, b)
        assert winner is a

    def test_スコア差0_1以内でpairwise呼び出し(self, sample_skill):
        """トップ2のスコア差が 0.1 以内のとき pairwise_compare が呼ばれる"""
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
        population[0].fitness = 0.80
        population[1].fitness = 0.75  # 差が 0.05 なので pairwise が呼ばれる
        population[2].fitness = 0.50

        with patch.object(optimizer, "pairwise_compare", wraps=optimizer.pairwise_compare) as mock_pw, \
             patch.object(optimizer, "mutate") as mock_mutate, \
             patch.object(optimizer, "crossover") as mock_cross:
            mock_mutate.return_value = Individual("変異", generation=1)
            mock_cross.return_value = Individual("交叉", generation=1)

            optimizer.next_generation(population, 1)

            mock_pw.assert_called_once()

    def test_スコア差0_1超でpairwise呼ばない(self, sample_skill):
        """トップ2のスコア差が 0.1 を超えるとき pairwise_compare は呼ばれない"""
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
        population[0].fitness = 0.90
        population[1].fitness = 0.60  # 差が 0.3 なので pairwise は不要
        population[2].fitness = 0.50

        with patch.object(optimizer, "pairwise_compare") as mock_pw, \
             patch.object(optimizer, "mutate") as mock_mutate, \
             patch.object(optimizer, "crossover") as mock_cross:
            mock_mutate.return_value = Individual("変異", generation=1)
            mock_cross.return_value = Individual("交叉", generation=1)

            optimizer.next_generation(population, 1)

            mock_pw.assert_not_called()


# --- Regression Gate のテスト ---

class TestRegressionGate:
    """回帰テストゲートのテスト"""

    def test_空コンテンツは不合格(self, sample_skill):
        """空のコンテンツは不合格"""
        optimizer = GeneticOptimizer(target_path=str(sample_skill))
        passed, reason = optimizer._regression_gate("")
        assert passed is False
        assert reason == "empty"

    def test_空白のみは不合格(self, sample_skill):
        """空白のみのコンテンツは不合格"""
        optimizer = GeneticOptimizer(target_path=str(sample_skill))
        passed, reason = optimizer._regression_gate("   \n  ")
        assert passed is False
        assert reason == "empty"

    def test_行数超過は不合格(self, temp_dir):
        """行数上限を超えるコンテンツは不合格"""
        # ルールファイル（3行上限）
        rule_path = temp_dir / ".claude" / "rules" / "test.md"
        rule_path.parent.mkdir(parents=True)
        rule_path.write_text("# test", encoding="utf-8")

        optimizer = GeneticOptimizer(target_path=str(rule_path))
        content = "行1\n行2\n行3\n行4\n行5"  # 5行 > 3行上限
        passed, reason = optimizer._regression_gate(content)
        assert passed is False
        assert "line_limit_exceeded" in reason

    def test_禁止パターンTODOは不合格(self, sample_skill):
        """TODO を含むコンテンツは不合格"""
        optimizer = GeneticOptimizer(target_path=str(sample_skill))
        passed, reason = optimizer._regression_gate("# スキル\nTODO: あとで実装")
        assert passed is False
        assert "forbidden_pattern(TODO)" == reason

    def test_禁止パターンFIXMEは不合格(self, sample_skill):
        """FIXME を含むコンテンツは不合格"""
        optimizer = GeneticOptimizer(target_path=str(sample_skill))
        passed, reason = optimizer._regression_gate("# スキル\nFIXME: バグ")
        assert passed is False
        assert "forbidden_pattern(FIXME)" == reason

    def test_禁止パターンHACKは不合格(self, sample_skill):
        """HACK を含むコンテンツは不合格"""
        optimizer = GeneticOptimizer(target_path=str(sample_skill))
        passed, reason = optimizer._regression_gate("# スキル\nHACK: 回避策")
        assert passed is False
        assert "forbidden_pattern(HACK)" == reason

    def test_禁止パターンXXXは不合格(self, sample_skill):
        """XXX を含むコンテンツは不合格"""
        optimizer = GeneticOptimizer(target_path=str(sample_skill))
        passed, reason = optimizer._regression_gate("# スキル\nXXX: 注意")
        assert passed is False
        assert "forbidden_pattern(XXX)" == reason

    def test_正常コンテンツは合格(self, sample_skill):
        """正常なコンテンツは合格"""
        optimizer = GeneticOptimizer(target_path=str(sample_skill))
        content = "# テストスキル\n\nこれは正常なスキルです。"
        passed, reason = optimizer._regression_gate(content)
        assert passed is True
        assert reason is None


# --- 実行ベース評価のテスト ---

class TestExecutionEvaluation:
    """実行ベース評価のテスト"""

    def test_テストタスクYAMLのロード(self, temp_dir):
        """YAML ファイルからテストタスクを正しくロードできる"""
        yaml_content = json.dumps({
            "tasks": [
                {"name": "task1", "prompt": "テスト", "expected": "出力"},
                {"name": "task2", "prompt": "テスト2", "expected": "出力2"},
            ]
        })
        task_file = temp_dir / "test-tasks.json"
        task_file.write_text(yaml_content, encoding="utf-8")

        tasks = GeneticOptimizer._load_test_tasks(str(task_file))
        assert len(tasks) == 2
        assert tasks[0]["name"] == "task1"

    def test_存在しないファイルは空リスト(self):
        """存在しないファイルは空リストを返す"""
        tasks = GeneticOptimizer._load_test_tasks("/nonexistent/path.yaml")
        assert tasks == []

    def test_テストタスクなしでスコア0_5(self, sample_skill):
        """テストタスクが未設定の場合は 0.5 を返す"""
        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
        )
        ind = Individual("# テスト\nテスト内容")
        score = optimizer._execution_evaluate(ind)
        assert score == 0.5

    def test_タイムアウト時スコア0(self, sample_skill, temp_dir):
        """タイムアウト時はスコア 0.0 を返す"""
        task_file = temp_dir / "tasks.json"
        task_file.write_text(
            json.dumps({"tasks": [{"name": "t", "prompt": "p", "expected": "e"}]}),
            encoding="utf-8",
        )

        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            test_tasks=str(task_file),
        )
        ind = Individual("# テスト")

        with patch("optimize.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
            score = optimizer._execution_evaluate(ind)

        assert score == 0.0

    def test_正常実行(self, sample_skill, temp_dir):
        """正常なモック実行で正しいスコアが返る"""
        task_file = temp_dir / "tasks.json"
        task_file.write_text(
            json.dumps({"tasks": [{"name": "t", "prompt": "p", "expected": "e"}]}),
            encoding="utf-8",
        )

        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            test_tasks=str(task_file),
        )
        ind = Individual("# テスト")

        mock_exec = MagicMock(returncode=0, stdout="タスク出力")
        mock_eval = MagicMock(returncode=0, stdout="0.85")

        with patch("optimize.subprocess.run", side_effect=[mock_exec, mock_eval]):
            score = optimizer._execution_evaluate(ind)

        assert score == 0.85

    def test_加重平均の計算(self, sample_skill, temp_dir):
        """CoT * 0.4 + 実行ベース * 0.6 の加重平均が正しく計算される"""
        task_file = temp_dir / "tasks.json"
        task_file.write_text(
            json.dumps({"tasks": [{"name": "t", "prompt": "p", "expected": "e"}]}),
            encoding="utf-8",
        )

        optimizer = GeneticOptimizer(
            target_path=str(sample_skill),
            test_tasks=str(task_file),
        )
        ind = Individual("# テスト")

        # _llm_evaluate -> (0.8, cot_data), _execution_evaluate -> 0.9
        with patch.object(optimizer, "_llm_evaluate", return_value=(0.8, None)), \
             patch.object(optimizer, "_execution_evaluate", return_value=0.9), \
             patch.object(optimizer, "_regression_gate", return_value=(True, None)):
            score = optimizer.evaluate(ind)

        # 0.8 * 0.4 + 0.9 * 0.6 = 0.32 + 0.54 = 0.86
        assert score == pytest.approx(0.86, abs=0.001)


# --- Pitfall Accumulator のテスト ---

class TestPitfallAccumulator:
    """失敗パターン自動蓄積のテスト"""

    def test_新規作成(self, temp_dir):
        """pitfalls.md が存在しない場合、新規作成される"""
        skill_path = temp_dir / "test-skill.md"
        skill_path.write_text("# test", encoding="utf-8")

        GeneticOptimizer._record_pitfall(
            str(skill_path), "gate", "empty", 0.0
        )

        pitfalls = temp_dir / "references" / "pitfalls.md"
        assert pitfalls.exists()
        content = pitfalls.read_text(encoding="utf-8")
        assert "| gate | empty | 0.00 |" in content

    def test_追記(self, temp_dir):
        """既存の pitfalls.md に追記される"""
        skill_path = temp_dir / "test-skill.md"
        skill_path.write_text("# test", encoding="utf-8")

        GeneticOptimizer._record_pitfall(str(skill_path), "gate", "empty", 0.0)
        GeneticOptimizer._record_pitfall(str(skill_path), "cot", "clarity: low", 0.3)

        pitfalls = temp_dir / "references" / "pitfalls.md"
        content = pitfalls.read_text(encoding="utf-8")
        assert "| gate | empty | 0.00 |" in content
        assert "| cot | clarity: low | 0.30 |" in content

    def test_重複排除(self, temp_dir):
        """同じパターンは重複追記されない"""
        skill_path = temp_dir / "test-skill.md"
        skill_path.write_text("# test", encoding="utf-8")

        GeneticOptimizer._record_pitfall(str(skill_path), "gate", "empty", 0.0)
        GeneticOptimizer._record_pitfall(str(skill_path), "gate", "empty", 0.0)

        pitfalls = temp_dir / "references" / "pitfalls.md"
        content = pitfalls.read_text(encoding="utf-8")
        # データ行（ヘッダー2行を除く）が1行のみ
        data_lines = [
            l for l in content.strip().split("\n")[2:]
            if l.strip().startswith("|")
        ]
        assert len(data_lines) == 1

    def test_行数上限(self, temp_dir):
        """50行上限を超えると古い行が削除される"""
        skill_path = temp_dir / "test-skill.md"
        skill_path.write_text("# test", encoding="utf-8")

        for i in range(55):
            GeneticOptimizer._record_pitfall(
                str(skill_path), "gate", f"pattern_{i}", 0.0
            )

        pitfalls = temp_dir / "references" / "pitfalls.md"
        content = pitfalls.read_text(encoding="utf-8")
        data_lines = [
            l for l in content.strip().split("\n")[2:]
            if l.strip().startswith("|")
        ]
        assert len(data_lines) == 50
        # 最初の5つが削除されている
        assert "pattern_0" not in content
        assert "pattern_54" in content

    def test_動的ゲートチェック(self, temp_dir):
        """pitfalls.md のパターンが regression_gate で動的チェックされる"""
        skill_path = temp_dir / "test-skill.md"
        skill_path.write_text("# test", encoding="utf-8")

        # pitfalls.md に gate パターンを手動追加
        refs_dir = temp_dir / "references"
        refs_dir.mkdir(parents=True, exist_ok=True)
        pitfalls = refs_dir / "pitfalls.md"
        pitfalls.write_text(
            "| Source | Pattern | Score |\n"
            "|--------|---------|-------|\n"
            "| gate | forbidden_pattern(DANGER) | 0.00 |\n",
            encoding="utf-8",
        )

        optimizer = GeneticOptimizer(target_path=str(skill_path))
        # DANGER を含むコンテンツは不合格
        passed, reason = optimizer._regression_gate("# スキル\nDANGER: 注意")
        assert passed is False
        assert "pitfall_pattern(DANGER)" == reason

    def test_動的ゲート_pitfallsなし(self, temp_dir):
        """pitfalls.md が存在しない場合、動的パターンチェックはスキップ"""
        skill_path = temp_dir / "test-skill.md"
        skill_path.write_text("# test", encoding="utf-8")

        optimizer = GeneticOptimizer(target_path=str(skill_path))
        passed, reason = optimizer._regression_gate("# 正常なコンテンツ")
        assert passed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
