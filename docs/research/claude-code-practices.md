# Claude Codeでの自己進化 - 実践事例

## 事例一覧

| 事例 | アプローチ | 実装コスト | 効果 |
|------|-----------|-----------|------|
| [claude-meta](#1-claude-meta) | メタルール1文 | 極小 | 中〜高 |
| [claude-reflect](#2-claude-reflect) | PostToolUse + Stopフック | 中 | 高 |
| [claude-reflect-system](#3-claude-reflect-system) | Stopフック自動リフレクション | 中 | 高 |
| [hooks-mastery](#4-hooks-mastery) | 13フック完全制御 | 高 | 最高 |
| [セッションログ解析](#5-セッションログ解析) | JSONL事後分析 | 低 | 中 |

---

## 1. claude-meta

**最もシンプル。最初の一歩に最適。**

- **GitHub**: [aviadr1/claude-meta](https://github.com/aviadr1/claude-meta)
- **DEV記事**: [Self-Improving AI: One Prompt That Makes Claude Learn From Every Mistake](https://dev.to/aviad_rozenhek_cba37e0660/self-improving-ai-one-prompt-that-makes-claude-learn-from-every-mistake-16ek)

### やること

CLAUDE.mdに「メタルール」（ルールの書き方のルール）を記載する。ミスが起きた時に:

```
Reflect on this mistake. Abstract and generalize the learning. Write it to CLAUDE.md.
```

これだけで、Claudeがメタルールに従って自己改善を実行する。

### なぜ効くのか

- セッション開始時にCLAUDE.mdを読み込み
- プロジェクトルールとルール記述方法の両方を学習
- ミス時にリフレクション→メタルールに従って自動追記
- 次のセッションで反映

### Atlas Breeadersとの関連

このプロジェクトの `.claude/rules/rules-style.md` はまさにメタルール:
> `.claude/rules/` のファイルは3行以内で書く。詳細な手順・例・テンプレートはスキルに置く。

これを拡張して「MEMORYの書き方のルール」を追加すれば、そのまま適用可能。

---

## 2. claude-reflect

**フック駆動型。ユーザーの修正パターンを自動検出。**

- **GitHub**: [BayramAnnakov/claude-reflect](https://github.com/BayramAnnakov/claude-reflect)

### やること

PostToolUseフックとStopフックで:
1. ユーザーの修正パターン（"no, use X", "actually...", "wait..."）を自動検出
2. 修正パターンをキューに蓄積
3. `/reflect` コマンドで人間のレビュー付きでCLAUDE.mdに書き戻し

### 特筆すべき機能

- **セッション履歴スキャン**: 過去のやり取りからパターンを検出
- **セマンティック重複排除**: `/reflect --dedupe` で既存ルールとの重複を排除
- **多言語対応**: 日本語でも動作

### Atlas Breeadersとの関連

特に強力なのは**重複排除**機能。23スキル + 11ルール + MEMORYの体系で、知見の重複管理は重要な課題。

---

## 3. claude-reflect-system

**セッション間で学習が引き継がれる。**

- **GitHub**: [haddock-development/claude-reflect-system](https://github.com/haddock-development/claude-reflect-system)

### やること

Stopフックでセッション終了時に自動リフレクションを実行。修正パターンを恒久的なスキルとして保存。

### ポイント

- 同じミスを跨セッションで繰り返さない
- スキルファイルとして構造化されるため、検索・管理が容易

---

## 4. hooks-mastery

**本格的。3,000+ stars。**

- **GitHub**: [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

### やること

13のライフサイクルフックでClaude Code CLIの全段階を制御:
- PostToolUseバリデーターでコード品質を自動検証
- Builder/Validatorエージェントパターンで信頼性を向上
- チャットトランスクリプト抽出
- チームベース検証

### Atlas Breeadersとの関連

Agent Teamワークフロー（worktree並行開発）と組み合わせると、各エージェントの行動品質を自動検証するパイプラインが構築可能。

---

## 5. セッションログ解析

**事後分析型。既存のログを活用。**

- **ブログ**: [Self-improving CLAUDE.md files (Martin Alderson)](https://martinalderson.com/posts/self-improving-claude-md-files/)
- **Gist**: [Self-Improving Claude Code bootstrap (ChristopherA)](https://gist.github.com/ChristopherA/fd2985551e765a86f4fbb24080263a2f)

### やること

`~/.claude/projects`のJSONLセッションログを解析:
1. フラストレーションパターンを検出（ユーザーの修正指示等）
2. セッション間の繰り返し要求を特定
3. CLAUDE.mdの改善提案を生成

### Atlas Breeadersとの関連

MEMORY.mdに記録済みの「Agent Teamワークツリーのファイルロス防止」教訓は、まさにこのアプローチで得られた知見。subagent jsonlログ（`.claude/projects/.../subagents/agent-{id}.jsonl`）からの分析パイプラインは既に経験済み。

---

## 他のツールでの類似アプローチ

| ツール | 仕組み | 参考 |
|--------|--------|------|
| **Cursor** | .cursorrules の自動改善 | [Agent Best Practices](https://cursor.com/blog/agent-best-practices) |
| **Windsurf** | Memories System（自動コンテキスト保持） | [Cascade Memories](https://docs.windsurf.com/windsurf/cascade/memories) |
| **Roo Code** | Memory Bank（.rooフォルダにMarkdown） | [roocode.com](https://roocode.com) |
| **横断** | 全ツール対応プロンプト集 | [instructa/ai-prompts](https://github.com/instructa/ai-prompts) |

---

## その他の参考リンク

- [SpecWeave Self-Improving Skills](https://spec-weave.com/docs/skills/extensible/self-improving-skills/) - スキルの自己成長フレームワーク
- [bokan/claude-skill-self-improvement](https://github.com/bokan/claude-skill-self-improvement) - スキル自己改善
- [OpenAI Self-Evolving Agents Cookbook](https://cookbook.openai.com/examples/partners/self_evolving_agents/autonomous_agent_retraining) - OpenAI版の実装ガイド
