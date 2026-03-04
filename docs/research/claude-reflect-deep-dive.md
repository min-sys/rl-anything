# claude-reflect 詳細調査

> 調査日: 2026-03-01
> **ステータス: 参考資料** — rl-anything が correction detection・reflect を独自実装したため、claude-reflect は採用していません。設計の参考として保持。

## 結論（先に）

**BayramAnnakov/claude-reflect が圧倒的に成熟**。v3.0.1、758 stars、160テスト。
プラグインマーケットプレイス経由でインストール可能。

rl-anything では以下のアーキテクチャを参考に独自実装した:
1. **correction_detect.py** — UserPromptSubmit フックで CJK/英語 26パターンの修正検出
2. **reflect スキル** — corrections.jsonl → CLAUDE.md/rules への反映
3. **偽陽性フィルタ** — CJK 対応を含むフィルタリング

---

## 2リポジトリの比較

| 観点 | BayramAnnakov/claude-reflect | haddock/claude-reflect-system |
|------|------------------------------|-------------------------------|
| Star数 | **758** | 68 |
| バージョン | **v3.0.1** | v1.0.0 |
| インストール | **マーケットプレイス** | 手動コピー |
| Hook数 | **4つ** | 1つ（Stopのみ） |
| 書き込み先 | **6層メモリ階層** | SKILL.mdのみ |
| リアルタイムキャプチャ | **あり** | なし |
| 重複排除 | **あり** | なし |
| スキルディスカバリー | **あり** | なし |
| テスト | **160テスト + CI/CD** | なし |
| 総合 | **採用推奨** | 参考程度 |

以下、BayramAnnakov/claude-reflect を中心に詳述。

---

## BayramAnnakov/claude-reflect

### 基本情報

