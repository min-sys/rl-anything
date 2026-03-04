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

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

# --- 設定 ---
GENERATIONS_DIR = Path(__file__).parent / "generations"
BACKUP_SUFFIX = ".backup"
MAX_KEPT_RUNS = 5  # generations/ に保持する最大ラン数

# 行数制限は共通モジュールから取得
_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
from line_limit import MAX_RULE_LINES, MAX_SKILL_LINES, check_line_limit


class Individual:
    """最適化対象の個体（スキルのバリエーション）"""

    def __init__(
        self, content: str, generation: int = 0, parent_ids: Optional[List[str]] = None
    ):
        self.content = content
        self.generation = generation
        self.parent_ids = parent_ids or []
        self.fitness: Optional[float] = None
        self.strategy: Optional[str] = None  # "elite", "mutation", "crossover"
        self.cot_reasons: Optional[Dict[str, Any]] = None
        self.id = f"gen{generation}_{datetime.now().strftime('%H%M%S_%f')}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "generation": self.generation,
            "parent_ids": self.parent_ids,
            "fitness": self.fitness,
            "strategy": self.strategy,
            "cot_reasons": self.cot_reasons,
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
        test_tasks: Optional[str] = None,
    ):
        self.target_path = Path(target_path)
        self.generations = generations
        self.population_size = population_size
        self.fitness_func = fitness_func
        self.dry_run = dry_run
        self.test_tasks_path = test_tasks
        self.test_tasks: Optional[List[Dict[str, str]]] = None
        if test_tasks:
            self.test_tasks = self._load_test_tasks(test_tasks)
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
        return check_line_limit(str(self.target_path), content)

    @staticmethod
    def _load_test_tasks(path: str) -> List[Dict[str, str]]:
        """テストタスクYAMLをロード。

        YAML 形式:
            tasks:
              - name: "タスク名"
                prompt: "実行プロンプト"
                expected: "期待される出力の特徴"
        """
        task_path = Path(path)
        if not task_path.exists():
            print(f"  テストタスクファイルが見つかりません: {path}")
            return []

        content = task_path.read_text(encoding="utf-8")

        if yaml is not None:
            data = yaml.safe_load(content)
        else:
            # yaml がない場合は JSON フォールバック
            data = json.loads(content)

        if isinstance(data, dict) and "tasks" in data:
            return data["tasks"]
        return []

    def _execution_evaluate(self, individual: Individual) -> float:
        """テストタスクで候補スキルを実行し、出力品質を評価する2段階パイプライン。

        Stage 1: claude -p にスキルを渡してタスクを実行
        Stage 2: 出力品質を別の claude -p 呼び出しで評価
        """
        if not self.test_tasks:
            print("Warning: no test-tasks configured, execution score defaults to 0.5", file=sys.stderr)
            return 0.5

        scores = []
        for task in self.test_tasks:
            task_name = task.get("name", "unnamed")
            task_prompt = task.get("prompt", "")
            expected = task.get("expected", "")

            # Stage 1: スキルを使ってタスクを実行
            exec_prompt = (
                f"以下のスキル定義に従って、タスクを実行してください。\n\n"
                f"スキル:\n```markdown\n{individual.content}\n```\n\n"
                f"タスク: {task_prompt}"
            )

            try:
                exec_result = subprocess.run(
                    ["claude", "-p", "--output-format", "text"],
                    input=exec_prompt,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if exec_result.returncode != 0:
                    scores.append(0.0)
                    continue

                output = exec_result.stdout.strip()

                # Stage 2: 出力品質を評価
                eval_prompt = (
                    f"以下のタスク出力を0.0〜1.0で評価してください。\n\n"
                    f"タスク: {task_prompt}\n"
                    f"期待される特徴: {expected}\n\n"
                    f"出力:\n```\n{output}\n```\n\n"
                    f"数値のみ回答してください（例: 0.75）"
                )
                eval_result = subprocess.run(
                    ["claude", "-p", "--output-format", "text"],
                    input=eval_prompt,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if eval_result.returncode == 0:
                    match = re.search(
                        r"(0\.\d+|1\.0|0|1)", eval_result.stdout.strip()
                    )
                    if match:
                        scores.append(float(match.group(1)))
                    else:
                        scores.append(0.5)
                else:
                    scores.append(0.5)

            except subprocess.TimeoutExpired:
                print(f"  実行ベース評価タイムアウト: {task_name}")
                scores.append(0.0)
            except FileNotFoundError:
                scores.append(0.0)

        if not scores:
            return 0.5

        return sum(scores) / len(scores)

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

        # history.jsonl にエントリを追記（human_accepted は後で更新）
        self.save_history_entry(result)

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

    def _load_workflow_hints(self) -> str:
        """ワークフロー統計からスキル向けの mutation ヒントを読み込む。

        ~/.claude/rl-anything/workflow_stats.json が存在し、
        対象スキル名のエントリがあればヒントテキストを生成する。
        存在しない場合は空文字を返す（フォールバック）。
        """
        stats_path = Path.home() / ".claude" / "rl-anything" / "workflow_stats.json"
        if not stats_path.exists():
            return ""

        try:
            data = json.loads(stats_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ""

        # hints 付きの場合はそのまま使う
        if "hints" in data and "stats" in data:
            hints = data.get("hints", {})
        else:
            # stats のみの場合
            print("Warning: no workflow hints found in stats-only data", file=sys.stderr)
            return ""

        # ターゲットのスキル名を推定
        target_name = self.target_path.stem
        # SKILL.md の場合は親ディレクトリ名を使う
        if target_name == "SKILL":
            target_name = self.target_path.parent.name

        # スキル名でマッチするヒントを探す
        for key, hint_text in hints.items():
            # "opsx:apply" のようなキーの ":" 以降でもマッチ
            key_parts = key.split(":")
            if target_name in key_parts or key == target_name:
                return hint_text

        return ""

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

        # ワークフロー分析ヒントを読み込む（存在しない場合は空文字）
        workflow_hint = self._load_workflow_hints()
        workflow_section = ""
        if workflow_hint:
            workflow_section = (
                f"\n\nワークフロー分析からの示唆:\n{workflow_hint}\n"
            )

        prompt = (
            f"以下のClaude Code{file_type}定義を改善してください。\n\n"
            "改善方針（ランダムに1-2個選んで適用）:\n"
            "- より具体的な例を追加\n"
            "- 曖昧な指示を明確化\n"
            "- 構造を整理\n"
            "- 不要な冗長性を削除\n"
            "- エッジケースの対処を追加\n\n"
            f"{workflow_section}"
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
                        child = Individual(
                            content,
                            generation=generation,
                            parent_ids=[individual.id],
                        )
                        child.strategy = "mutation"
                        return child
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  突然変異失敗（{type(e).__name__}）、元の個体を使用")

        # フォールバック: 元の個体を返す
        fallback = Individual(
            individual.content,
            generation=generation,
            parent_ids=[individual.id],
        )
        fallback.strategy = "mutation"
        return fallback

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
                        child = Individual(
                            content,
                            generation=generation,
                            parent_ids=[parent1.id, parent2.id],
                        )
                        child.strategy = "crossover"
                        return child
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  交叉失敗（{type(e).__name__}）、親1を使用")

        # フォールバック
        fallback = Individual(
            parent1.content,
            generation=generation,
            parent_ids=[parent1.id, parent2.id],
        )
        fallback.strategy = "crossover"
        return fallback

    # 禁止パターン
    FORBIDDEN_PATTERNS = ["TODO", "FIXME", "HACK", "XXX"]

    def _regression_gate(self, content: str) -> Tuple[bool, Optional[str]]:
        """構造的必要条件のハードゲートチェック。

        Returns:
            (passed, reason) のタプル。passed=False なら reason に不合格理由。
        """
        # 空チェック
        if not content or not content.strip():
            return False, "empty"

        # 行数チェック
        if not self._check_line_limit(content):
            lines = content.count("\n") + 1
            return False, f"line_limit_exceeded({lines}/{self._max_lines})"

        # 禁止パターンチェック
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in content:
                return False, f"forbidden_pattern({pattern})"

        # pitfalls.md からの動的パターンチェック
        pitfall_patterns = self._load_pitfall_patterns()
        for pp in pitfall_patterns:
            if pp in content:
                return False, f"pitfall_pattern({pp})"

        return True, None

    def _load_pitfall_patterns(self) -> List[str]:
        """pitfalls.md からゲート不合格パターンを読み込む。

        gate ソースのパターンのうち、forbidden_pattern(*) の中身を抽出して返す。
        """
        pitfalls_file = self.target_path.parent / "references" / "pitfalls.md"
        if not pitfalls_file.exists():
            return []

        patterns = []
        content = pitfalls_file.read_text(encoding="utf-8")
        for line in content.strip().split("\n"):
            if not line.strip().startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|")]
            # parts: ['', 'Source', 'Pattern', 'Score', '']
            if len(parts) >= 4 and parts[1] == "gate":
                pat = parts[2]
                # forbidden_pattern(X) から X を抽出
                m = re.match(r"forbidden_pattern\((.+)\)", pat)
                if m:
                    patterns.append(m.group(1))
        return patterns

    def evaluate(self, individual: Individual) -> float:
        """適応度関数で個体を評価"""
        if self.dry_run:
            # dry-run: 内容長に基づく簡易スコア
            base = min(len(individual.content) / 5000, 1.0)
            return round(base * 0.5 + 0.3, 2)

        # Regression Gate: 不合格なら即 0.0
        passed, reason = self._regression_gate(individual.content)
        if not passed:
            print(f"  Regression Gate 不合格: {reason}")
            self._record_pitfall(
                str(self.target_path), "gate", reason or "unknown", 0.0
            )
            return 0.0

        # カスタム適応度関数を試す
        fitness_score = self._run_custom_fitness(individual)
        if fitness_score is not None:
            return fitness_score

        # デフォルト: LLM 評価（CoT）
        cot_score, cot = self._llm_evaluate(individual)

        # CoT reason を Individual に保存
        if cot:
            individual.cot_reasons = cot

        # CoT 低スコア基準を pitfalls に記録
        if cot:
            criteria = ["clarity", "completeness", "structure", "practicality"]
            for c in criteria:
                if c in cot and isinstance(cot[c], dict):
                    c_score = cot[c].get("score", 1.0)
                    if c_score < 0.4:
                        reason_text = cot[c].get("reason", "low score")
                        self._record_pitfall(
                            str(self.target_path),
                            "cot",
                            f"{c}: {reason_text}",
                            c_score,
                        )

        # 実行ベース評価（--test-tasks 指定時のみ）
        if self.test_tasks:
            exec_score = self._execution_evaluate(individual)
            # CoT * 0.4 + 実行ベース * 0.6
            return round(cot_score * 0.4 + exec_score * 0.6, 3)

        return cot_score

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

    def _llm_evaluate(self, individual: Individual) -> Tuple[float, Optional[Dict[str, Any]]]:
        """LLM でスキル品質を CoT 付きで評価。

        Returns:
            (total_score, cot_result) のタプル。
            cot_result は各基準の score/reason を含む dict、またはパース失敗時 None。
        """
        prompt = (
            "以下のClaude Codeスキル定義を評価してください。\n\n"
            "各基準について、まず根拠（reason）を述べてから 0.0〜1.0 のスコアを付けてください。\n\n"
            "評価基準:\n"
            "- clarity: 指示が明確で曖昧さがないか (25%)\n"
            "- completeness: 必要な情報が全て含まれているか (25%)\n"
            "- structure: 論理的に整理されているか (25%)\n"
            "- practicality: 実際に使いやすいか (25%)\n\n"
            f"スキル:\n```markdown\n{individual.content}\n```\n\n"
            "以下のJSON形式で回答してください:\n"
            '{"clarity": {"score": 0.8, "reason": "..."}, '
            '"completeness": {"score": 0.7, "reason": "..."}, '
            '"structure": {"score": 0.9, "reason": "..."}, '
            '"practicality": {"score": 0.75, "reason": "..."}, '
            '"total": 0.79}'
        )

        try:
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    "--output-format",
                    "text",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                score, cot = self._parse_cot_response(result.stdout.strip())
                return score, cot
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  LLM評価失敗（{type(e).__name__}）、デフォルトスコア使用")

        return 0.5, None  # フォールバック

    @staticmethod
    def _parse_cot_response(text: str) -> Tuple[float, Optional[Dict[str, Any]]]:
        """CoT JSON レスポンスをパース。

        Returns:
            (total_score, parsed_dict) のタプル。パース失敗時は正規表現フォールバック。
        """
        # JSON ブロックを抽出（```json ... ``` またはそのまま）
        json_match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
        json_str = json_match.group(1).strip() if json_match else text.strip()

        # JSON パース試行
        try:
            data = json.loads(json_str)
            if isinstance(data, dict) and "total" in data:
                total = float(data["total"])
                return max(0.0, min(1.0, total)), data
            # total がない場合、各基準の平均を計算
            if isinstance(data, dict):
                criteria = ["clarity", "completeness", "structure", "practicality"]
                scores = []
                for c in criteria:
                    if c in data and isinstance(data[c], dict) and "score" in data[c]:
                        scores.append(float(data[c]["score"]))
                if scores:
                    total = sum(scores) / len(scores)
                    data["total"] = round(total, 2)
                    return max(0.0, min(1.0, total)), data
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # 正規表現フォールバック: 数値を抽出
        match = re.search(r"(0\.\d+|1\.0|0|1)", json_str)
        if match:
            return float(match.group(1)), None

        print("Warning: CoT response parse failed, score defaults to 0.5", file=sys.stderr)
        return 0.5, None

    def pairwise_compare(self, a: Individual, b: Individual) -> Individual:
        """2つの候補を直接比較し、優れた方を返す。

        位置バイアス緩和のため A/B 入替で2回評価。
        一致しない場合は絶対スコアにフォールバック。
        """
        if self.dry_run:
            # dry-run: 絶対スコアで判定
            return a if (a.fitness or 0) >= (b.fitness or 0) else b

        prompt_template = (
            "以下の2つのClaude Codeスキル定義を比較し、"
            "より優れた方を選んでください。\n\n"
            "スキルA:\n```markdown\n{first}\n```\n\n"
            "スキルB:\n```markdown\n{second}\n```\n\n"
            "回答は 'A' または 'B' の一文字のみで答えてください。"
        )

        try:
            # 1回目: a=A, b=B
            result1 = subprocess.run(
                ["claude", "-p", "--output-format", "text"],
                input=prompt_template.format(first=a.content, second=b.content),
                capture_output=True,
                text=True,
                timeout=60,
            )
            # 2回目: b=A, a=B（入替）
            result2 = subprocess.run(
                ["claude", "-p", "--output-format", "text"],
                input=prompt_template.format(first=b.content, second=a.content),
                capture_output=True,
                text=True,
                timeout=60,
            )

            winner1 = None
            winner2 = None

            if result1.returncode == 0:
                ans = result1.stdout.strip().upper()
                if "A" in ans:
                    winner1 = a
                elif "B" in ans:
                    winner1 = b

            if result2.returncode == 0:
                ans = result2.stdout.strip().upper()
                # 入替しているので逆
                if "A" in ans:
                    winner2 = b
                elif "B" in ans:
                    winner2 = a

            # 2回とも同じ勝者なら確定
            if winner1 is not None and winner1 is winner2:
                return winner1

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  Pairwise比較失敗（{type(e).__name__}）、絶対スコアで判定")

        # フォールバック: 絶対スコアで判定
        return a if (a.fitness or 0) >= (b.fitness or 0) else b

    def next_generation(
        self, population: List[Individual], gen_num: int
    ) -> List[Individual]:
        """次世代を生成（エリート選択 + 突然変異 + 交叉）"""
        new_pop: List[Individual] = []

        # エリート選択: トップ2のスコア差が 0.1 以内なら pairwise で決定
        elite_source = population[0]
        if (
            len(population) >= 2
            and population[0].fitness is not None
            and population[1].fitness is not None
            and abs(population[0].fitness - population[1].fitness) <= 0.1
        ):
            elite_source = self.pairwise_compare(population[0], population[1])

        elite = Individual(
            elite_source.content,
            generation=gen_num,
            parent_ids=[elite_source.id],
        )
        elite.fitness = elite_source.fitness
        elite.strategy = "elite"
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

    # --- History (human_accepted / rejection_reason) ---

    def save_history_entry(self, result: Dict[str, Any],
                           human_accepted: Optional[bool] = None,
                           rejection_reason: Optional[str] = None) -> Path:
        """history.jsonl にエントリを追記する。

        Args:
            result: run() の戻り値
            human_accepted: ユーザーが受理したか (None=未決定)
            rejection_reason: 却下理由 (accept 時は None)

        Returns:
            history.jsonl のパス
        """
        history_file = self.run_dir.parent / "history.jsonl"
        best = result.get("best_individual", {})
        entry = {
            "run_id": result.get("run_id", self.run_id),
            "target": str(self.target_path),
            "timestamp": datetime.now().isoformat(),
            "generations": result.get("generations", self.generations),
            "population_size": result.get("population_size", self.population_size),
            "fitness_func": result.get("fitness_func", self.fitness_func),
            "best_fitness": best.get("fitness"),
            "best_strategy": best.get("strategy"),
            "human_accepted": human_accepted,
            "rejection_reason": rejection_reason,
        }
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return history_file

    @staticmethod
    def record_human_decision(run_dir: str, human_accepted: bool,
                              rejection_reason: Optional[str] = None) -> None:
        """既存の history.jsonl エントリに human decision を記録する。

        直近のエントリを読み取り、human_accepted/rejection_reason を更新して書き戻す。
        """
        run_path = Path(run_dir)
        history_file = run_path.parent / "history.jsonl"
        if not history_file.exists():
            print(f"history.jsonl が見つかりません: {history_file}")
            return

        lines = history_file.read_text(encoding="utf-8").strip().split("\n")
        if not lines:
            return

        # 最後のエントリを更新
        last_entry = json.loads(lines[-1])
        last_entry["human_accepted"] = human_accepted
        last_entry["rejection_reason"] = rejection_reason
        lines[-1] = json.dumps(last_entry, ensure_ascii=False)

        history_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- Pitfall Accumulator ---

    PITFALLS_MAX_ROWS = 50
    PITFALLS_HEADER = "| Source | Pattern | Score |\n|--------|---------|-------|\n"

    @staticmethod
    def _record_pitfall(
        target_path: str, source: str, pattern: str, score: Optional[float] = None
    ):
        """失敗パターンを references/pitfalls.md に記録。

        Args:
            target_path: 対象スキルファイルのパス
            source: 観測ポイント（gate/cot/human）
            pattern: 失敗パターンの説明
            score: スコア（省略可）
        """
        target = Path(target_path)
        refs_dir = target.parent / "references"
        refs_dir.mkdir(parents=True, exist_ok=True)
        pitfalls_file = refs_dir / "pitfalls.md"

        score_str = f"{score:.2f}" if score is not None else "-"
        new_row = f"| {source} | {pattern} | {score_str} |"

        # 既存ファイルを読み込み
        existing_rows: List[str] = []
        if pitfalls_file.exists():
            content = pitfalls_file.read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            # ヘッダー（最初の2行）をスキップしてデータ行を取得
            for line in lines[2:]:
                if line.strip().startswith("|"):
                    existing_rows.append(line.strip())

        # 重複チェック: Pattern 列が一致するものがあればスキップ
        for row in existing_rows:
            parts = [p.strip() for p in row.split("|")]
            # parts: ['', 'Source', 'Pattern', 'Score', '']
            if len(parts) >= 4 and parts[2] == pattern:
                return  # 重複

        existing_rows.append(new_row)

        # FIFO: 上限超過時は古い行を削除
        if len(existing_rows) > GeneticOptimizer.PITFALLS_MAX_ROWS:
            existing_rows = existing_rows[-GeneticOptimizer.PITFALLS_MAX_ROWS:]

        # ファイル書き出し
        output = GeneticOptimizer.PITFALLS_HEADER + "\n".join(existing_rows) + "\n"
        pitfalls_file.write_text(output, encoding="utf-8")


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
    parser.add_argument(
        "--test-tasks", default=None, help="実行ベース評価用テストタスクYAMLファイル"
    )
    parser.add_argument(
        "--accept", action="store_true", help="直近の最適化結果を受理する"
    )
    parser.add_argument(
        "--reject", action="store_true", help="直近の最適化結果を却下する"
    )
    parser.add_argument(
        "--reason", default=None, help="却下理由（--reject 時のオプション）"
    )

    args = parser.parse_args()

    if args.accept or args.reject:
        # human decision の記録
        run_dir = str(GENERATIONS_DIR)
        if GENERATIONS_DIR.exists():
            run_dirs = sorted(
                [d for d in GENERATIONS_DIR.iterdir() if d.is_dir()],
                key=lambda p: p.name,
            )
            if run_dirs:
                run_dir = str(run_dirs[-1])
        GeneticOptimizer.record_human_decision(
            run_dir,
            human_accepted=args.accept,
            rejection_reason=args.reason if args.reject else None,
        )
        status = "受理" if args.accept else "却下"
        print(f"結果を{status}として記録しました")
        if args.reason:
            print(f"理由: {args.reason}")
        return

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
        test_tasks=args.test_tasks,
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
