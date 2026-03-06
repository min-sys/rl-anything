# rl-anything

Claude Code のスキル/ルールを **自律的に観測・発見・淘汰・進化** させ、**遺伝的アルゴリズムで最適化** する Claude Code Plugin。

## クイックスタート

```bash
# マーケットプレイスを登録（初回のみ）
claude plugin marketplace add min-sys/rl-anything

# インストール
claude plugin install rl-anything@rl-anything --scope user

# Claude Code を再起動
```

再起動後、Observe hooks が自動で動き始め、スキル使用・エラー・修正フィードバックを記録する。

```bash
# 環境の健康診断
/rl-anything:audit

# 過去セッションからデータを一括収集
/rl-anything:backfill

# 日次運用（まず dry-run でプレビュー → 確認後に本実行）
/rl-anything:evolve --dry-run
/rl-anything:evolve
```

普段は **`evolve` を日に1回叩くだけ**。データが足りなければ自動でスキップを提案してくれる。

## 全体像 — 3つの柱

rl-anything は **3つの独立した柱** で構成される。

```
┌─────────────────────────────────────────────────────────┐
│  柱1: 自律進化パイプライン                                │
│  Observe(hooks) → Discover → Enrich → Optimize →        │
│  Reorganize → Prune → Reflect → Report                   │
│  → evolve で一括実行                                      │
├─────────────────────────────────────────────────────────┤
│  柱2: 修正フィードバックループ                             │
│  correction_detect(hook) → corrections.jsonl → Reflect   │
├─────────────────────────────────────────────────────────┤
│  柱3: 遺伝的最適化                                       │
│  Generate-Fitness → Optimize → RL-Loop → Evolve-Fitness  │
└─────────────────────────────────────────────────────────┘
```

| 柱 | 何をするか | メインコマンド |
|----|-----------|--------------|
| 自律進化 | 使用データからパターン検出→スキル生成→淘汰→進化 | `/rl-anything:evolve` |
| フィードバック | ユーザーの修正（「いや、違う」等）を検出→ルールに反映 | `/rl-anything:reflect` |
| 遺伝的最適化 | LLM でバリエーション生成→適応度評価→エリート選択 | `/rl-anything:optimize` |

## やりたいこと別ガイド

| やりたいこと | コマンド |
|-------------|---------|
| 日次メンテナンス（プレビュー→本実行） | `evolve --dry-run` → `evolve` |
| 特定スキルをピンポイント改善 | `optimize my-skill` |
| 修正フィードバックをルールに反映 | `reflect` |
| 蓄積されたフィードバックを確認 | `reflect --view` |
| 全 skills/rules の棚卸し | `audit` |
| プロジェクト固有の評価関数を作成 | `generate-fitness --ask` |
| 過去セッションからデータ収集 | `backfill` |
| 評価関数自体を改善 | `evolve-fitness` |

> すべてのコマンドは `/rl-anything:` プレフィックス付きで呼び出す（例: `/rl-anything:evolve`）

## スキル一覧（全13スキル）

| スキル | 柱 | 説明 |
|--------|-----|------|
| `backfill` | 自律進化 | 過去セッション履歴からデータ収集＋分析 |
| `discover` | 自律進化 | 観測データからパターン検出→スキル/ルール候補生成 |
| `prune` | 自律進化 | 未使用・重複アーティファクトの淘汰（merge 統合対応） |
| `evolve` | 自律進化 | 全フェーズ統合実行（日次運用） |
| `audit` | 自律進化 | 全 skills/rules/memory の棚卸し＋健康診断 |
| `reflect` | フィードバック | corrections の修正フィードバックを CLAUDE.md/rules に反映 |
| `optimize` | 遺伝的最適化 | 遺伝的アルゴリズムでスキル/ルールを最適化 |
| `rl-loop` | 遺伝的最適化 | ベースライン→バリエーション→評価→人間確認ループ |
| `generate-fitness` | 遺伝的最適化 | プロジェクト固有の評価関数を自動生成 |
| `evolve-fitness` | 遺伝的最適化 | accept/reject データから評価関数を改善 |
| `feedback` | ユーティリティ | GitHub Issue でフィードバック送信 |
| `update` | ユーティリティ | プラグインを最新版に更新 |
| `version` | ユーティリティ | バージョン・コミットハッシュを表示 |

内部スキル（evolve から自動呼出し）: `enrich`, `reorganize`

## Hooks（データ収集）

7つの hooks が LLM コストゼロでセッションライフサイクル全体をカバーする。

