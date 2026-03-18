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
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


# --- optimize.py から _record_pitfall をインポート ---
_optimizer_scripts = Path(__file__).parent.parent.parent / "genetic-prompt-optimizer" / "scripts"
sys.path.insert(0, str(_optimizer_scripts))
try:
    from optimize import DirectPatchOptimizer as _GO
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

# 行数制限は共通モジュールから取得
_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "scripts" / "lib"))
from line_limit import check_line_limit as _check_line_limit
from skill_evolve import assess_single_skill, evolve_skill_proposal, apply_evolve_proposal


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


def get_baseline_score(target_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """ベースラインスコアを3軸並列で取得。
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

    try:
        content = Path(target_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print("Warning: target file not found, defaulting to 0.50", file=sys.stderr)
        return {
            "target": target_path,
            "integrated_score": 0.50,
            "summary": "対象ファイルが見つかりません。フォールバック値を使用。",
        }

    axis_scores = _parallel_score(content)
    return {
        "target": target_path,
        "integrated_score": axis_scores["integrated"],
        "scores": {
            "technical": {"total": axis_scores.get("technical", FALLBACK_SCORE)},
            "domain_quality": {"total": axis_scores.get("domain", FALLBACK_SCORE)},
            "structure": {"total": axis_scores.get("structure", FALLBACK_SCORE)},
        },
        "summary": "3軸並列スコアリング",
    }


def generate_variants(
    target_path: str,
    population: int = 3,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """直接パッチ最適化でバリエーションを生成"""
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


# --- 3軸並列スコアリング ---
AXIS_WEIGHTS = {"technical": 0.40, "domain": 0.40, "structure": 0.20}

_AXIS_PROMPTS = {
    "technical": """以下のClaude Codeスキル定義を技術品質の観点で評価してください。

評価項目（各0.0〜1.0）:
- 明確性: 指示が明確で曖昧さがないか
- 完全性: 必要な情報が全て含まれているか
- 一貫性: 用語・スタイルが統一されているか
- エッジケース: 例外や境界条件への対応があるか
- テスト可能性: 指示の成果を検証できるか

スキル:
```markdown
{content}
```

5項目の平均を total として、数値のみ回答してください（例: 0.75）""",
    "domain": """以下のClaude Codeスキル定義をドメイン品質の観点で評価してください。

評価項目（各0.0〜1.0）:
- 正確性: ドメイン知識が正しいか
- 実用性: 実際のタスクに役立つか
- 保守性: 変更・拡張が容易か
- 完全性: ドメインの重要な側面を網羅しているか

スキル:
```markdown
{content}
```

4項目の平均を total として、数値のみ回答してください（例: 0.75）""",
    "structure": """以下のClaude Codeスキル定義を構造品質の観点で評価してください。

評価項目（各0.0〜1.0）:
- フォーマット: Markdownの構造が適切か
- 長さ: 冗長でなく、かつ不足がないか
- 例示: 具体例が適切に含まれているか
- 参照: 関連リソースへの参照が適切か
- 規約準拠: Claude Code スキルの慣習に沿っているか

スキル:
```markdown
{content}
```

5項目の平均を total として、数値のみ回答してください（例: 0.75）""",
}

FALLBACK_SCORE = 0.5


def _score_single_axis(axis: str, content: str) -> float:
    """単一軸のスコアを claude -p で取得する。失敗時は FALLBACK_SCORE を返す。"""
    prompt = _AXIS_PROMPTS[axis].format(content=content)
    try:
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
    return FALLBACK_SCORE


def _parallel_score(content: str) -> Dict[str, float]:
    """3軸を並列でスコアリングし、各軸スコアと統合スコアを返す。"""
    axis_scores: Dict[str, float] = {}
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(_score_single_axis, axis, content): axis
                for axis in AXIS_WEIGHTS
            }
            for future in as_completed(futures):
                axis = futures[future]
                try:
                    axis_scores[axis] = future.result()
                except Exception:
                    axis_scores[axis] = FALLBACK_SCORE
    except Exception:
        # ThreadPoolExecutor が使えない場合は逐次実行
        for axis in AXIS_WEIGHTS:
            axis_scores[axis] = _score_single_axis(axis, content)

    integrated = sum(
        axis_scores.get(axis, FALLBACK_SCORE) * weight
        for axis, weight in AXIS_WEIGHTS.items()
    )
    axis_scores["integrated"] = round(integrated, 4)
    return axis_scores


def score_variant(content: str, target_path: str, dry_run: bool = False) -> float:
    """バリエーションを3軸並列でスコアリングし、統合スコアを返す。"""
    if dry_run:
        # コンテンツ長に基づくダミースコア
        import hashlib
        h = int(hashlib.md5(content.encode()).hexdigest()[:8], 16)
        return round(0.5 + (h % 50) / 100, 2)

    scores = _parallel_score(content)
    return scores["integrated"]


def _try_evolve_skill(
    target_path: str,
    auto: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Step 5.5: 自己進化パターン組み込みを試行する。

    Returns:
        {"evolve_suitability": str, "evolve_applied": bool, "evolve_scores": dict|None}
    """
    target = Path(target_path)
    skill_dir = target.parent
    skill_name = skill_dir.name

    print("Step 5.5: 自己進化パターン判定...")
    assessment = assess_single_skill(skill_name, skill_dir)
    suitability = assessment.get("suitability", "low")
    scores = assessment.get("scores")

    result: Dict[str, Any] = {
        "evolve_suitability": suitability,
        "evolve_applied": False,
        "evolve_scores": scores,
    }

    if suitability == "already_evolved":
        print("  既に自己進化対応済みです。スキップ。")
        return result

    if suitability in ("low", "rejected"):
        print(f"  適性: {suitability} — {assessment.get('recommendation', '変換非推奨')}")
        return result

    print(f"  適性: {suitability} — {assessment.get('recommendation', '')}")

    if dry_run:
        print("  [dry-run] 自己進化パターン組み込みスキップ。")
        return result

    # 承認フロー
    approved = False
    if auto:
        print("  [自動承認] 自己進化パターンを組み込みます。")
        approved = True
    else:
        response = input("  自己進化パターンを組み込みますか？ [y/N]: ").strip().lower()
        approved = response in ("y", "yes")

    if not approved:
        print("  自己進化パターン組み込みを却下しました。")
        return result

    proposal = evolve_skill_proposal(skill_name, skill_dir)
    if proposal.get("error"):
        print(f"  エラー: {proposal['error']}")
        return result

    apply_result = apply_evolve_proposal(proposal)
    result["evolve_applied"] = apply_result["applied"]
    if apply_result["applied"]:
        print(f"  自己進化パターン組み込み完了。バックアップ: {apply_result['backup_path']}")
    else:
        print(f"  組み込み失敗: {apply_result['error']}")

    return result


def run_loop(
    target_path: str,
    loops: int = 1,
    population: int = 3,
    auto: bool = False,
    dry_run: bool = False,
    output_dir: Optional[str] = None,
    evolve: bool = False,
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
    print(f"バリエーション数: {population}")
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

        if dry_run and variants:
            print("  注意: dry-run モードのスコアは実際の品質を反映しません", file=sys.stderr)

        if not variants:
            print("  バリエーションが見つかりません。スキップ。")
            continue

        # 最良バリエーション選択
        best = max(variants, key=lambda v: v["score"])
        print(f"\n  最良: {best['id']} (スコア {best['score']})")
        print(f"  ベースライン: {baseline_score}")
        improvement = best["score"] - baseline_score
        print(f"  改善幅: {improvement:+.2f}")
        if dry_run:
            print("  注意: dry-run モードのスコアは実際の品質を反映しません", file=sys.stderr)

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

        # Step 5.5: 自己進化パターン組み込み (D4: 最適化後)
        evolve_result: Optional[Dict[str, Any]] = None
        if evolve:
            evolve_result = _try_evolve_skill(target_path, auto=auto, dry_run=dry_run)

        loop_result: Dict[str, Any] = {
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
        if evolve_result:
            loop_result["evolve_suitability"] = evolve_result["evolve_suitability"]
            loop_result["evolve_applied"] = evolve_result["evolve_applied"]
            loop_result["evolve_scores"] = evolve_result["evolve_scores"]
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
    parser.add_argument("--population", type=int, default=3, help="バリエーション数")
    parser.add_argument("--auto", action="store_true", help="自動承認モード")
    parser.add_argument("--dry-run", action="store_true", help="構造テスト")
    parser.add_argument("--output-dir", help="出力ディレクトリ（デフォルト: .rl-loop/）")
    parser.add_argument("--evolve", action="store_true", help="自己進化パターン組み込みを有効化")

    args = parser.parse_args()

    run_loop(
        target_path=args.target,
        loops=args.loops,
        population=args.population,
        auto=args.auto,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        evolve=args.evolve,
    )


if __name__ == "__main__":
    main()
