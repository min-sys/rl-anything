#!/usr/bin/env python3
"""直接パッチプロンプト最適化スクリプト

corrections/sessions からエラーを分類し、LLM 1パスでスキルを直接パッチする。
corrections がない場合は usage 統計・audit 結果をコンテキストに含めた汎用改善。

使用方法:
    python3 optimize.py --target .claude/skills/my-skill/SKILL.md
    python3 optimize.py --target .claude/skills/my-skill/SKILL.md --mode error_guided
    python3 optimize.py --target .claude/skills/my-skill/SKILL.md --dry-run
    python3 optimize.py --restore --target .claude/skills/my-skill/SKILL.md
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
MAX_KEPT_RUNS = 5
MAX_CORRECTIONS_PER_PATCH = 10

# 行数制限は共通モジュールから取得
_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
from line_limit import MAX_RULE_LINES, MAX_SKILL_LINES, check_line_limit
from regression_gate import GateResult, check_gates

# corrections パス
_CORRECTIONS_PATH = Path.home() / ".claude" / "rl-anything" / "corrections.jsonl"

# 廃止オプション
_DEPRECATED_OPTIONS = {
    "--generations": "直接パッチモードでは世代ループは不要です。",
    "--population": "直接パッチモードでは集団サイズは不要です。",
    "--budget": "直接パッチモードではバジェット制御は不要です。",
    "--cascade": "直接パッチモードではモデルカスケードは不要です。",
    "--parallel": "直接パッチモードでは並行最適化は不要です。",
    "--strategy": "直接パッチモードでは --mode を使用してください。",
    "--test-tasks": "直接パッチモードではテストタスクは不要です。",
}


def detect_scope(target_path: Path) -> str:
    """ターゲットスキルの scope を判定する。"""
    resolved = target_path.resolve()
    home = Path.home()
    global_skills_dir = home / ".claude" / "skills"
    if str(resolved).startswith(str(global_skills_dir) + os.sep):
        return "global"
    claude_dir = home / ".claude"
    if str(resolved).startswith(str(claude_dir) + os.sep) and "/skills/" in str(resolved):
        return "global"
    return "project"


class DirectPatchOptimizer:
    """直接パッチ最適化エンジン

    corrections/sessions からエラーを分類し、LLM 1パスでスキルを直接パッチする。
    """

    FORBIDDEN_PATTERNS = ["TODO", "FIXME", "HACK", "XXX"]
    PITFALLS_MAX_ROWS = 50
    PITFALLS_HEADER = "| Source | Pattern | Score |\n|--------|---------|-------|\n"

    def __init__(
        self,
        target_path: str,
        mode: str = "auto",
        fitness_func: str = "default",
        dry_run: bool = False,
    ):
        self.target_path = Path(target_path)
        self.scope = detect_scope(self.target_path)
        self.mode = mode
        self.fitness_func = fitness_func
        self.dry_run = dry_run
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = GENERATIONS_DIR / self.run_id

    @property
    def _is_rule_file(self) -> bool:
        return ".claude/rules/" in str(self.target_path)

    @property
    def _max_lines(self) -> int:
        return MAX_RULE_LINES if self._is_rule_file else MAX_SKILL_LINES

    @property
    def _claude_cwd(self) -> Optional[str]:
        if self.scope == "global":
            return str(Path.home())
        return None

    def _check_line_limit(self, content: str) -> bool:
        return check_line_limit(str(self.target_path), content)

    @property
    def _target_skill_name(self) -> str:
        """対象スキルのスキル名を推定する。"""
        name = self.target_path.stem
        if name == "SKILL":
            name = self.target_path.parent.name
        return name

    # --- Task 1.1: corrections 収集 ---

    def _collect_corrections(self) -> List[Dict[str, Any]]:
        """corrections.jsonl から対象スキル関連の pending レコードを抽出する。

        直近 MAX_CORRECTIONS_PER_PATCH 件に制限。
        """
        if not _CORRECTIONS_PATH.exists():
            return []

        target_name = self._target_skill_name
        corrections = []

        try:
            for line in _CORRECTIONS_PATH.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # applied は除外
                if record.get("reflect_status") == "applied":
                    continue

                # 対象スキルに関連するもの
                last_skill = record.get("last_skill") or ""
                if target_name.lower() in last_skill.lower():
                    corrections.append(record)
        except OSError:
            return []

        # 直近 N 件に制限
        return corrections[-MAX_CORRECTIONS_PER_PATCH:]

    # --- Task 1.2: コンテキスト収集 ---

    def _collect_context(self) -> Dict[str, Any]:
        """workflow_stats, audit collect_issues, pitfalls.md を統合してコンテキスト辞書を返す。"""
        context: Dict[str, Any] = {}

        # workflow_stats.json
        try:
            stats_path = Path.home() / ".claude" / "rl-anything" / "workflow_stats.json"
            if stats_path.exists():
                data = json.loads(stats_path.read_text(encoding="utf-8"))
                workflow_hint = self._extract_workflow_hint(data)
                if workflow_hint:
                    context["workflow_hint"] = workflow_hint
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: workflow_stats 読み込み失敗: {e}", file=sys.stderr)

        # audit collect_issues
        try:
            audit_script = _plugin_root / "skills" / "audit" / "scripts" / "audit.py"
            if audit_script.exists():
                sys.path.insert(0, str(audit_script.parent))
                from audit import collect_issues
                issues = collect_issues(Path.cwd())
                if issues:
                    context["audit_issues"] = issues[:10]  # 上限10件
        except Exception as e:
            print(f"Warning: audit collect_issues 失敗: {e}", file=sys.stderr)

        # pitfalls.md
        try:
            pitfalls_file = self.target_path.parent / "references" / "pitfalls.md"
            if pitfalls_file.exists():
                context["pitfalls"] = pitfalls_file.read_text(encoding="utf-8")
        except OSError as e:
            print(f"Warning: pitfalls.md 読み込み失敗: {e}", file=sys.stderr)

        return context

    def _extract_workflow_hint(self, data: Dict[str, Any]) -> str:
        """workflow_stats.json からスキル向けのヒントを抽出する。"""
        if "hints" not in data or "stats" not in data:
            return ""

        hints = data.get("hints", {})
        target_name = self._target_skill_name

        for key, hint_text in hints.items():
            key_parts = key.split(":")
            if target_name in key_parts or key == target_name:
                return hint_text

        return ""

    # --- Task 2.1, 2.2: プロンプト構築 ---

    def _build_patch_prompt(
        self,
        skill_content: str,
        corrections: List[Dict[str, Any]],
        context: Dict[str, Any],
        strategy: str,
    ) -> str:
        """モードに応じたパッチプロンプトを構築する。"""
        file_type = "ルール" if self._is_rule_file else "スキル"
        line_constraint = (
            f"\n\n**重要な制約**: 出力は {self._max_lines} 行以内に収めてください。"
            f"{'ルールは3行以内が原則です。' if self._is_rule_file else '冗長な説明を避け、簡潔に保ってください。'}"
        )

        # 共通ヘッダー
        prompt_parts = [
            f"以下のClaude Code{file_type}定義を改善してください。\n",
            f"元の{file_type}:\n```markdown\n{skill_content}\n```\n",
        ]

        if strategy == "error_guided":
            # error_guided: corrections ベース
            prompt_parts.append("## 修正すべき問題点\n")
            prompt_parts.append("以下のユーザー修正フィードバックに基づいて、スキルを改善してください:\n")
            for i, corr in enumerate(corrections, 1):
                msg = corr.get("message", "")
                ctype = corr.get("correction_type", "unknown")
                learning = corr.get("extracted_learning", "")
                prompt_parts.append(f"\n### 修正 {i} (type: {ctype})")
                if msg:
                    prompt_parts.append(f"メッセージ: {msg}")
                if learning:
                    prompt_parts.append(f"学習: {learning}")
            prompt_parts.append("\n上記のフィードバックを反映し、同じ問題が再発しないようにスキルを修正してください。\n")
        else:
            # llm_improve: 汎用改善
            prompt_parts.append("## 改善方針\n")
            prompt_parts.append(
                "以下の情報を参考に、スキルの品質を向上させてください:\n"
                "- より具体的な例を追加\n"
                "- 曖昧な指示を明確化\n"
                "- 構造を整理\n"
                "- 不要な冗長性を削除\n"
                "- エッジケースの対処を追加\n"
            )

        # コンテキスト情報を追加
        if context.get("workflow_hint"):
            prompt_parts.append(f"\n## ワークフロー分析からの示唆\n{context['workflow_hint']}\n")

        if context.get("audit_issues"):
            prompt_parts.append("\n## 検出された構造的問題\n")
            for issue in context["audit_issues"]:
                prompt_parts.append(f"- [{issue.get('type', '')}] {issue.get('file', '')}: {issue.get('detail', '')}")
            prompt_parts.append("")

        if context.get("pitfalls"):
            prompt_parts.append(f"\n## 過去の失敗パターン\n{context['pitfalls']}\n")

        prompt_parts.append(
            f"改善後の{file_type}全文をMarkdownで出力してください。"
            "```markdown と ``` で囲んでください。"
            f"{line_constraint}"
        )

        return "\n".join(prompt_parts)

    # --- Task 3.1: コア実行 ---

    def run(self) -> Dict[str, Any]:
        """直接パッチ最適化を実行する。"""
        # scope 通知
        if self.scope == "global":
            print("ℹ️ 汎用評価モードで最適化します（プロジェクト固有のコンテキストは使用しません）")

        # クリーンアップ
        self._cleanup_old_runs()

        # バックアップ
        self.backup_original()

        # 元のスキル読み込み
        original_content = self.target_path.read_text(encoding="utf-8")
        self.original_content = original_content

        # コンテキスト収集
        corrections = self._collect_corrections()
        context = self._collect_context()

        # 戦略決定
        strategy = self._determine_strategy(corrections)
        print(f"Mode: {strategy} (corrections: {len(corrections)}件)")

        if self.dry_run:
            # dry-run: LLM コールなし
            result = {
                "run_id": self.run_id,
                "target": str(self.target_path),
                "strategy": strategy,
                "corrections_used": len(corrections),
                "dry_run": True,
                "fitness_func": self.fitness_func,
                "best_individual": {
                    "content": original_content,
                    "content_length": len(original_content),
                    "fitness": None,
                    "strategy": strategy,
                },
            }
            self.save_result(result)
            self.save_history_entry(result)
            return result

        # プロンプト構築
        prompt = self._build_patch_prompt(original_content, corrections, context, strategy)

        # LLM コール
        patched_content, error = self._call_llm(prompt)

        if error:
            print(f"LLM コール失敗: {error}。元のスキルを維持します。")
            result = {
                "run_id": self.run_id,
                "target": str(self.target_path),
                "strategy": strategy,
                "corrections_used": len(corrections),
                "dry_run": False,
                "fitness_func": self.fitness_func,
                "error": error,
                "best_individual": {
                    "content": original_content,
                    "content_length": len(original_content),
                    "fitness": None,
                    "strategy": strategy,
                },
            }
            self.save_result(result)
            self.save_history_entry(result)
            return result

        # regression gate
        passed, gate_reason = self._regression_gate(patched_content)
        if not passed:
            reason_msg = self._format_gate_reason(gate_reason)
            print(f"品質ゲート不合格: {reason_msg}")
            self._record_pitfall(str(self.target_path), "gate", gate_reason or "unknown", 0.0)
            result = {
                "run_id": self.run_id,
                "target": str(self.target_path),
                "strategy": strategy,
                "corrections_used": len(corrections),
                "dry_run": False,
                "fitness_func": self.fitness_func,
                "gate_rejected": True,
                "gate_reason": gate_reason,
                "best_individual": {
                    "content": original_content,
                    "content_length": len(original_content),
                    "fitness": None,
                    "strategy": strategy,
                },
            }
            self.save_result(result)
            self.save_history_entry(result)
            return result

        # パッチ適用（ファイル書き込み）
        self.target_path.write_text(patched_content, encoding="utf-8")

        # fitness score（参考表示用）
        ref_score = self._run_custom_fitness(patched_content)

        result = {
            "run_id": self.run_id,
            "target": str(self.target_path),
            "strategy": strategy,
            "corrections_used": len(corrections),
            "dry_run": False,
            "fitness_func": self.fitness_func,
            "best_individual": {
                "content": patched_content,
                "content_length": len(patched_content),
                "fitness": ref_score,
                "strategy": strategy,
            },
        }

        self.save_result(result)
        self.save_history_entry(result)
        return result

    def _determine_strategy(self, corrections: List[Dict[str, Any]]) -> str:
        """corrections 有無とモード指定から戦略を決定する。"""
        if self.mode == "auto":
            return "error_guided" if corrections else "llm_improve"
        if self.mode == "error_guided":
            if not corrections:
                print("対象スキルの corrections が見つかりません。llm_improve モードにフォールバックします。")
                return "llm_improve"
            return "error_guided"
        return "llm_improve"

    def _call_llm(self, prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """claude -p を1回呼び出し、パッチ結果を返す。

        Returns:
            (patched_content, error) のタプル。成功時は error=None。
        """
        try:
            run_kwargs: Dict[str, Any] = dict(
                input=prompt,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if self._claude_cwd:
                run_kwargs["cwd"] = self._claude_cwd
            result = subprocess.run(
                ["claude", "-p", "--output-format", "text"],
                **run_kwargs,
            )
            if result.returncode != 0:
                return None, f"claude -p がエラーコード {result.returncode} で終了"

            content = self._extract_markdown(result.stdout)
            if not content:
                return None, "LLM レスポンスからコンテンツを抽出できませんでした"

            return content, None

        except subprocess.TimeoutExpired:
            return None, "LLM コールがタイムアウトしました（180秒）"
        except FileNotFoundError:
            return None, "claude CLI が見つかりません"

    @staticmethod
    def _format_gate_reason(reason: Optional[str]) -> str:
        """ゲート不合格理由をユーザー向けメッセージに変換する。"""
        if not reason:
            return "不明な理由"
        if reason == "empty":
            return "パッチ内容が空です"
        if reason.startswith("line_limit_exceeded"):
            return f"行数制限超過（{reason}）"
        if reason.startswith("forbidden_pattern"):
            return f"禁止パターン検出（{reason}）"
        if reason.startswith("pitfall_pattern"):
            return f"既知の失敗パターン検出（{reason}）"
        if reason == "frontmatter_lost":
            return "YAML frontmatter が消失しました"
        return reason

    # --- Regression Gate ---

    def _regression_gate(self, content: str) -> Tuple[bool, Optional[str]]:
        """構造的必要条件のハードゲートチェック。共通ライブラリに委譲。"""
        pitfalls_file = self.target_path.parent / "references" / "pitfalls.md"
        pitfall_path = str(pitfalls_file) if pitfalls_file.exists() else None

        original = getattr(self, "original_content", None)
        result = check_gates(
            candidate=content,
            original=original,
            max_lines=self._max_lines,
            pitfall_patterns_path=pitfall_path,
        )
        if result.passed:
            return True, None
        # 既存の reason フォーマットとの互換性を維持
        reason = result.reason
        if reason == "empty_content":
            reason = "empty"
        return False, reason

    def _load_pitfall_patterns(self) -> List[str]:
        """pitfalls.md からゲート不合格パターンを読み込む。"""
        pitfalls_file = self.target_path.parent / "references" / "pitfalls.md"
        if not pitfalls_file.exists():
            return []

        patterns = []
        content = pitfalls_file.read_text(encoding="utf-8")
        for line in content.strip().split("\n"):
            if not line.strip().startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4 and parts[1] == "gate":
                m = re.match(r"forbidden_pattern\((.+)\)", parts[2])
                if m:
                    patterns.append(m.group(1))
        return patterns

    # --- Fitness (参考表示用) ---

    def _run_custom_fitness(self, content: str) -> Optional[float]:
        """カスタム適応度関数を実行（参考スコア表示用）。"""
        if self.fitness_func == "default":
            return None

        project_root = Path.cwd()
        fitness_path = project_root / "scripts" / "rl" / "fitness" / f"{self.fitness_func}.py"

        if not fitness_path.exists():
            plugin_fitness_path = (
                _plugin_root / "scripts" / "fitness" / f"{self.fitness_func}.py"
            )
            if plugin_fitness_path.exists():
                fitness_path = plugin_fitness_path
            else:
                print(f"  適応度関数が見つかりません: {self.fitness_func}")
                return None

        try:
            result = subprocess.run(
                [sys.executable, str(fitness_path)],
                input=content,
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

    # --- バックアップ/復元 ---

    def backup_original(self):
        """元のスキルをバックアップ"""
        backup_path = self.target_path.with_suffix(
            self.target_path.suffix + BACKUP_SUFFIX
        )
        if not backup_path.exists():
            shutil.copy2(self.target_path, backup_path)
            print(f"バックアップ作成: {backup_path}")

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

    # --- 結果保存 ---

    def save_result(self, result: Dict[str, Any]):
        """最終結果を保存"""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        result_file = self.run_dir / "result.json"
        result_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _cleanup_old_runs(self):
        """古いランデータを削除し、最新 MAX_KEPT_RUNS 件のみ保持"""
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
            print(f"  古いランデータを削除: {old_dir.name}")

    @staticmethod
    def _extract_markdown(text: str) -> Optional[str]:
        """```markdown ... ``` ブロックからコンテンツを抽出。

        複数ブロックがある場合は最長のものを返す。
        """
        pattern = r"```(?:markdown)?\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            longest = max(matches, key=len).strip()
            if longest:
                return longest
        stripped = text.strip()
        if stripped:
            return stripped
        return None

    # --- History ---

    def save_history_entry(self, result: Dict[str, Any],
                           human_accepted: Optional[bool] = None,
                           rejection_reason: Optional[str] = None) -> Path:
        """history.jsonl にエントリを追記する。"""
        history_file = self.run_dir.parent / "history.jsonl"
        best = result.get("best_individual", {})
        entry = {
            "run_id": result.get("run_id", self.run_id),
            "target": str(self.target_path),
            "timestamp": datetime.now().isoformat(),
            "strategy": result.get("strategy", "auto"),
            "corrections_used": result.get("corrections_used", 0),
            "fitness_func": result.get("fitness_func", self.fitness_func),
            "best_fitness": best.get("fitness"),
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
        """既存の history.jsonl エントリに human decision を記録する。"""
        run_path = Path(run_dir)
        history_file = run_path.parent / "history.jsonl"
        if not history_file.exists():
            print(f"history.jsonl が見つかりません: {history_file}")
            return

        lines = history_file.read_text(encoding="utf-8").strip().split("\n")
        if not lines:
            return

        last_entry = json.loads(lines[-1])
        last_entry["human_accepted"] = human_accepted
        last_entry["rejection_reason"] = rejection_reason
        lines[-1] = json.dumps(last_entry, ensure_ascii=False)

        history_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- Pitfall Accumulator ---

    @staticmethod
    def _record_pitfall(
        target_path: str, source: str, pattern: str, score: Optional[float] = None
    ):
        """失敗パターンを references/pitfalls.md に記録。"""
        target = Path(target_path)
        refs_dir = target.parent / "references"
        refs_dir.mkdir(parents=True, exist_ok=True)
        pitfalls_file = refs_dir / "pitfalls.md"

        score_str = f"{score:.2f}" if score is not None else "-"
        new_row = f"| {source} | {pattern} | {score_str} |"

        existing_rows: List[str] = []
        if pitfalls_file.exists():
            content = pitfalls_file.read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            for line in lines[2:]:
                if line.strip().startswith("|"):
                    existing_rows.append(line.strip())

        for row in existing_rows:
            parts = [p.strip() for p in row.split("|")]
            if len(parts) >= 4 and parts[2] == pattern:
                return  # 重複

        existing_rows.append(new_row)

        if len(existing_rows) > DirectPatchOptimizer.PITFALLS_MAX_ROWS:
            existing_rows = existing_rows[-DirectPatchOptimizer.PITFALLS_MAX_ROWS:]

        output = DirectPatchOptimizer.PITFALLS_HEADER + "\n".join(existing_rows) + "\n"
        pitfalls_file.write_text(output, encoding="utf-8")


def _check_deprecated_options(argv: List[str]) -> Optional[str]:
    """廃止オプションが使われていないかチェック。使われていたらエラーメッセージを返す。"""
    for arg in argv:
        for dep_opt, msg in _DEPRECATED_OPTIONS.items():
            if arg == dep_opt or arg.startswith(dep_opt + "="):
                return f"{dep_opt} は廃止されました。{msg}"
    return None


def main():
    # 廃止オプションチェック
    dep_error = _check_deprecated_options(sys.argv[1:])
    if dep_error:
        print(f"エラー: {dep_error}", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="直接パッチプロンプト最適化")
    parser.add_argument(
        "--target", required=True, help="最適化対象のスキルファイルパス"
    )
    parser.add_argument(
        "--mode", default="auto", choices=["auto", "error_guided", "llm_improve"],
        help="最適化モード（auto: corrections有無で自動判定）"
    )
    parser.add_argument(
        "--fitness", default="default", help="適応度関数名（参考スコア表示用）"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="構造テスト（LLM呼び出しなし）"
    )
    parser.add_argument(
        "--restore", action="store_true", help="バックアップから復元"
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
        run_dir = str(GENERATIONS_DIR)
        if GENERATIONS_DIR.exists():
            run_dirs = sorted(
                [d for d in GENERATIONS_DIR.iterdir() if d.is_dir()],
                key=lambda p: p.name,
            )
            if run_dirs:
                run_dir = str(run_dirs[-1])
        DirectPatchOptimizer.record_human_decision(
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
        DirectPatchOptimizer.restore(args.target)
        return

    if not Path(args.target).exists():
        print(f"エラー: ターゲットファイルが見つかりません: {args.target}")
        sys.exit(1)

    optimizer = DirectPatchOptimizer(
        target_path=args.target,
        mode=args.mode,
        fitness_func=args.fitness,
        dry_run=args.dry_run,
    )

    result = optimizer.run()

    # サマリー出力
    print(f"\n=== 最適化結果 ===")
    print(f"Run ID: {result['run_id']}")
    print(f"モード: {result['strategy']}")
    print(f"corrections使用: {result['corrections_used']}件")
    print(f"dry-run: {result['dry_run']}")

    if result.get("error"):
        print(f"エラー: {result['error']}")

    if result.get("gate_rejected"):
        print(f"品質ゲート不合格: {result.get('gate_reason', '不明')}")

    if result.get("best_individual"):
        best = result["best_individual"]
        if best.get("fitness") is not None:
            print(f"参考スコア: {best['fitness']}")

    print(f"\n結果保存先: {optimizer.run_dir}")


if __name__ == "__main__":
    main()
