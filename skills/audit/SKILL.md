---
name: audit
description: |
  Run an environment health check: inventory all skills/rules/memory, check line limits,
  aggregate usage stats, and generate a one-screen report with Scope Advisory.
  Trigger: audit, 健康診断, health check, レポート, report, 棚卸し
---

# /rl-anything:audit — 環境の健康診断

全 skills / rules / memory の棚卸し + 行数チェック + 使用状況集計 + Scope Advisory を含む1画面レポートを出力する。

## Usage

```
/rl-anything:audit [project-dir]
```

## 実行手順

### Step 0.5: Coherence Score / Telemetry Score（オプション）

`--coherence-score` が指定された場合、環境全体の構造的整合性スコアを算出してレポート先頭に表示する:

```bash
python3 <PLUGIN_DIR>/skills/audit/scripts/audit.py "$(pwd)" --coherence-score
```

4軸（Coverage / Consistency / Completeness / Efficiency）の重み付き平均で 0.0〜1.0 のスコアを算出。
0.7 未満の軸には改善アドバイスを表示。

`--telemetry-score` が指定された場合、テレメトリデータから環境の実効性を3軸で測定:

```bash
python3 <PLUGIN_DIR>/skills/audit/scripts/audit.py "$(pwd)" --telemetry-score
```

3軸（Utilization / Effectiveness / Implicit Reward）の重み付き平均で 0.0〜1.0 のスコアを算出。
データ不足時（30セッション未満 or 7日未満）は警告を表示。

`--constitutional-score` が指定された場合、CLAUDE.md/Rules から抽出した原則に対する LLM Judge 評価と Chaos Testing を実行:

```bash
python3 <PLUGIN_DIR>/skills/audit/scripts/audit.py "$(pwd)" --constitutional-score
```

Constitutional Score: 各原則 × 各レイヤーの遵守度を LLM Judge で評価。Coherence Coverage < 0.5 の場合はスキップ。
Chaos Testing: Rules/Skills の仮想除去による堅牢性テスト + SPOF 検出。

複数指定時は Environment Fitness（統合スコア）も表示:

```bash
python3 <PLUGIN_DIR>/skills/audit/scripts/audit.py "$(pwd)" --coherence-score --telemetry-score --constitutional-score
```

### Step 1: Audit スクリプト実行

```bash
python3 <PLUGIN_DIR>/skills/audit/scripts/audit.py "$(pwd)"
```

出力されるレポートをユーザーに表示する。

### Step 1.5: Memory Semantic Verification

MEMORY のセクション内容がコードベースの実態と整合しているかを LLM で検証する。

1. 検証コンテキストを取得:
```bash
python3 <PLUGIN_DIR>/skills/audit/scripts/audit.py "$(pwd)" --memory-context
```

2. 出力 JSON が空（`sections` が空配列）の場合は「検証対象の MEMORY セクションがありません」と表示してスキップ。

3. 各セクションについて、`content` と `codebase_evidence` を突合し3段階で判定:
   - **CONSISTENT**: コードベースと整合。変更不要
   - **MISLEADING**: 正確だが誤解を招く表現がある。書き換え案を提示
   - **STALE**: コードベースと矛盾している。更新/削除を推奨

判定基準チェックリスト:
- [ ] セクションに記載されたツール名・コマンド名はコードベースに存在するか
- [ ] 記載されたファイルパスは実在するか（Step 1 の Stale References と合わせて確認）
- [ ] 記載された動作説明はコードの実装と一致するか
- [ ] 記載が冒頭や目立つ位置にあり、実態と異なる印象を与えないか（MISLEADING 判定）
- [ ] archive_mentions に関連する完了済み change があり、その変更が MEMORY に反映されているか

4. 判定結果をレポートの Memory Health セクション内に「### Semantic Verification」サブセクションとして表示:
   - 全セクションが CONSISTENT → 「全セクション整合」
   - MISLEADING/STALE あり → セクション名・判定・修正提案を表示

### Step 2: クロスラン集計（オプション）

optimize / rl-loop の実行履歴がある場合:

```bash
python3 <PLUGIN_DIR>/skills/audit/scripts/aggregate_runs.py
```

### Step 3: 品質モニタリング（オプション）

高頻度 global/plugin スキルの品質スコアを計測し劣化を検知する:

```bash
python3 <PLUGIN_DIR>/scripts/quality_monitor.py
```

- `--dry-run`: 実際の LLM 評価を行わず対象スキルのみ表示
- audit レポートの "Skill Quality Trends" セクションで品質推移を確認
- `--skip-rescore` を audit.py に渡すと品質計測をスキップ

### Step 4: 意味的類似度の検出（オプション）

行数超過や重複候補が検出された場合、改善アクションを提案する:
- 行数超過 → 分割を提案
- 重複候補 → 統合を提案
- Scope Advisory → スコープ最適化を提案

## allowed-tools

Read, Bash, Glob, Grep

## Tags

audit, health-check, report