| Hook | イベント | 出力先 |
|------|---------|--------|
| `observe` | PostToolUse | `usage.jsonl`, `errors.jsonl` |
| `correction_detect` | UserPromptSubmit | `corrections.jsonl` |
| `subagent_observe` | SubagentStop | `subagents.jsonl` |
| `workflow_context` | PreToolUse | `$TMPDIR/rl-anything-workflow-*.json` |
| `save_state` | PreCompact | `checkpoint.json` |
| `restore_state` | SessionStart | stdout |
| `session_summary` | Stop | `sessions.jsonl`, `workflows.jsonl` |

---

以下は必要に応じて参照する詳細セクション。

<details>
<summary><strong>各スキルの詳細オプション</strong></summary>

### evolve

```
/rl-anything:evolve --dry-run    # プレビュー（推奨）
/rl-anything:evolve              # 本実行
```

実行フェーズ: Discover → Enrich → Optimize → Reorganize → Prune(+Merge) → Fitness Evolution → Remediation → Reflect → Report

前回以降のセッション数が3未満 or 10観測未満の場合はスキップを推奨。

### discover

```
/rl-anything:discover                    # パターン検出＋候補生成
/rl-anything:discover --scope global     # グローバルスコープで検出
/rl-anything:discover --session-scan     # セッションテキストからも検出
```

検出基準: 行動パターン（5+回）→スキル候補、エラーパターン（3+回）→ルール候補、却下理由（3+回）→ルール候補。組み込み Agent は `agent_usage_summary` に分離。推奨ルール/hook 未導入も検出。

### prune

```
/rl-anything:prune                 # 淘汰候補を検出
/rl-anything:prune --restore       # アーカイブから復元
/rl-anything:prune --list-archive  # アーカイブ一覧
```

各候補に推薦ラベル（archive推奨 / keep推奨 / 要確認）と description を付与。TF-IDF 類似度フィルタで偽陽性を除外。参照型スキルは淘汰対象から除外。

### reflect

```
/rl-anything:reflect                          # 対話レビュー
/rl-anything:reflect --view                   # pending 一覧
/rl-anything:reflect --dry-run                # プレビューのみ
/rl-anything:reflect --apply-all              # 高信頼度を一括適用（>= 0.85）
/rl-anything:reflect --apply-all --min-confidence 0.70  # 閾値変更
/rl-anything:reflect --skip-semantic          # セマンティック検証を無効化
```

### optimize

```
/rl-anything:optimize my-skill                         # 基本（3世代 x 集団3）
/rl-anything:optimize my-skill --dry-run               # 構造テスト
/rl-anything:optimize my-skill --fitness skill_quality  # カスタム適応度関数
/rl-anything:optimize my-skill --generations 5          # 5世代
/rl-anything:optimize my-skill --restore                # バックアップ復元
```

### rl-loop

```
/rl-anything:rl-loop my-skill              # 1ループ
/rl-anything:rl-loop my-skill --loops 3    # 3ループ
/rl-anything:rl-loop my-skill --auto       # 人間確認スキップ
```

### generate-fitness

```
/rl-anything:generate-fitness                # 基本
/rl-anything:generate-fitness --ask          # 品質基準を質問してから生成
/rl-anything:generate-fitness --name bot     # 関数名を指定
```

### audit

```
/rl-anything:audit [project-dir]
/rl-anything:audit --skip-rescore    # 品質計測をスキップ
/rl-anything:audit --memory-context  # MEMORY セマンティック検証用 JSON 出力
```

レポート内容: Skill Quality Trends / MEMORY Health / Plugin Usage / OpenSpec Workflow Analytics / ハードコード値検出

### backfill

```
/rl-anything:backfill              # バックフィル＋分析
/rl-anything:backfill --force      # 既存データを削除して再実行
```

</details>

<details>
<summary><strong>データフロー</strong></summary>

すべてのデータは `~/.claude/rl-anything/` に保存される。

```
~/.claude/rl-anything/
├── usage.jsonl           # スキル/エージェント使用記録
├── errors.jsonl          # エラー記録
├── sessions.jsonl        # セッションサマリ
├── workflows.jsonl       # ワークフローシーケンス
├── subagents.jsonl       # サブエージェント完了データ
├── usage-registry.jsonl  # グローバルスキル使用レジストリ
├── corrections.jsonl     # 修正フィードバック
├── false_positives.jsonl # 偽陽性 corrections（SHA-256 管理）
├── workflow_stats.json   # ワークフロー統計（workflow_analysis.py が出力）
├── checkpoint.json       # 進化状態チェックポイント
├── archive/              # prune でアーカイブされたファイル
└── feedback-drafts/      # ローカル保存フィードバック
```

