#!/usr/bin/env python3
"""遺伝的プロンプト最適化スクリプト

スキル/ルール（SKILL.md）のバリエーションを LLM で生成し、
適応度関数で評価して進化させる。

使用方法:
    python3 optimize.py --target .claude/skills/narrative-ux-writing/SKILL.md --generations 3 --population 3
    python3 optimize.py --target .claude/skills/narrative-ux-writing/SKILL.md --dry-run
    python3 optimize.py --restore --target .claude/skills/narrative-ux-writing/SKILL.md
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- 設定 ---
GENERATIONS_DIR = Path(__file__).parent / "generations"
BACKUP_SUFFIX = ".backup"
MAX_KEPT_RUNS = 5  # generations/ に保持する最大ラン数
MAX_SKILL_LINES = 500  # スキルファイルの行数上限
MAX_RULE_LINES = 3  # ルールファイルの行数上限


class Individual:
    """最適化対象の個体（スキルのバリエーション）"""

    def __init__(
        self, content: str, generation: int = 0, parent_ids: Optional[List[str]] = None
    ):
        self.content = content
        self.generation = generation
        self.parent_ids = parent_ids or []
        self.fitness: Optional[float] = None
        self.id = f"gen{generation}_{datetime.now().strftime('%H%M%S_%f')}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "generation": self.generation,
            "parent_ids": self.parent_ids,
            "fitness": self.fitness,
            "content_length": len(self.content),
            "content": self.content,
        }


class GeneticOptimizer:
    """遺伝的最適化エンジン"""

    def __init__(
        self,
        target_path: str,
        generations: int = 3,
        population_size: int = 3,
        fitness_func: str = "default",
        dry_run: bool = False,
    ):
        self.target_path = Path(target_path)
        self.generations = generations
        self.population_size = population_size
        self.fitness_func = fitness_func
        self.dry_run = dry_run
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = GENERATIONS_DIR / self.run_id

    @property
    def _is_rule_file(self) -> bool:
        """対象がルールファイルかどうか"""
        return ".claude/rules/" in str(self.target_path)

    @property
    def _max_lines(self) -> int:
        """対象ファイルの行数上限"""
        return MAX_RULE_LINES if self._is_rule_file else MAX_SKILL_LINES

    def _check_line_limit(self, content: str) -> bool:
        """行数制限をチェック。超過時は False"""
        lines = content.count("\n") + 1
        return lines <= self._max_lines

    def run(self) -> Dict[str, Any]:
        """最適化ループを実行"""
        # 0. 古い世代データをクリーンアップ
        self._cleanup_old_runs()

        # 1. バックアップ
        self.backup_original()

        # 2. 初期集団生成
        original_content = self.target_path.read_text(encoding="utf-8")
        population = self.initialize_population(original_content)

        # 3. 世代ループ
        best_ever: Optional[Individual] = None
        history: List[Dict[str, Any]] = []

        for gen in range(self.generations):
            print(f"\n--- 世代 {gen} ---")

            # 評価
            for individual in population:
                if individual.fitness is None:
                    individual.fitness = self.evaluate(individual)
                    print(
                        f"  {individual.id}: fitness={individual.fitness:.3f}"
                    )

            # ソート（適応度降順）
            population.sort(key=lambda x: x.fitness or 0, reverse=True)

            # ベスト更新
            if best_ever is None or (population[0].fitness or 0) > (
                best_ever.fitness or 0
            ):
                best_ever = population[0]

            # 記録
            gen_record = {
                "generation": gen,
                "best_fitness": population[0].fitness,
                "avg_fitness": sum(i.fitness or 0 for i in population)
                / len(population),
                "individuals": [i.to_dict() for i in population],
            }
            history.append(gen_record)
            self.save_generation(gen, population)

            # 最終世代でなければ次世代生成
            if gen < self.generations - 1:
                population = self.next_generation(population, gen + 1)

        # 4. 結果保存
        result = {
            "run_id": self.run_id,
            "target": str(self.target_path),
            "generations": self.generations,
            "population_size": self.population_size,
            "fitness_func": self.fitness_func,
            "dry_run": self.dry_run,
            "best_individual": best_ever.to_dict() if best_ever else None,
            "history": history,
        }

        self.save_result(result)
        return result

    def backup_original(self):
        """元のスキルをバックアップ"""
        backup_path = self.target_path.with_suffix(
            self.target_path.suffix + BACKUP_SUFFIX
        )
        if not backup_path.exists():
            shutil.copy2(self.target_path, backup_path)
            print(f"バックアップ作成: {backup_path}")

    def initialize_population(self, original: str) -> List[Individual]:
        """初期集団を生成。オリジナル + バリエーション"""
        population = [Individual(original, generation=0)]

        for i in range(self.population_size - 1):
            if self.dry_run:
                # dry-run: オリジナルのコピーで代用
                variant = Individual(
                    original + f"\n<!-- variant {i + 1} -->",
                    generation=0,
                )
            else:
                variant = self.mutate(Individual(original, generation=0), 0)
            population.append(variant)

        return population

    def mutate(self, individual: Individual, generation: int) -> Individual:
        """LLM で突然変異を生成。
        claude -p で変異指示を与え、変異後のスキル内容を取得。
        行数制限を超える出力は拒否する。
        """
        file_type = "ルール" if self._is_rule_file else "スキル"
        line_constraint = (
            f"\n\n**重要な制約**: 出力は {self._max_lines} 行以内に収めてください。"
            f"{'ルールは3行以内が原則です。詳細な手順は別ファイルに書きます。' if self._is_rule_file else '冗長な説明を避け、簡潔に保ってください。'}"
        )
        prompt = (
            f"以下のClaude Code{file_type}定義を改善してください。\n\n"
            "改善方針（ランダムに1-2個選んで適用）:\n"
            "- より具体的な例を追加\n"
            "- 曖昧な指示を明確化\n"
            "- 構造を整理\n"
            "- 不要な冗長性を削除\n"
            "- エッジケースの対処を追加\n\n"
            "元のスキル:\n"
            f"```markdown\n{individual.content}\n```\n\n"
            "改善後のスキル全文をMarkdownで出力してください。"
            "```markdown と ``` で囲んでください。"
            f"{line_constraint}"
        )

        try:
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    "--model",
                    "sonnet",
                    "--output-format",
                    "text",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                content = self._extract_markdown(result.stdout)
                if content:
                    if not self._check_line_limit(content):
                        lines = content.count("\n") + 1
                        print(
                            f"  行数超過（{lines}/{self._max_lines}行）、元の個体を使用"
                        )
                    else:
                        return Individual(
                            content,
                            generation=generation,
                            parent_ids=[individual.id],
                        )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  突然変異失敗（{type(e).__name__}）、元の個体を使用")

        # フォールバック: 元の個体を返す
        return Individual(
            individual.content,
            generation=generation,
            parent_ids=[individual.id],
        )

    def crossover(
        self, parent1: Individual, parent2: Individual, generation: int
    ) -> Individual:
        """LLM で交叉を生成。行数制限を超える出力は拒否する。"""
        line_constraint = (
            f"\n\n**重要な制約**: 出力は {self._max_lines} 行以内に収めてください。"
        )
        prompt = (
            "以下の2つのClaude Codeスキル定義の良い部分を組み合わせて、"
            "改善版を作成してください。\n\n"
            f"スキルA:\n```markdown\n{parent1.content}\n```\n\n"
            f"スキルB:\n```markdown\n{parent2.content}\n```\n\n"
            "両方の良い点を活かした改善版スキル全文をMarkdownで出力してください。"
            "```markdown と ``` で囲んでください。"
            f"{line_constraint}"
        )

        try:
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    "--model",
                    "sonnet",
                    "--output-format",
                    "text",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                content = self._extract_markdown(result.stdout)
                if content:
                    if not self._check_line_limit(content):
                        lines = content.count("\n") + 1
                        print(
                            f"  交叉結果が行数超過（{lines}/{self._max_lines}行）、親1を使用"
                        )
                    else:
                        return Individual(
                            content,
                            generation=generation,
                            parent_ids=[parent1.id, parent2.id],
                        )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  交叉失敗（{type(e).__name__}）、親1を使用")

        # フォールバック
        return Individual(
            parent1.content,
            generation=generation,
            parent_ids=[parent1.id, parent2.id],
        )

    def evaluate(self, individual: Individual) -> float:
        """適応度関数で個体を評価"""
        if self.dry_run:
            # dry-run: 内容長に基づく簡易スコア
            base = min(len(individual.content) / 5000, 1.0)
            return round(base * 0.5 + 0.3, 2)

        # カスタム適応度関数を試す
        fitness_score = self._run_custom_fitness(individual)
        if fitness_score is not None:
            return fitness_score

        # デフォルト: LLM 評価
        return self._llm_evaluate(individual)

    def _run_custom_fitness(self, individual: Individual) -> Optional[float]:
        """カスタム適応度関数を実行。

        検索順序:
        1. プロジェクトルートの scripts/rl/fitness/{name}.py
        2. Plugin 内の scripts/fitness/{name}.py
        """
        # fitness_func が "default" の場合はスキップ
        if self.fitness_func == "default":
            return None

        # 1. プロジェクト側の適応度関数を優先
        project_root = Path.cwd()
        fitness_path = (
            project_root / "scripts" / "rl" / "fitness" / f"{self.fitness_func}.py"
        )

        # 2. Plugin 内の適応度関数にフォールバック
        if not fitness_path.exists():
            plugin_fitness_path = (
                Path(__file__).parent.parent.parent.parent
                / "scripts"
                / "fitness"
                / f"{self.fitness_func}.py"
            )
            if plugin_fitness_path.exists():
                fitness_path = plugin_fitness_path
            else:
                print(f"  適応度関数が見つかりません: {self.fitness_func}")
                return None

        try:
            result = subprocess.run(
                [sys.executable, str(fitness_path)],
                input=individual.content,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                score = float(result.stdout.strip())
                return max(0.0, min(1.0, score))
            else:
                print(f"  適応度関数エラー: {result.stderr.strip()}")
        except (ValueError, subprocess.TimeoutExpired) as e:
            print(f"  適応度関数実行失敗: {type(e).__name__}")

        return None

    def _llm_evaluate(self, individual: Individual) -> float:
        """LLM でスキル品質を評価"""
        prompt = (
            "以下のClaude Codeスキル定義を0.0〜1.0で評価してください。\n\n"
            "評価基準:\n"
            "- 明確性: 指示が明確で曖昧さがないか (25%)\n"
            "- 完全性: 必要な情報が全て含まれているか (25%)\n"
            "- 構造: 論理的に整理されているか (25%)\n"
            "- 実用性: 実際に使いやすいか (25%)\n\n"
            f"スキル:\n```markdown\n{individual.content}\n```\n\n"
            "数値のみ回答してください（例: 0.75）"
        )

        try:
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    "--model",
                    "haiku",
                    "--output-format",
                    "text",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                # 数値を抽出
                match = re.search(r"(0\.\d+|1\.0|0|1)", result.stdout.strip())
                if match:
                    return float(match.group(1))
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  LLM評価失敗（{type(e).__name__}）、デフォルトスコア使用")

        return 0.5  # フォールバック

    def next_generation(
        self, population: List[Individual], gen_num: int
    ) -> List[Individual]:
        """次世代を生成（エリート選択 + 突然変異 + 交叉）"""
        new_pop: List[Individual] = []

        # エリート: 上位1個体をそのまま次世代へ
        elite = Individual(
            population[0].content,
            generation=gen_num,
            parent_ids=[population[0].id],
        )
        elite.fitness = population[0].fitness
        new_pop.append(elite)

        # 残りは突然変異と交叉で生成
        for i in range(1, self.population_size):
            if i % 2 == 1 and len(population) >= 2:
                # 交叉
                child = self.crossover(population[0], population[1], gen_num)
            else:
                # 突然変異
                parent = population[i % len(population)]
                child = self.mutate(parent, gen_num)
            new_pop.append(child)

        return new_pop

    def save_generation(self, gen: int, population: List[Individual]):
        """世代データを保存"""
        gen_dir = self.run_dir / f"gen_{gen}"
        gen_dir.mkdir(parents=True, exist_ok=True)

        for ind in population:
            ind_file = gen_dir / f"{ind.id}.json"
            ind_file.write_text(
                json.dumps(ind.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def save_result(self, result: Dict[str, Any]):
        """最終結果を保存"""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        result_file = self.run_dir / "result.json"
        result_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _cleanup_old_runs(self):
        """古い世代データを削除し、最新 MAX_KEPT_RUNS 件のみ保持"""
        if not GENERATIONS_DIR.exists():
            return
        run_dirs = sorted(
            [d for d in GENERATIONS_DIR.iterdir() if d.is_dir()],
            key=lambda p: p.name,
        )
        if len(run_dirs) <= MAX_KEPT_RUNS:
            return
        for old_dir in run_dirs[: len(run_dirs) - MAX_KEPT_RUNS]:
            shutil.rmtree(old_dir)
            print(f"  古い世代データを削除: {old_dir.name}")

    @staticmethod
    def _extract_markdown(text: str) -> Optional[str]:
        """```markdown ... ``` ブロックからコンテンツを抽出"""
        # ```markdown ... ``` パターンを優先
        pattern = r"```(?:markdown)?\s*\n(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # マークダウンブロックがない場合はテキスト全体を返す
        stripped = text.strip()
        if stripped:
            return stripped
        return None

    @staticmethod
    def restore(target_path: str):
        """バックアップから復元"""
        target = Path(target_path)
        backup = target.with_suffix(target.suffix + BACKUP_SUFFIX)
        if backup.exists():
            shutil.copy2(backup, target)
            backup.unlink()
            print(f"復元完了: {target}")
        else:
            print(f"バックアップが見つかりません: {backup}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="遺伝的プロンプト最適化")
    parser.add_argument(
        "--target", required=True, help="最適化対象のスキルファイルパス"
    )
    parser.add_argument(
        "--generations", type=int, default=3, help="世代数"
    )
    parser.add_argument(
        "--population", type=int, default=3, help="集団サイズ"
    )
    parser.add_argument(
        "--fitness", default="default", help="適応度関数名"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="構造テスト（LLM呼び出しなし）"
    )
    parser.add_argument(
        "--restore", action="store_true", help="バックアップから復元"
    )

    args = parser.parse_args()

    if args.restore:
        GeneticOptimizer.restore(args.target)
        return

    if not Path(args.target).exists():
        print(f"エラー: ターゲットファイルが見つかりません: {args.target}")
        sys.exit(1)

    optimizer = GeneticOptimizer(
        target_path=args.target,
        generations=args.generations,
        population_size=args.population,
        fitness_func=args.fitness,
        dry_run=args.dry_run,
    )

    result = optimizer.run()

    # サマリー出力
    print(f"\n=== 最適化結果 ===")
    print(f"Run ID: {result['run_id']}")
    print(f"世代数: {result['generations']}")
    print(f"集団サイズ: {result['population_size']}")
    print(f"適応度関数: {result['fitness_func']}")
    print(f"dry-run: {result['dry_run']}")

    if result.get("best_individual"):
        best = result["best_individual"]
        print(f"最良スコア: {best['fitness']}")
        print(f"最良個体ID: {best['id']}")

    for h in result.get("history", []):
        print(
            f"  Gen {h['generation']}: "
            f"best={h['best_fitness']}, "
            f"avg={h['avg_fitness']:.3f}"
        )

    print(f"\n結果保存先: {optimizer.run_dir}")


if __name__ == "__main__":
    main()