| 項目 | 内容 |
|------|------|
| GitHub | [BayramAnnakov/claude-reflect](https://github.com/BayramAnnakov/claude-reflect) |
| Star | 758 / Fork 54 |
| 言語 | Python 3.6+（標準ライブラリのみ） |
| ライセンス | MIT |
| バージョン | v3.0.1 (2026-02-28更新) |

### インストール

```bash
claude plugin marketplace add bayramannakov/claude-reflect
claude plugin install claude-reflect@claude-reflect-marketplace
# 再起動必須
```

### アーキテクチャ: 2段階プロセス

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stage 1: キャプチャ（自動・毎プロンプト）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ユーザープロンプト
       │
       ▼
  [UserPromptSubmit hook]
  capture_learning.py
       │
       ├── regex パターン検出
       │   ├── "no, use X" → 補正 (0.75)
       │   ├── "don't add X unless" → ガードレール (0.85)
       │   ├── "remember:" → 明示 (0.90)
       │   └── "perfect!" → 正のFB (0.70)
       │
       ├── 偽陽性フィルタ
       │   ├── 疑問文（?で終わる）→ 除外
       │   ├── 500文字超 → 除外
       │   └── XML/JSON混入 → 除外
       │
       └── ~/.claude/learnings-queue.json にキューイング

  [SessionStart hook] → キュー残件を通知
  [PreCompact hook] → コンテキスト圧縮前にバックアップ
  [PostToolUse hook] → git commit後に /reflect リマインド

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stage 2: プロセス（手動・/reflect コマンド）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /reflect 実行
       │
       ▼
  キューから読み込み
       │
       ▼
  [semantic_detector.py]
  claude -p でAI検証（偽陽性除去）
  デフォルトモデル: sonnet
       │
       ▼
  既存エントリとの重複チェック
       │
       ▼
  6層メモリ階層ルーティング
  （どのファイルに書くか自動判定）
       │
       ▼
  ヒューマンレビュー
  Apply / Edit / Skip
       │
       ▼
  ファイル書き込み

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 4つのHookイベント

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/capture_learning.py\""
      }]
    }],
    "PreCompact": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/check_learnings.py\""
      }]
    }],
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/post_commit_reminder.py\""
      }]
    }],
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/session_start_reminder.py\""
      }]
    }]
  }
}
```

### パターン検出の詳細

#### 4段階の信頼度

| 段階 | パターン例 | 信頼度 |
|------|-----------|--------|
| Explicit | `remember:` プレフィックス | 0.90 |
| Guardrail | `"don't add X unless"`, `"only change what I asked"` | 0.80-0.90 |
| Correction（強） | `"no, use X"`, `"don't use Y"`, `"actually..."` | 0.75-0.85 |
| Correction（弱） | `"that's wrong"`, `"use X not Y"` | 0.55-0.65 |
| Positive | `"perfect!"`, `"exactly right"` | 0.70 |

#### 信頼度の調整ロジック

- 短いメッセージ（80文字未満）: **+0.10** ブースト（明確な指示の可能性が高い）
- 長いメッセージ（300文字超）: **-0.15** ペナルティ（ノイズの可能性）
- 複数パターンマッチ（3個以上）: **0.85** まで上昇

### 6層メモリ階層（v3.0で導入）

```
┌─────────────────────────────────────────────────┐
│  メモリ階層                                      │
│                                                  │
│  高信頼度 ──────────────────────── 低信頼度       │
│                                                  │
│  ~/.claude/CLAUDE.md     (グローバル)            │
│  ./CLAUDE.md             (プロジェクト)          │
│  ./CLAUDE.local.md       (個人用・gitignore)     │
│  ./.claude/rules/*.md    (モジュラールール)       │
│  ~/.claude/rules/*.md    (グローバルルール)       │
│  ~/.claude/projects/.../memory/*.md (低信頼度)   │
│  ./commands/*.md         (スキル改善)            │
│  ./AGENTS.md             (クロスツール標準)       │
│                                                  │
└─────────────────────────────────────────────────┘
```

#### ルーティングロジック

| 検出内容 | 書き込み先 |
|---------|-----------|
| ガードレール系 | `.claude/rules/guardrails.md` |
| モデル名を含む | グローバル `~/.claude/CLAUDE.md` |
| `always`/`never`/`prefer` | グローバル `~/.claude/CLAUDE.md` |
| パス制約付き | 該当する `.claude/rules/*.md` |
| 低信頼度（0.60-0.74） | `memory/*.md`（ステージング） |

### コマンド一覧

| コマンド | 説明 |
|---------|------|
| `/reflect` | キューされた学習をレビュー・適用 |
| `/reflect --scan-history` | 過去全セッションスキャン |
| `/reflect --dry-run` | プレビューのみ |
| `/reflect --dedupe` | 類似エントリ統合 + 矛盾検出 |
| `/reflect --organize` | メモリ階層再構成提案 |
| `/reflect --include-tool-errors` | ツールエラーも学習対象に |
| `/reflect --model MODEL` | セマンティック分析モデル指定 |
| `/reflect-skills` | スキル候補の自動発見 |
| `/skip-reflect` | 全キュー破棄 |
| `/view-queue` | キュー閲覧 |

### 制限事項・注意点

| 問題 | 詳細 | 状況 |
|------|------|------|
| CJK偽陽性 | 日本語・中国語・韓国語で誤検出 | PR #19で対応中 |
| `CLAUDE_PLUGIN_ROOT`未設定 | hookが失敗する | Issue #17 (Open) |
| クロスコンタミネーション | プロジェクト間でキュー共有 | PR #21で対応中 |
| APIトークン消費 | `/reflect`実行時にClaude CLIを子プロセス呼び出し | sonnetモデル使用 |
| セッション履歴消失 | `cleanupPeriodDays`未設定だと30日で消える | 設定で対応 |

### パフォーマンス影響

- **UserPromptSubmit hook**: 毎プロンプトで実行されるが、regexベースなのでミリ秒単位
- **セマンティック分析**: `/reflect` 実行時のみ（30秒タイムアウト付き）
- **通常の開発体験**: ほぼ影響なし

---

## haddock-development/claude-reflect-system（参考）

### 基本情報

| 項目 | 内容 |
|------|------|
| GitHub | [haddock-development/claude-reflect-system](https://github.com/haddock-development/claude-reflect-system) |
| Star | 68 / Fork 9 |
| バージョン | v1.0.0 |

### 異なるアプローチ

- **Stopフック1つだけ**: セッション終了時にのみリフレクション
- **SKILL.mdに直接書き込み**: CLAUDE.mdではなくスキルファイルを更新
- **3段階セクション**: HIGH → `Critical Corrections` / MEDIUM → `Best Practices` / LOW → `Advanced Considerations`
- **メタラーニング**: `/reflect-meta` でリフレクションプロセス自体を改善（ユニーク機能）

### Atlas Breeadersへの示唆

このリポジトリからの学び:
- **SKILL.mdへの直接書き込み**は、本プロジェクトのスキル自己成長（skill-evolve）概念と一致
- **信頼度別セクション分け**は、知見の成熟度管理として参考になる

---

## Atlas Breeadersへの適用分析

### 相性の良い点

1. **6層メモリ階層**: 本プロジェクトの `rules/` + `skills/` + `memory/` 構造に自然にマッピング

   | claude-reflect の階層 | Atlas Breeaders の対応物 |
   |---|---|
   | `.claude/rules/*.md` | `.claude/rules/`（11ファイル） |
   | `./commands/*.md` | `.claude/skills/*/SKILL.md`（23スキル） |
   | `memory/*.md` | `memory/MEMORY.md` |
   | `./CLAUDE.md` | `./CLAUDE.md` |

2. **ガードレール検出**: `"only change what I asked"`, `"stop refactoring unrelated"` はまさにこのプロジェクトで頻出するパターン

3. **`/reflect --dedupe`**: 23スキル間の知見重複を検出・統合できる

### 注意が必要な点

1. **CJK偽陽性**: 日本語のプロンプトで誤検出の可能性。PR #19のマージを待つか、自前でフィルタ追加
2. **MEMORY.md 200行制限**: 自動追記でオーバーフローする可能性。低信頼度のステージング先を別ファイルに
3. **API消費**: `/reflect` でsonnetを使うため、頻繁な実行はコストに注意

### 導入ステップ案

```
Step 1: プラグインインストール
  claude plugin marketplace add bayramannakov/claude-reflect
  claude plugin install claude-reflect@claude-reflect-marketplace

Step 2: CJK対応の確認
  日本語プロンプトでの偽陽性を確認
  必要なら capture_learning.py にフィルタ追加

Step 3: メモリ階層ルーティングのカスタマイズ
  本プロジェクトの rules/skills/memory 構造に合わせて
  suggest_claude_file() のロジックを調整

Step 4: /reflect を日常ワークフローに組み込み
  OpenSpec verify 後に /reflect を実行する習慣
  git commit 前の /reflect リマインドを活用

Step 5: /reflect --dedupe で定期的な棚卸し
  月1回程度、スキル間・ルール間の重複を検出・統合
```
