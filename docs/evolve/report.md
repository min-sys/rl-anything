# Phase 5: Report（報告）

環境全体の健康状態を1画面で把握できるレポートを出す。

## レポート例

```
rl-anything: Environment Health Report (2026-03-02)
─────────────────────────────────────────────────────
Artifacts:
  Skills: 23 active, 2 unused (>30日), 1 low-score (0.58)
  Rules:  11 active, 1 dead glob, 2 duplicates
  Memory: 180/200 lines (90% capacity)
  CLAUDE.md: 45 lines (healthy)

Observations (since last evolve):
  Sessions: 12
  Skill invocations: 87 (top: commit 23, optimize 15, deploy 12)
  Errors captured: 5
  claude-reflect learnings: 3

Optimization stats (last 30 days):
  Runs: 8
  Approval rate: 75% (6/8)
  Best strategy: mutation (+0.12 avg)
  Top rejection reason: "冗長すぎる" (3回)

Discoveries (3 candidates):
  1. [SKILL] 「PR作成の定型手順」 (7回, confidence 0.85)
  2. [RULE]  「tsc --noEmit を先に実行」 (4回, confidence 0.72)
  3. [RULE]  「冗長な前置きを避ける」 (却下理由から, 4件)

Prune candidates (3):
  1. rules/old-deploy.md — glob matches 0 files
  2. skills/legacy-migrate — 0 invocations (60日)
  3. rules/test-order.md ≈ rules/ci-flow.md (87% similar)

Optimize candidates (1):
  1. skills/bot-create — score 0.58 (threshold 0.70)

Actions: [a]pply all / [r]eview one-by-one / [s]kip
─────────────────────────────────────────────────────
```

## レポートの構成要素

| セクション | データソース |
|-----------|-------------|
| Artifacts | skills/rules/memory の棚卸し（ファイルスキャン） |
| Observations | usage.jsonl / errors.jsonl / sessions.jsonl |
| Optimization stats | history.jsonl + aggregate_runs.py |
| Discoveries | Discover フェーズの出力 |
| Enrich | 既存スキルとの照合・改善提案 |
| Reorganize | TF-IDF クラスタリングによる統合/分割候補 |
| Prune candidates (+Merge) | Prune フェーズの出力（由来ペア統合含む） |
| Reflect | 修正フィードバックの反映状況 |
| Optimize candidates | 全スキル/ルールのスコアスキャン |

## クロスラン集計（aggregate_runs.py）

```bash
python3 skills/audit/scripts/aggregate_runs.py --dir <results_dir>
```

集計項目:

| 項目 | 説明 |
|------|------|
| pitfalls 出現頻度 | 繰り返される失敗パターンのランキング |
| 承認率 | approved / total（人間がどれだけ受け入れたか） |
| 戦略別 fitness 改善幅 | mutation / crossover / elite の有効性比較 |
| 却下理由の傾向 | rejection_reason の頻度ランキング |
| CoT reason の傾向 | 高スコア/低スコアの reason パターン |

## レポート履歴

各 evolve 実行のレポートは `.claude/rl-anything/history/` に日付付きで保存。
推移を確認したい場合に過去のレポートを参照できる。

```
.claude/rl-anything/history/
├── 2026-03-01.json
├── 2026-03-02.json
└── 2026-03-03.json
```
