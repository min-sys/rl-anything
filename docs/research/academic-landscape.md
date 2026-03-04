# 学術的な最新動向 - 自己進化するLLMエージェント

## サーベイ論文（全体像の把握に）

### A Comprehensive Survey of Self-Evolving AI Agents (2025年8月)

- **arXiv**: [arXiv:2508.07407](https://arxiv.org/abs/2508.07407)
- **GitHub**: [EvoAgentX/Awesome-Self-Evolving-Agents](https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents)
- **分類**: 単一エージェント最適化 / マルチエージェント最適化 / ドメイン固有最適化
- **貢献**: フィードバックループの統一的概念フレームワークを提案

### A Survey of Self-Evolving Agents (2025年7月)

- **arXiv**: [arXiv:2507.21046](https://arxiv.org/abs/2507.21046)
- **整理軸**: 何を(What) / いつ(When) / どうやって(How) / どこで(Where) 進化するか
- **位置づけ**: 人工超知能(ASI)への道筋として

---

## 主要な論文

### Self-Rewarding Language Models (2024年1月, ICML'24)

- **arXiv**: [arXiv:2401.10020](https://arxiv.org/abs/2401.10020)
- **核心**: LLM自身がLLM-as-a-Judgeとして自らの出力を報酬として使用
- **意義**: 凍結された報酬モデルではなく、自己改善する報酬モデルの学習を実現
- **RLAnythingとの関係**: RLAnythingの「報酬モデルの同時最適化」の先行研究

### Meta-Rewarding Language Models (2024年7月)

- **OpenReview**: [openreview.net/forum?id=lbj0i29Z92](https://openreview.net/forum?id=lbj0i29Z92)
- **核心**: Self-Rewardingの拡張。「自分の判断を自分で判断する」Meta-Rewardingステップ
- **成果**: Llama-3-8B-InstructのAlpacaEval 2勝率を22.9%→39.4%に改善
- **RLAnythingとの関係**: 報酬モデルの再帰的改善という点で関連

### Multi-Agent Evolve (MAE) (2025年10月)

- **arXiv**: [arXiv:2510.23595](https://arxiv.org/abs/2510.23595)
- **核心**: Proposer(問題生成) + Solver(回答) + Judge(評価) の3役を単一LLMからインスタンス化
- **RLAnythingとの関係**: 方策/報酬/環境の3要素を別エージェントで担当する点が類似

### SEAgent: Self-Evolving Computer Use Agent (2025年8月)

- **arXiv**: [arXiv:2508.04700](https://arxiv.org/abs/2508.04700)
- **GitHub**: [SunzeY/SEAgent](https://github.com/SunzeY/SEAgent)
- **核心**: コンピュータ操作エージェントが未知ソフトウェアと自律的に対話して進化
- **成果**: 成功率を11.3%→34.5%に改善（+23.2%）
- **手法**: カリキュラムジェネレーターで段階的に難しいタスクを生成 + GRPO

### Constitutional AI (Anthropic, 2022年12月)

- **arXiv**: [arXiv:2212.08073](https://arxiv.org/abs/2212.08073)
- **核心**: 「憲法」に基づくRL from AI Feedback（RLAIF）
- **意義**: RLAIF概念の原点。人間のフィードバックなしにAIの行動を改善

---

## プロンプト自動最適化

### GAAPO (Genetic Algorithm Applied to Prompt Optimization)

- **論文**: [Frontiers in AI](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1613007/full)
- **核心**: 遺伝的アルゴリズムでプロンプトを最適化
- **成果**: バリデーションスコア0.46（OPRO 0.24, Mutator 0.34, APO 0.38を大幅に上回る）

### GEPA (Genetic-Pareto Evolutionary Prompt Optimization)

- **手法**: エージェント軌跡をサンプリング → 自然言語で振り返り → プロンプト修正を提案 → 反復
- **意義**: モデル重みの更新なしでRLアプローチに匹敵する性能

---

## 注目イベント

### ICLR 2026 Workshop on Recursive Self-Improvement

- **公式**: [recursive-workshop.github.io](https://recursive-workshop.github.io/)
- **場所**: リオデジャネイロ、2026年4月26-27日
- **焦点**: LLMエージェントが自らのコードベースやプロンプトを書き換える再帰的自己改善
- **5つの分析レンズ**: 変更対象 / 適応の時間的体制 / メカニズム / 運用コンテキスト / 改善のエビデンス

---

## 全体像マップ

```
                    自己進化するAIエージェント
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   方策の改善         報酬モデルの改善      環境の適応
        │                  │                  │
  Self-Rewarding    Meta-Rewarding      SEAgent
  (LLM-as-Judge)   (再帰的判断改善)    (カリキュラム生成)
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
               RLAnything    MAE (Multi-Agent)
             (3要素同時最適化) (3役分担)
                    │
              Claude Codeへの
              適用が可能
```
