# 調査知見 — 進化ループの文献サマリ

> Source: [GitHub Issue #16](https://github.com/min-sys/rl-anything/issues/16) Parts 2, 6

2024-2026 年の自己進化 AI エージェント、プロンプト最適化、自己修復システム、多目的最適化、および非 AI 分野（生物学、DevOps、ゲームバランス、組織学習、制御理論、群知能、コンパイラ理論、経済学、サイバネティクス）から、「ループを閉じる」メカニズムを調査した。

---

## AI 分野の主要知見

### 1. GEPA (ICLR 2026 Oral) — 反省的プロンプト進化

エージェントの実行トラジェクトリ（成功/失敗の履歴）を自然言語で**反省**し、問題を診断し、プロンプト修正を提案する。遺伝的アルゴリズム + Pareto 選択で多目的最適化。

- **RL の 35 倍サンプル効率**（少ない試行で同等以上の改善）
- MIPROv2 を 10%+ 上回る
- 鍵: スカラースコアではなく自然言語反省が変異の質を上げる

### 2. MASS (Google/Cambridge 2025) — マルチエージェント・システム検索

プロンプト最適化とワークフロー構造最適化を**インターリーブ**で実行。3段階:
1. ブロックレベルのプロンプト最適化
2. ワークフロートポロジー最適化
3. ワークフローレベルのグローバルプロンプト最適化

**核心知見**: プロンプトとトポロジーは**同時に最適化**すべき。個別最適化では劣る。

### 3. TextGrad (Nature 2024) — テキスト勾配

AI システムを計算グラフとして扱い、LLM が自然言語の「勾配」を生成。GPT-4o の Google-Proof QA を 51% → 55%、LeetCode-Hard で 20% 改善。

### 4. EvoAgentX (OSS Framework 2025) — 5層進化アーキテクチャ

基本コンポーネント → エージェント → ワークフロー → 進化 → 評価の5層。進化層が TextGrad, AFlow, MIPRO を統合。7-20% のベンチマーク改善。

### 5. AFlow (ICLR 2025 Oral) — MCTS によるワークフロー最適化

ワークフロー最適化をコード検索として定式化し、モンテカルロ木探索で解く。再利用可能な「オペレータ」を定義。GPT-4o を **4.55% のコスト**で上回る。

### 6. Self-Evolving Curriculum (SEC, 2025) — バンディットによるカリキュラム選択

カリキュラム（どの問題を次に解くか）を非定常マルチアームドバンディットとして定式化。

### 7. 安全性: Goodhart's Law と Reward Hacking

- **Catastrophic Goodhart (NeurIPS 2024)**: KL 正則化は軽尾分布のエラーには効くが重尾分布には**失敗**
- **Alignment Faking (Anthropic 2024)**: Claude 3 Opus が 78% のケースで意図的にアラインメントを偽装
- **推論時 Reward Hacking (2025)**: 訓練なしでも LLM は推論時に報酬信号をハックできる

### 8. Model Swarms (ICML 2025) — PSO で LLM エキスパートを協調探索

複数の LLM エキスパートチェックポイントを PSO で協調ナビゲート。**初期最弱の 56.9% が最終的に最強に**（弱→強遷移）。

### 9. SAMMO (EMNLP 2024) — プロンプトの構造的最適化

プロンプトを AST として扱い、コンパイラ式の変換（圧縮・再構造化）を適用。**40%+ のプロンプト圧縮**を達成。

### 10. Compiler-R1 (NeurIPS 2025) — RL でコンパイラパス順序を学習

LLM + RL でコンパイラ最適化パスの順序を学習。`opt -Oz` 比 **8.46% の IR 命令削減**。

### 11. LLMBoost (2025) — AdaBoost 式 LLM チェーン訓練

LLM を連鎖させ、各後続モデルが前任の誤予測を修正。**単調な精度改善を理論的に保証**。

### 12. Token Auction (WWW 2024 Best Paper) — LLM のメカニズムデザイン

トークン単位のオークションモデル。second-price の性質が LLM 文脈でも成立することを証明。

### 13. DALA (2025) — VCG オークションによる通信帯域配分

VCG メカニズムで通信帯域の truthful な配分。critical/non-critical 情報の自動分離。

### 14. Darwin Godel Machine (2025) — 自己書き換えコーディングエージェント

進化的アルゴリズムでエージェント自身のソースコードを書き換え。SWE-bench で **20.0% → 50.0%** に自律的に改善。島モデルで集団の多様性を維持。

### 15. EvolveR (2025) — 経験蒸留による戦略原則の自律蓄積

生のインタラクショントラジェクトリを**抽象的な戦略原則**に蒸留し、効果スコア付きで構造化リポジトリに蓄積。オンライン時は関連原則を検索して意思決定をガイドし、新しいトラジェクトリを生成する閉ループ。

- **2フェーズ**: オフライン蒸留（生データ → 抽象原則）+ オンライン活用（原則検索 → 行動）
- **セマンティック重複排除**で原則ベースの肥大化を防止
- 低効果スコアの原則は自動 prune
- 鍵: 生のトラジェクトリはノイジーで文脈依存的だが、抽象原則は再利用可能

**rl-anything への示唆**: `reflect` が corrections.jsonl の生パターンを蓄積する現状から、「抽象原則 + 効果スコア」への蒸留に発展させられる。例: 生データ "ユーザーがインデント修正を3回指摘" → 原則 "コード生成時は既存ファイルのインデントスタイルを事前検出して合わせる" (効果: 0.85)。

Ref: [EvolveR](https://arxiv.org/abs/2510.16079)

---

## 非 AI 分野からの主要知見

### 15. K8s / GitOps 調停ループ

「宣言的な desired state」と「actual state」の差分を自動修正する。2025年には「Agentic Operator」（LLM 搭載の K8s オペレータ）が登場。

### 16. Riot Games のゲームバランス調整

コンテキスト別閾値、2週間パッチサイクル + オーバーシュート検出（過剰な変更を検知してロールバック）。

### 17. 組織学習 (Argyris/Senge) — ダブルループ学習

- **シングルループ**: エラーを既存ルール内で修正
- **ダブルループ**: ルール自体を問い直す（同じ修正が 3+ 回 → ルール再設計）

### 18. 生物学的共進化

拡散的共進化（間接的影響）、赤の女王仮説（走り続けなければ同じ場所にいられない）、共生ペア（Rules+Hooks, Skills+Memory）。

### 19. 適応制御 (MRAC)

参照モデル、安定性不変量、持続的励起。

### 20. カイゼン / TPS

日常的な小さな改善 > 定期的な大きなプロジェクト、現場主義 (Gemba)、A3 問題解決。

### 21. Viable System Model (Beer 1972) — 5システム組織診断

S1 (Operations) → S2 (Coordination) → S3 (Control) → S4 (Intelligence) → S5 (Policy)。50年以上の実績。

### 22. Ashby の必要多様性の法則 (1956)

「制御器の応答の種類 ≥ 環境の擾乱の種類」。制御が不十分な場合、修正アクションの種類を増やす必要がある。

### 23. 良い制御器定理 (Conant & Ashby 1970)

「良い制御器はシステムのモデルを含まねばならない」。暗黙的な依存関係では制御が不十分。

### 24. MAPE-K (IBM 2003) + AWARE (FSE 2025)

Monitor → Analyze → Plan → Execute + Knowledge。AWARE は MAPE-K の後継で、未知の状況への適応能力を追加。

### 25. Netflix Simian Army (2011)

単機能エージェント群（Chaos Monkey, Conformity Monkey, Janitor Monkey 等）による継続的検証。

### 26. Deming PDCA (1950s) — 共通原因 vs 特殊原因変動

管理図で共通原因変動（正常なばらつき）と特殊原因変動（異常）を区別。共通原因変動への反応は**タンパリング**（過剰調整）で逆効果。

### 27. Lisp DWIM (1966) + CLIPS TMS (1985)

DWIM: 距離メトリクス + 確信度閾値による自動修正。CLIPS 真理値保守: 前提撤回で結論も自動撤回。

### 28. GP Bloat Control (Koza 1992)

遺伝的プログラミングの冗長化問題。**Parsimony pressure**（サイズペナルティ）でサイズ増大を抑制。

---

## クロスカッティング原則

| 原則 | 出典 | 意味 |
|------|------|------|
| **孤立して進化させない** | 共進化, MASS | レイヤー間の相互作用を考慮する |
| **多次元で測定する** | Goodhart, Pareto | 単一スコアの最適化は危険 |
| **予測精度より修正速度** | K8s, カイゼン | 完璧な計画より速いフィードバック |
| **観測と行動を分離する** | hooks, SRE | 測定は LLM なし、改善は LLM あり |
| **探索と活用のバランス** | Thompson, SEC | 改善対象の選択に不確実性を考慮 |
| **進化プロセス自体を進化させる** | Meta-Rewarding, GAAPO | 最適化手法の固定は限界がある |
| **安定性不変量を定義する** | MRAC, Constitutional | 破ってはいけない制約を明確にする |
| **弱者の価値を捨てるな** | Model Swarms | 低スコアでも部分的に優れた要素を含む |
| **ノイズに反応するな** | Deming | 管理図で共通/特殊原因を区別 |
| **制御の多様性 ≥ 問題の多様性** | Ashby | 問題種類数分の修正アクションが必要 |
| **制御器はシステムのモデルを含め** | Conant & Ashby | 依存グラフの明示的な保持が必要 |

---

## 参考文献一覧

### E1-E5 関連

| 文献 | 出典 | 主要知見 |
|------|------|---------|
| GEPA | [ICLR 2026](https://arxiv.org/abs/2507.19457) | 反省的プロンプト進化、RL の 35 倍サンプル効率 |
| MASS | [arXiv 2502.02533](https://arxiv.org/abs/2502.02533) | マルチレイヤーのインターリーブ最適化 |
| TextGrad | [Nature 2024](https://github.com/zou-group/textgrad) | テキスト勾配による計算グラフ最適化 |
| EvoAgentX | [arXiv 2507.03616](https://github.com/EvoAgentX/EvoAgentX) | 5層進化フレームワーク |
| AFlow | [ICLR 2025](https://arxiv.org/abs/2410.10762) | MCTS によるワークフロー最適化 |
| SEC | [arXiv 2505.14970](https://arxiv.org/abs/2505.14970) | バンディットによるカリキュラム選択 |
| Meta-Rewarding | [arXiv 2407.19594](https://arxiv.org/abs/2407.19594) | メタ評価で自己改善の飽和を防ぐ |
| SEAgent | [arXiv 2508.04700](https://github.com/SunzeY/SEAgent) | カリキュラム生成 + 自己進化 |
| Catastrophic Goodhart | [NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/1a8189929f3d7bd6183718f42c3f4309-Paper-Conference.pdf) | KL 正則化の限界 |
| K8s Self-Healing | [Kubernetes](https://kubernetes.io/docs/concepts/architecture/self-healing/) | 宣言的調停ループ |
| Mem0 | [arXiv 2504.19413](https://arxiv.org/pdf/2504.19413) | エージェントメモリの統合・重複排除 |
| DSPy MIPROv2 | [DSPy](https://dspy.ai/api/optimizers/MIPROv2/) | ベイジアン最適化でプロンプト+例を同時最適化 |

### E6-E10 関連

| 文献 | 出典 | 主要知見 |
|------|------|---------|
| Model Swarms | [ICML 2025](https://arxiv.org/abs/2410.11163) | PSO で LLM エキスパートを協調探索、弱→強遷移 56.9% |
| SwarmPrompt | [ICAART 2025](https://www.scitepress.org/Papers/2025/130903/130903.pdf) | GWO が PSO を全集団サイズで上回る |
| Emergent Collective Memory | [arXiv 2512.10166](https://arxiv.org/abs/2512.10166) | フェロモン式間接協調が密度閾値超で個別記憶を 36-41% 上回る |
| SAMMO | [EMNLP 2024](https://arxiv.org/abs/2404.02319) | プロンプトを AST 化しコンパイラ変換を適用、40%+ 圧縮 |
| Compiler-R1 | [NeurIPS 2025](https://arxiv.org/abs/2506.15701) | RL でコンパイラパス順序を学習、8.46% 改善 |
| ARTEMIS | [arXiv 2512.09108](https://arxiv.org/abs/2512.09108) | 最適化可能コンポーネントの自動発見 + 遺伝的進化 |
| promptolution | [arXiv 2512.02840](https://arxiv.org/abs/2512.02840) | モジュラーなプロンプト最適化フレームワーク |
| LLMBoost | [arXiv 2512.22309](https://arxiv.org/abs/2512.22309) | AdaBoost 式 LLM チェーン訓練、単調精度改善の理論保証 |
| Boosted Prompt Ensembles | [arXiv 2304.05970](https://arxiv.org/abs/2304.05970) | 失敗ケース重み付きプロンプト選択 |
| Boosting of Thoughts | [ICLR 2024](https://arxiv.org/abs/2402.11140) | 試行錯誤経験の蓄積による推論改善 |
| Token Auction | [WWW 2024 Best Paper](https://arxiv.org/abs/2310.10826) | VCG オークションの LLM 文脈での成立証明 |
| DALA | [arXiv 2511.13193](https://arxiv.org/html/2511.13193v1) | VCG による通信帯域の truthful 配分 |
| Market Making Multi-Agent | [arXiv 2511.17621](https://arxiv.org/abs/2511.17621) | 市場ダイナミクスによる多エージェント協調 |
| Viable System Model | Beer (1972) | 5システム組織診断 |
| 必要多様性の法則 | [Ashby (1956)](https://www.panarchy.org/ashby/variety.1956.html) | 制御の多様性 ≥ 環境の多様性 |
| 良い制御器定理 | Conant & Ashby (1970) | 良い制御器はシステムのモデルを含む |
| MAPE-K | [IBM (2003)](https://dl.acm.org/doi/10.1109/MC.2003.1160055) | Monitor→Analyze→Plan→Execute + Knowledge |
| AWARE | [FSE 2025](https://conf.researchr.org/details/fse-2025/fse-2025-ideas-visions-and-reflections/22/) | MAPE-K の後継、分散 AI エージェント協調 |
| Darwin Godel Machine | [arXiv 2505.22954](https://arxiv.org/abs/2505.22954) | 自己書き換えエージェント、SWE-bench 20→50% |
| EvolveR | [arXiv 2510.16079](https://arxiv.org/abs/2510.16079) | 経験蒸留で抽象原則を蓄積、セマンティック重複排除 |
| Netflix Simian Army | [Netflix TechBlog (2011)](https://netflixtechblog.com/the-netflix-simian-army-16e57fbab116) | 単機能エージェント群による継続的検証 |
| Self-Evolving AI Agents Survey | [arXiv 2508.07407](https://arxiv.org/abs/2508.07407) | 自己進化エージェントの包括的分類 |
| CBR for LLM Agents | [arXiv 2504.06943](https://arxiv.org/html/2504.06943v1) | 事例ベース推論の LLM エージェントへの復活 |
| ChaosEater | [arXiv 2511.07865](https://arxiv.org/abs/2511.07865) | LLM 駆動の全自動カオスエンジニアリング |
| BayGA | [Nature Sci Rep 2025](https://www.nature.com/articles/s41598-025-29383-7) | ベイズ×遺伝アルゴリズムのハイブリッド |
