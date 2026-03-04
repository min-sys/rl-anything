# rl-anything

Claude Code のスキル/ルールを **自律的に観測・発見・淘汰・進化** させ、**遺伝的アルゴリズムで最適化** する Claude Code Plugin。

## 目次

- [クイックスタート](#クイックスタート)
- [3つの柱](#3つの柱)
  - [柱1: 自律進化パイプライン](#柱1-自律進化パイプライン-observe--discover--prune--evolve)
  - [柱2: 修正フィードバックループ](#柱2-修正フィードバックループ-correction--reflect)
  - [柱3: 遺伝的最適化](#柱3-遺伝的最適化-optimize--rl-loop)
- [データフロー](#データフロー)
- [スキル一覧](#スキル一覧)
  - [自律進化パイプライン](#自律進化パイプライン)
  - [修正フィードバックループ](#修正フィードバックループ)
  - [遺伝的最適化](#遺伝的最適化)
  - [ユーティリティ](#ユーティリティ)
- [Hooks とデータ収集](#hooks-とデータ収集)
- [導入ストーリー](#導入ストーリー)
- [適応度関数](#適応度関数)
- [rl-scorer のドメイン自動判定](#rl-scorer-のドメイン自動判定)
- [向いているプロジェクト](#向いているプロジェクト)
- [Before / After](#before--after)
- [テスト](#テスト)
- [claude-reflect からの移行](#claude-reflect-からの移行)
- [Acknowledgements](#acknowledgements)
- [ライセンス](#ライセンス)

## クイックスタート

### インストール

```bash
# マーケットプレイスを登録（初回のみ）
claude plugin marketplace add shohu/rl-anything

# インストール
claude plugin install rl-anything@rl-anything --scope user

# Claude Code を再起動
```

再起動後、Observe hooks が自動で動き始め、スキル使用・エラー・修正フィードバックを記録する。

### 初回セットアップ

```bash
# 環境の健康診断
/rl-anything:audit

# 過去セッションからデータを一括収集
/rl-anything:backfill
```

### 日次運用

```bash
# 全フェーズ一括実行: Discover → Enrich → Optimize → Prune → Reflect → Report
/rl-anything:evolve
```

普段は **`evolve` を日に1回叩くだけ**。データが足りなければ自動でスキップを提案してくれる。

### やりたいこと別ガイド

| やりたいこと | コマンド |
|-------------|---------|
| 日次/週次メンテナンス | `/rl-anything:evolve` |
| 特定スキルをピンポイント改善 | `/rl-anything:optimize my-skill` |
| 修正フィードバックを CLAUDE.md に反映 | `/rl-anything:reflect` |
| 蓄積されたフィードバックを確認 | `/rl-anything:reflect --view` |
| 全 skills/rules の棚卸し | `/rl-anything:audit` |
| プロジェクト固有の評価関数を作成 | `/rl-anything:generate-fitness --ask` |

## 3つの柱

rl-anything は **3つの独立した柱** で構成される。

### 柱1: 自律進化パイプライン (Observe → Discover → Evolve)

日々の Claude Code 使用データを **自動観測** し、繰り返しパターンからスキル/ルール候補を **発見**、不要なものを **淘汰** し、全体を **進化** させる。

```
Observe (hooks)       使用・エラー・ワークフローを自動記録（LLM コストゼロ）
    ↓
Backfill             過去セッションからデータを一括収集
    ↓
Discover             パターン検出 → スキル/ルール候補を生成
    ↓
Enrich               既存スキルと照合 → 改善提案を生成
    ↓
Optimize             遺伝的アルゴリズムでスキルを最適化
    ↓
Reorganize           TF-IDF クラスタリングで統合/分割候補を提案
    ↓
Prune (+Merge)       未使用・重複アーティファクトをアーカイブ
    ↓
Fitness Evolution    評価関数自体の改善を提案
    ↓
Reflect              修正フィードバックを CLAUDE.md/rules に反映
    ↓
Report               結果レポートを出力
    ↓
Evolve               上記を一括実行（日次運用）
```

### 柱2: 修正フィードバックループ (Correction → Reflect)

ユーザーの修正フィードバック（「いや、違う」「don't do that」等）を **リアルタイム検出** し、蓄積されたフィードバックを CLAUDE.md やルールに **反映** する。

```
correction_detect (hook)   「いや」「no,」「don't」等の修正パターンを検出
    ↓
corrections.jsonl          信頼度・感情・パターン種別と共に記録
    ↓
Reflect                    pending corrections を対話レビュー → CLAUDE.md/rules に反映
```

**特徴**: 26種のパターン（CJK 3 + Explicit 1 + Positive 3 + Correction 8 + Guardrail 8 + Weak 3）を検出。偽陽性フィルタ付き。セマンティック検証（LLM）でノイズを除去。

### 柱3: 遺伝的最適化 (Optimize → RL-Loop)

個別のスキル/ルールを **遺伝的アルゴリズム** で改善する。LLM でバリエーションを生成し、適応度関数で評価、エリート選択で次世代を生成する。

```
Generate-Fitness     プロジェクト固有の評価関数を自動生成
    ↓
Optimize             LLM でバリエーション生成 → 適応度評価 → 進化
    ↓
RL-Loop              ベースライン → バリエーション → 評価 → 人間確認のサイクル
    ↓
Evolve-Fitness       accept/reject データから評価関数自体を改善
```

## データフロー

すべてのデータは `~/.claude/rl-anything/` に保存される。

```
~/.claude/rl-anything/
├── usage.jsonl           # スキル/エージェント使用記録
├── errors.jsonl          # エラー記録
├── sessions.jsonl        # セッションサマリ
├── workflows.jsonl       # ワークフローシーケンス（Skill→Agent の構造）
├── subagents.jsonl       # サブエージェント完了データ
├── usage-registry.jsonl  # グローバルスキル使用レジストリ
├── workflow_stats.json   # ワークフロー統計（workflow_analysis.py が出力）
├── corrections.jsonl     # 修正フィードバック（correction_detect + backfill + reflect）
├── checkpoint.json       # 進化状態チェックポイント
├── archive/              # prune でアーカイブされたファイル
└── feedback-drafts/      # ローカル保存フィードバック
```

| ファイル | 書き込み元 | 読み取り先 |
|---------|-----------|-----------|
| `usage.jsonl` | observe hook, backfill | discover, prune, audit, session_summary |
| `errors.jsonl` | observe hook | discover, audit, session_summary |
| `sessions.jsonl` | session_summary hook, backfill | audit, evolve |
| `workflows.jsonl` | session_summary hook, backfill | audit, discover |
| `subagents.jsonl` | subagent_observe hook | audit |
| `usage-registry.jsonl` | observe hook | prune（cross-PJ 判定） |
| `workflow_stats.json` | workflow_analysis.py | optimize, rl-scorer, generate-fitness |
| `corrections.jsonl` | correction_detect hook, backfill | reflect, discover, evolve, prune |
| `checkpoint.json` | save_state hook | restore_state hook |

## スキル一覧

全14スキル。`/rl-anything:<name>` で呼び出す。

| スキル | 柱 | 説明 |
|--------|-----|------|
| `backfill` | 自律進化 | 過去セッション履歴からデータ収集＋分析 |
| `discover` | 自律進化 | 観測データからパターン検出 → スキル/ルール候補生成 |
| `prune` | 自律進化 | 未使用・重複アーティファクトの淘汰 |
| `evolve` | 自律進化 | 全フェーズ統合（Discover→Enrich→Optimize→Prune→Reflect→Report） |
| `audit` | 自律進化 | 全 skills/rules/memory の棚卸し＋健康診断 |
| `reflect` | フィードバック | corrections.jsonl の修正フィードバックを CLAUDE.md/rules に反映 |
| `optimize` | 遺伝的最適化 | 遺伝的アルゴリズムでスキル/ルールを最適化 |
| `rl-loop` | 遺伝的最適化 | ベースライン→バリエーション→評価→人間確認ループ |
| `generate-fitness` | 遺伝的最適化 | プロジェクト固有の評価関数を自動生成 |
| `evolve-fitness` | 遺伝的最適化 | accept/reject データから評価関数を改善 |
| `feedback` | ユーティリティ | GitHub Issue でフィードバック送信 |
| `update` | ユーティリティ | プラグインを最新版に更新 |
| `version` | ユーティリティ | バージョン・コミットハッシュを表示 |

### 自律進化パイプライン

#### `/rl-anything:backfill`

過去の Claude Code セッションから使用データを一括収集し、分析レポートを出力する。

```
/rl-anything:backfill              # バックフィル＋分析
/rl-anything:backfill --force      # 既存データを削除して再実行
```

出力: `usage.jsonl`, `workflows.jsonl`, `sessions.jsonl`

#### `/rl-anything:discover`

観測データ（usage.jsonl, errors.jsonl）から繰り返しパターンを検出し、スキル/ルール候補を生成する。

```
/rl-anything:discover                    # パターン検出＋候補生成
/rl-anything:discover --scope global     # グローバルスコープで検出
/rl-anything:discover --session-scan     # セッションテキストからもパターン検出
```

- 行動パターン（5+回）→ スキル候補
- エラーパターン（3+回）→ ルール候補（予防策）
- 却下理由パターン（3+回）→ ルール候補（品質基準）

#### `/rl-anything:prune`

未使用・重複アーティファクトを検出し、人間承認のうえアーカイブする。直接削除は行わない。

```
/rl-anything:prune                 # 淘汰候補を検出
/rl-anything:prune --restore       # アーカイブから復元
/rl-anything:prune --list-archive  # アーカイブ一覧
```

検出基準: Dead Glob / Zero Invocation（30日） / 重複候補

#### `/rl-anything:evolve`

全フェーズをワンコマンドで実行する。日次運用を想定。

```
/rl-anything:evolve              # 通常実行
/rl-anything:evolve --dry-run    # レポートのみ、変更なし
```

実行フェーズ: Discover → Enrich → Optimize → Reorganize → Prune(+Merge) → Fitness Evolution → **Reflect** → Report

前回以降のセッション数が3未満、または10観測未満の場合はスキップを推奨。Reflect フェーズでは pending corrections が 5件以上 or 前回から7日超の場合に `/rl-anything:reflect` を提案する。

#### `/rl-anything:audit`

全 skills / rules / memory の棚卸し + 行数チェック + 使用状況集計 + Scope Advisory を含む1画面レポート。

```
/rl-anything:audit [project-dir]
```

### 修正フィードバックループ

#### `/rl-anything:reflect`

corrections.jsonl に蓄積された修正フィードバックを CLAUDE.md やルールに反映する。

```
/rl-anything:reflect                          # 対話レビューで1件ずつ確認
/rl-anything:reflect --view                   # pending 一覧を表示
/rl-anything:reflect --dry-run                # プレビューのみ（書込なし）
/rl-anything:reflect --skip-all               # pending を全件スキップ
/rl-anything:reflect --apply-all              # 高信頼度を一括適用（デフォルト >= 0.85）
/rl-anything:reflect --apply-all --min-confidence 0.70  # 閾値を変更
/rl-anything:reflect --skip-semantic          # セマンティック検証を無効化
```

| オプション | 説明 |
|-----------|------|
| `--view` | pending corrections を confidence・タイプ・経過日数付きで一覧表示 |
| `--dry-run` | 分析結果の表示のみ。ファイル書込・reflect_status 更新なし |
| `--skip-all` | 全 pending corrections を skipped に一括更新 |
| `--apply-all` | confidence >= 閾値の corrections を確認なしで一括適用。閾値未満は対話レビュー |
| `--min-confidence N` | `--apply-all` の閾値（デフォルト 0.85） |
| `--skip-semantic` | セマンティック検証（LLM によるノイズ除去）を無効化 |

対話レビューでは各 correction に対して approve / edit / skip / skip-remaining（3件目以降）を選択できる。

### 遺伝的最適化

#### `/rl-anything:optimize`

スキル/ルールを遺伝的アルゴリズムで最適化する。LLM でバリエーションを複数生成し、適応度関数で評価、エリート選択で次世代を生成。

```
/rl-anything:optimize my-skill                         # 基本実行（3世代 x 集団3）
/rl-anything:optimize my-skill --dry-run               # 構造テスト（LLM 呼び出しなし）
/rl-anything:optimize my-skill --fitness skill_quality  # カスタム適応度関数
/rl-anything:optimize my-skill --generations 5          # 5世代実行
/rl-anything:optimize my-skill --restore                # バックアップから復元
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `TARGET` | スキル名 or ファイルパス | 必須 |
| `--generations N` | 世代数 | 3 |
| `--population N` | 集団サイズ | 3 |
| `--fitness FUNC` | 適応度関数名 | default |
| `--dry-run` | 構造テスト | - |
| `--restore` | バックアップから復元 | - |

#### `/rl-anything:rl-loop`

ベースライン取得 → バリエーション生成 → 評価 → 人間確認のサイクルを1コマンドで回す。

```
/rl-anything:rl-loop my-skill              # 1ループ実行
/rl-anything:rl-loop my-skill --loops 3    # 3ループ実行
/rl-anything:rl-loop my-skill --auto       # 人間確認スキップ
/rl-anything:rl-loop my-skill --dry-run    # 構造テスト
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `TARGET` | スキル名 or ファイルパス | 必須 |
| `--loops N` | ループ回数 | 1 |
| `--auto` | 人間確認スキップ | - |
| `--dry-run` | 構造テスト | - |

#### `/rl-anything:generate-fitness`

CLAUDE.md・rules・skills を分析し、プロジェクト固有の評価関数を `scripts/rl/fitness/` に自動生成する。`--ask` でユーザーに品質基準を質問し、`.claude/fitness-criteria.md` に保存して以降の生成に反映できる。

```
/rl-anything:generate-fitness                # 基本実行
/rl-anything:generate-fitness --ask          # ユーザーに品質基準を質問してから生成
/rl-anything:generate-fitness --name bot     # 関数名を指定
/rl-anything:generate-fitness --dry-run      # 分析のみ
```

#### `/rl-anything:evolve-fitness`

accept/reject データ（30件以上）から score-acceptance 相関を分析し、評価関数の改善を提案する。

```
/rl-anything:evolve-fitness
```

- 相関 < 0.50 → 再キャリブレーション推奨
- 同じ rejection_reason が3回以上 → 新軸追加を提案

### ユーティリティ

| スキル | Usage |
|--------|-------|
| `feedback` | `/rl-anything:feedback` — GitHub Issue でフィードバック送信 |
| `update` | `/rl-anything:update` — プラグインを最新版に更新 |
| `version` | `/rl-anything:version` — バージョン・コミットハッシュ表示 |

## Hooks とデータ収集

7つの hooks がセッションライフサイクル全体をカバーし、LLM コストゼロでデータを収集する。

| Hook | イベント | 処理内容 | 出力先 |
|------|---------|---------|--------|
| `observe.py` | PostToolUse | Skill/Agent 使用記録、エラー記録 | `usage.jsonl`, `errors.jsonl`, `usage-registry.jsonl` |
| `correction_detect.py` | UserPromptSubmit | CJK/英語 26パターンの修正フィードバック検出 | `corrections.jsonl` |
| `subagent_observe.py` | SubagentStop | サブエージェント完了データ記録 | `subagents.jsonl` |
| `workflow_context.py` | PreToolUse | Skill 呼び出し時にワークフロー文脈を書き出し | `$TMPDIR/rl-anything-workflow-*.json` |
| `save_state.py` | PreCompact | コンテキスト圧縮前に進化状態 + corrections をチェックポイント | `checkpoint.json` |
| `restore_state.py` | SessionStart | チェックポイントから進化状態を復元 | stdout |
| `session_summary.py` | Stop | セッション要約＋ワークフローシーケンス記録 | `sessions.jsonl`, `workflows.jsonl` |

**ワークフロートレーシング**:

```
[SessionStart]  restore_state が checkpoint を復元
       ↓
[UserPromptSubmit]  correction_detect が修正パターンを検出 → corrections.jsonl
       ↓
[PreToolUse]    workflow_context が Skill 呼び出しに workflow_id を付与
       ↓
[PostToolUse]   observe が Skill/Agent 使用を記録（workflow_id 付き）
       ↓
[SubagentStop]  subagent_observe がサブエージェント完了を記録
       ↓
[PreCompact]    save_state が進化状態 + corrections をチェックポイント
       ↓
[Stop]          session_summary がセッション要約 + ワークフローシーケンスを出力
```

## 導入ストーリー

### 第1幕: Observe — データが貯まる

rl-anything をインストールすると、hooks が自動でスキル使用・エラー・修正フィードバックを記録し始める。過去データは `/rl-anything:backfill` で一括収集できる。

ある Slack Bot プロジェクトで14個のスキルを運用していた。品質はバラバラで、新メンバーが `/bot-create` を使うと personality 設定が抜け落ちる事故が起きていた。

### 第2幕: Discover → Optimize — パターンから改善へ

```
/rl-anything:discover
```

観測データから「`/bot-create` 後に手動で personality を追加している」パターンが検出された。ルール候補が自動生成され、承認して反映。

次に遺伝的最適化でスキル自体を改善:

```
/rl-anything:optimize bot-create
```

3世代の進化を経て、「personality 設定を必ず含めること」という明示的な指示が自動追加された。プロジェクト固有の評価関数を使うとさらに精度が上がる:

```
/rl-anything:generate-fitness
/rl-anything:optimize bot-create --fitness bot
```

スコアが 0.62 → 0.84 に上昇。

### 第3幕: Reflect — フィードバックが活きる

ユーザーが「いや、personality を先に設定して」と修正したフィードバックが corrections.jsonl に蓄積されていた:

```
/rl-anything:reflect
```

correction が CLAUDE.md のルールに自動反映され、以降の Claude Code セッションで同じミスが発生しなくなった。

### 第4幕: Evolve — 日次運用に乗せる

全フェーズを統合実行する `/rl-anything:evolve` で日次運用に移行。

```
/rl-anything:evolve
```

| タイミング | やること | 所要時間 |
|-----------|---------|---------|
| 新スキル追加時 | `/optimize` で1回最適化 → diff レビュー | 5分 |
| 日次/週次 | `/evolve` で全フェーズ統合実行 | 30分 |
| 修正が溜まったとき | `/reflect` でフィードバック反映 | 10分 |
| 評価に不足を感じたとき | `/evolve-fitness` で評価関数を改善 | 15分 |

## 適応度関数

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

### 評価関数の育成（evolve-fitness）

運用で accept/reject データが30件以上溜まると、`/rl-anything:evolve-fitness` で:

- score-acceptance 相関を分析（< 0.50 なら再キャリブレーション推奨）
- 欠落評価軸を提案（同じ rejection_reason が3回以上）
- adversarial probe でゲーミング脆弱性を検出

## rl-scorer のドメイン自動判定

CLAUDE.md からドメインを推定し、評価軸を自動切替。

| ドメイン | 評価軸 |
|----------|--------|
| ゲーム | 没入感・面白さ・バランス・具体性 |
| API/バックエンド | 正確性・堅牢性・保守性・セキュリティ |
| Bot/対話 | パーソナリティ適合・有用性・トーン一貫性 |
| ドキュメント | 正確性・可読性・実行可能性・完全性 |

スコア構成: 技術品質 (40%) + ドメイン品質 (40%) + 構造品質 (20%)

ワークフロー統計（`workflow_stats.json`）が存在する場合、ドメイン品質にパターン一貫性・ステップ効率性・エージェント戦略の明確さを補助シグナルとして加味（最大 +0.1）。統計がない場合は従来通りの評価にフォールバック。

## 向いているプロジェクト

| 特徴 | 理由 |
|------|------|
| スキルが10個以上 | 手動メンテのコストが高い。一括で品質底上げできる |
| ドメイン固有の語彙・ルールがある | 汎用評価では「良いスキル」を測れない |
| スキル品質が Claude の出力品質に直結 | スキルが雑だと Claude の出力も雑になる |
| チームで Claude Code を使っている | 暗黙知をスキル化 → 最適化 → チーム全体の品質向上 |

## Before / After

| 指標 | Before | After |
|------|--------|-------|
| スキル平均スコア | 0.58 | 0.79 |
| 新メンバーの作業ミス率 | 週3件 | 週0-1件 |
| スキル改善にかける時間 | 週4時間 | 週30分（レビューのみ） |

### チュートリアル: 1つのスキルを evolve で改善する

1. **現在のスコアを確認**:
   ```
   /rl-anything:optimize my-skill --dry-run
   ```
   → baseline score: 0.62

2. **evolve で全フェーズを一括実行**:
   ```
   /rl-anything:evolve
   ```
   Discover → Enrich → Optimize → Reorganize → Prune(+Merge) → Fitness Evolution → Reflect → Report が順番に実行される。

3. **改善後のスコアを確認**:
   ```
   /rl-anything:optimize my-skill --dry-run
   ```
   → baseline score: 0.84（+0.22 改善）

4. **diff をレビューして承認**:
   evolve は変更を提案するのみ。diff を確認して問題なければ承認する。

## テスト

```bash
python3 -m pytest hooks/ skills/ scripts/tests/ scripts/rl/tests/ -v
```

## claude-reflect からの移行

claude-reflect を使用していた場合、以下の手順でデータを rl-anything に移行できる。

1. **データ移行**:
   ```bash
   python3 <PLUGIN_DIR>/scripts/migrate_reflect_queue.py
   ```
   - `~/.claude/learnings-queue.json` を `~/.claude/rl-anything/corrections.jsonl` に変換
   - 冪等（二重追記防止）: 同一タイムスタンプ + メッセージハッシュで重複を排除
   - 元ファイルは空配列 `[]` にリセットされる

2. **確認**:
   ```bash
   /rl-anything:reflect --view
   ```

3. **アンインストール**:
   ```bash
   claude plugin uninstall claude-reflect
   ```

## Acknowledgements

本プラグインの correction detection・confidence decay・multi-target routing のアーキテクチャは [claude-reflect](https://github.com/bayramnnakov/claude-reflect)（MIT License, Bayram Annakov）を参考にしています。

## ライセンス

MIT