| ファイル | 書き込み元 | 読み取り先 |
|---------|-----------|-----------|
| `usage.jsonl` | observe hook, backfill | discover, prune, audit |
| `errors.jsonl` | observe hook | discover, audit |
| `sessions.jsonl` | session_summary hook, backfill | audit, evolve, discover |
| `workflows.jsonl` | session_summary hook, backfill | audit, discover |
| `corrections.jsonl` | correction_detect hook, backfill | reflect, discover, evolve, prune |
| `false_positives.jsonl` | reflect | correction_detect |
| `workflow_stats.json` | workflow_analysis.py | optimize, rl-scorer, generate-fitness |
| `checkpoint.json` | save_state hook | restore_state hook |

</details>

<details>
<summary><strong>適応度関数</strong></summary>

### 組み込み

| 関数 | 説明 |
|------|------|
| `default` | LLM による汎用評価（明確性・完全性・構造・実用性） |
| `skill_quality` | ルールベースの構造品質チェック |

### プロジェクト固有（カスタム）

`scripts/rl/fitness/{name}.py` に配置 → `--fitness {name}` で使用。

インターフェース: stdin でスキル内容を受け取り、0.0〜1.0 を stdout に出力。

```python
#!/usr/bin/env python3
import sys

def evaluate(content: str) -> float:
    score = 0.0
    if "必須キーワード" in content:
        score += 0.5
    return score

def main():
    content = sys.stdin.read()
    print(f"{evaluate(content)}")

if __name__ == "__main__":
    main()
```

### 評価関数の育成

accept/reject データが30件以上溜まると `/rl-anything:evolve-fitness` で改善を提案:
- score-acceptance 相関 < 0.50 → 再キャリブレーション推奨
- 同じ rejection_reason が3回以上 → 新軸追加を提案

</details>

<details>
<summary><strong>rl-scorer のドメイン自動判定</strong></summary>

CLAUDE.md からドメインを推定し、評価軸を自動切替。

| ドメイン | 評価軸 |
|----------|--------|
| ゲーム | 没入感・面白さ・バランス・具体性 |
| API/バックエンド | 正確性・堅牢性・保守性・セキュリティ |
| Bot/対話 | パーソナリティ適合・有用性・トーン一貫性 |
| ドキュメント | 正確性・可読性・実行可能性・完全性 |

スコア構成: 技術品質 (40%) + ドメイン品質 (40%) + 構造品質 (20%)

</details>

<details>
<summary><strong>導入ストーリー（Slack Bot プロジェクトの例）</strong></summary>

### 第1幕: Observe — データが貯まる

インストール後、hooks が自動でスキル使用・エラー・修正フィードバックを記録。14個のスキルを運用中、`/bot-create` で personality 設定が抜け落ちる事故が起きていた。

### 第2幕: Discover → Optimize — パターンから改善へ

`/rl-anything:discover` で「`/bot-create` 後に手動で personality を追加している」パターンを検出。ルール候補を自動生成。さらに遺伝的最適化でスキル自体を改善し、スコアが 0.62 → 0.84 に上昇。

### 第3幕: Reflect — フィードバックが活きる

「いや、personality を先に設定して」という修正フィードバックが `/rl-anything:reflect` で CLAUDE.md に自動反映され、同じミスが発生しなくなった。

### 第4幕: 日次運用

| タイミング | やること |
|-----------|---------|
| 新スキル追加時 | `optimize` で1回最適化 → diff レビュー |
| 日次/週次 | `evolve --dry-run` → 確認 → `evolve` |
| 修正が溜まったとき | `reflect` でフィードバック反映 |

</details>

<details>
<summary><strong>claude-reflect からの移行</strong></summary>

```bash
# データ移行（冪等・二重追記防止）
python3 <PLUGIN_DIR>/scripts/migrate_reflect_queue.py

# 確認
/rl-anything:reflect --view

# アンインストール
claude plugin uninstall claude-reflect
```

</details>

## テスト

```bash
python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v
```

## Acknowledgements

correction detection・confidence decay・multi-target routing のアーキテクチャは [claude-reflect](https://github.com/bayramnnakov/claude-reflect)（MIT License, Bayram Annakov）を参考にしています。

## ライセンス

MIT
