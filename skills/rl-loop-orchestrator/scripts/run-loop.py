#!/usr/bin/env python3
"""自律進化ループランナー

1ループの流れ:
1. ベースラインスコア取得（rl-scorer）
2. バリエーション生成（genetic-prompt-optimizer）
3. 各バリエーション評価（rl-scorer）
4. 最良バリエーション選択
5. 人間確認（--auto でスキップ可）
6. 承認されたら対象スキルに反映

使用方法:
    python3 run-loop.py --target .claude/skills/narrative-ux-writing/SKILL.md
    python3 run-loop.py --target .claude/skills/narrative-ux-writing/SKILL.md --loops 3 --auto
    python3 run-loop.py --target .claude/skills/narrative-ux-writing/SKILL.md --dry-run
    python3 run-loop.py --target .claude/skills/narrative-ux-writing/SKILL.md --output-dir ./my-output
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


# --- optimize.py から _record_pitfall をインポート ---
_optimizer_scripts = Path(__file__).parent.parent.parent / "genetic-prompt-optimizer" / "scripts"
sys.path.insert(0, str(_optimizer_scripts))
try:
    from optimize import GeneticOptimizer as _GO
    _record_pitfall = _GO._record_pitfall
except ImportError:
    _record_pitfall = None  # type: ignore

# --- パス設定 ---
OPTIMIZER_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "genetic-prompt-optimizer"
    / "scripts"
    / "optimize.py"
)
DEFAULT_OUTPUT_DIR = Path.cwd() / ".rl-loop"
MAX_KEPT_RUNS = 10  # rl-loop 結果の保持数
MAX_SKILL_LINES = 500  # スキル行数上限
MAX_RULE_LINES = 3  # ルール行数上限


def _get_output_dir(output_dir: Optional[str] = None) -> Path:
    """出力ディレクトリを取得"""
    if output_dir:
        return Path(output_dir)
    return DEFAULT_OUTPUT_DIR


def _cleanup_old_runs(output_dir: Path):
    """古いループ結果を削除し、最新 MAX_KEPT_RUNS 件のみ保持"""
    if not output_dir.exists():
        return
    run_dirs = sorted(
        [d for d in output_dir.iterdir() if d.is_dir()],
        key=lambda p: p.name,
    )
    if len(run_dirs) <= MAX_KEPT_RUNS:
        return
    for old_dir in run_dirs[: len(run_dirs) - MAX_KEPT_RUNS]:
        shutil.rmtree(old_dir)
        print(f"  古いループ結果を削除: {old_dir.name}")


def _check_line_limit(target_path: str, content: str) -> bool:
    """行数制限をチェック。超過時は False + 警告"""
    is_rule = ".claude/rules/" in target_path
    max_lines = MAX_RULE_LINES if is_rule else MAX_SKILL_LINES
    lines = content.count("\n") + 1
    if lines > max_lines:
        file_type = "ルール" if is_rule else "スキル"
        print(f"  行数超過: {lines}/{max_lines}行（{file_type}制限）。適用を拒否。")
        return False
    return True


def get_baseline_score(target_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """ベースラインスコアを取得。
    実際の実装では rl-scorer エージェントを呼び出す。
    dry-run 時はダミースコアを返す。
    """
    if dry_run:
        return {
            "target": target_path,
            "integrated_score": 0.65,
            "scores": {
                "technical": {"total": 0.70},
                "domain_quality": {"total": 0.60},
                "structure": {"total": 0.65},
            },
            "summary": "[dry-run] ダミーベースラインスコア",
        }

    # rl-scorer エージェントを claude CLI で呼び出す
    prompt = f"""以下のスキルファイルを rl-scorer の基準で採点してください。
JSON形式で出力してください。

ファイル: {target_path}
"""
    try:
        content = Path(target_path).read_text(encoding="utf-8")
        prompt += f"\n内容:\n```markdown\n{content}\n```"

        result = subprocess.run(
            ["claude", "-p", "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # claude の出力から result フィールドを抽出
            if isinstance(data, dict) and "result" in data:
                return json.loads(data["result"])
            return data
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    # フォールバック
    return {
        "target": target_path,
        "integrated_score": 0.50,
        "summary": "スコア取得に失敗。フォールバック値を使用。",
    }


def generate_variants(
    target_path: str,
    population: int = 3,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """genetic-prompt-optimizer でバリエーションを生成"""
    args = [
        sys.executable,
        str(OPTIMIZER_SCRIPT),
        "--target", target_path,
        "--generations", "1",
        "--population", str(population),
    ]
    if dry_run:
        args.append("--dry-run")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            # optimizer の出力からラン結果を取得
            # generations/ ディレクトリから最新のresult.jsonを読む
            gen_dir = OPTIMIZER_SCRIPT.parent / "generations"
            if gen_dir.exists():
                run_dirs = sorted(gen_dir.iterdir(), reverse=True)
                if run_dirs:
                    result_file = run_dirs[0] / "result.json"
                    if result_file.exists():
                        return json.loads(
                            result_file.read_text(encoding="utf-8")
                        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return {"error": "バリエーション生成に失敗"}


def score_variant(content: str, target_path: str, dry_run: bool = False) -> float:
    """バリエーションをスコアリング"""
    if dry_run:
        # コンテンツ長に基づくダミースコア
        import hashlib
        h = int(hashlib.md5(content.encode()).hexdigest()[:8], 16)
        return round(0.5 + (h % 50) / 100, 2)

    prompt = f"""以下のClaude Codeスキル定義を0.0〜1.0で評価してください。

評価基準:
- 明確性 (25%): 指示が明確で曖昧さがないか
- 完全性 (25%): 必要な情報が全て含まれているか
- 構造 (25%): 論理的に整理されているか
- 実用性 (25%): 実際に使いやすいか

スキル:
```markdown
{content}
```

数値のみ回答してください（例: 0.75）"""

    try:
        import re
        result = subprocess.run(
            ["claude", "-p", "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            match = re.search(r"(0\.\d+|1\.0|0|1)", result.stdout.strip())
            if match:
                return float(match.group(1))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return 0.5


def run_loop(
    target_path: str,
    loops: int = 1,
    population: int = 3,
    auto: bool = False,
    dry_run: bool = False,
    output_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """メインループを実行"""
    results = []
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _get_output_dir(output_dir)
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    history_file = out_dir / "history.jsonl"

    # 古いループ結果をクリーンアップ
    _cleanup_old_runs(out_dir)

    print(f"=== RL 自律進化ループ ===")
    print(f"対象: {target_path}")
    print(f"ループ数: {loops}")
    print(f"集団サイズ: {population}")
    print(f"自動モード: {auto}")
    print(f"dry-run: {dry_run}")
    print(f"出力先: {out_dir}")
    print()

    for loop_num in range(loops):
        print(f"--- ループ {loop_num + 1}/{loops} ---")

        # Step 1: ベースラインスコア
        print("Step 1: ベースラインスコア取得...")
        baseline = get_baseline_score(target_path, dry_run=dry_run)
        baseline_score = baseline.get("integrated_score", 0.5)
        print(f"  ベースライン: {baseline_score}")

        # ベースライン保存
        baseline_file = run_dir / f"loop_{loop_num}_baseline.json"
        baseline_file.write_text(
            json.dumps(baseline, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Step 2: バリエーション生成
        print("Step 2: バリエーション生成...")
        optimizer_result = generate_variants(
            target_path, population=population, dry_run=dry_run
        )

        if "error" in optimizer_result:
            print(f"  エラー: {optimizer_result['error']}")
            continue

        # Step 3: 評価
        print("Step 3: バリエーション評価...")
        variants = []
        history = optimizer_result.get("history", [])
        if history:
            last_gen = history[-1]
            for ind in last_gen.get("individuals", []):
                content = ind.get("content", "")
                score = score_variant(content, target_path, dry_run=dry_run)
                variants.append({
                    "id": ind.get("id", "unknown"),
                    "score": score,
                    "content": content,
                    "content_length": len(content),
                })
                print(f"  {ind.get('id', '?')}: スコア {score}")

        if not variants:
            print("  バリエーションが見つかりません。スキップ。")
            continue

        # 最良バリエーション選択
        best = max(variants, key=lambda v: v["score"])
        print(f"\n  最良: {best['id']} (スコア {best['score']})")
        print(f"  ベースライン: {baseline_score}")
        improvement = best["score"] - baseline_score
        print(f"  改善幅: {improvement:+.2f}")

        # Step 4: 人間確認
        approved = False
        if improvement <= 0:
            print("\n  スコアが改善されていません。スキップ。")
        elif auto:
            print("\n  [自動承認] バリエーションを適用します。")
            approved = True
        elif not dry_run:
            print(f"\n  最良バリエーション（スコア {best['score']}）を適用しますか？")
            print(f"  差分: {len(best['content'])} 文字 (元: {Path(target_path).stat().st_size} バイト)")
            response = input("  適用する? [y/N]: ").strip().lower()
            approved = response in ("y", "yes")
            if not approved and _record_pitfall is not None:
                _record_pitfall(
                    target_path,
                    "human",
                    f"rejected variant {best['id']} (score={best['score']})",
                    best["score"],
                )
        else:
            print("\n  [dry-run] 適用スキップ。")

        # Step 5: 適用と記録
        if approved and not dry_run:
            # 行数制限チェック
            if not _check_line_limit(target_path, best["content"]):
                approved = False
                print("  行数制限超過のため適用を拒否しました。")
            else:
                # バックアップ
                backup_path = Path(target_path).with_suffix(".md.pre-rl-backup")
                if not backup_path.exists():
                    shutil.copy2(target_path, backup_path)

                # 適用
                Path(target_path).write_text(best["content"], encoding="utf-8")
                print(f"  適用完了: {target_path}")

        loop_result = {
            "loop": loop_num,
            "run_id": run_id,
            "target": target_path,
            "baseline_score": baseline_score,
            "best_score": best["score"],
            "improvement": improvement,
            "approved": approved,
            "dry_run": dry_run,
            "timestamp": datetime.now().isoformat(),
            "variants_count": len(variants),
        }
        results.append(loop_result)

        # 履歴に追記
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(loop_result, ensure_ascii=False) + "\n")

    # サマリー
    print(f"\n=== サマリー ===")
    for r in results:
        status = "承認" if r["approved"] else "却下"
        print(
            f"  ループ {r['loop'] + 1}: "
            f"{r['baseline_score']:.2f} → {r['best_score']:.2f} "
            f"({r['improvement']:+.2f}) [{status}]"
        )

    # 結果保存
    result_file = run_dir / "result.json"
    result_file.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n結果保存先: {run_dir}")

    return results


def main():
    parser = argparse.ArgumentParser(description="RL 自律進化ループ")
    parser.add_argument("--target", required=True, help="最適化対象のスキルファイルパス")
    parser.add_argument("--loops", type=int, default=1, help="ループ回数")
    parser.add_argument("--population", type=int, default=3, help="集団サイズ")
    parser.add_argument("--auto", action="store_true", help="自動承認モード")
    parser.add_argument("--dry-run", action="store_true", help="構造テスト")
    parser.add_argument("--output-dir", help="出力ディレクトリ（デフォルト: .rl-loop/）")

    args = parser.parse_args()

    run_loop(
        target_path=args.target,
        loops=args.loops,
        population=args.population,
        auto=args.auto,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
