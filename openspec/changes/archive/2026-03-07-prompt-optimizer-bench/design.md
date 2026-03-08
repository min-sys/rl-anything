## Context

rl-anything の `/optimize` は遺伝的アルゴリズム（GA）でスキル定義を最適化するが、10回の実行で一度もオリジナルを超えられていない。原因は3つ: (1) `claude -p` で全文書き直しすると出力が途中で切れる（自壊問題）、(2) 評価が見た目品質のみ、(3) 探索空間が 3x3=9 で狭すぎる。

2025-2026年のプロンプト最適化研究は GEPA（ICLR 2026 Oral）、TextGrad（Nature）、DSPy MIPROv2 など大きく進歩しており、どの手法が「メタプロンプト（スキル定義）の最適化」に最も効果的かを実データで検証する。

別リポジトリ `prompt-optimizer-bench` として構築し、pip 依存を rl-anything から完全に隔離する。

## Goals / Non-Goals

**Goals:**

- 6手法を統一インターフェースで公平に比較できるベンチマークフレームワーク
- Layer B（メタプロンプト最適化）: スキル定義の改善効果を実タスクで測定
- Layer A（汎用プロンプト最適化）: 各手法の地力を公開データセットで測定
- 再現可能な結果（seed固定、設定ファイル管理）
- rl-anything optimize v2 への手法還元

**Non-Goals:**

- rl-anything 本体のコード変更（結果を見てから別 change で対応）
- 独自の最適化アルゴリズムの研究開発（既存手法の比較に集中）
- プロダクション用の最適化サービス構築

## Decisions

### 1. 別リポジトリとして構築する

**選択**: `prompt-optimizer-bench` を min-sys org に新規作成

**理由**: TextGrad, DSPy, GEPA の pip 依存を rl-anything（Claude Code Plugin）から完全に隔離する。Plugin はゼロ依存が原則。

**代替案**: rl-anything 内の `benchmarks/` ディレクトリ → 依存が混入するリスク、却下

### 2. Strategy パターンで手法を抽象化する

**選択**: 共通の `BaseStrategy` ABC を定義し、各手法を Strategy として実装

```
BaseStrategy
├── mutate(content, context) -> str      # 変異生成
├── evaluate(original, mutated) -> Score # 評価
└── should_stop(history) -> bool         # 収束判定
```

**理由**: 公平な比較には統一インターフェースが必須。各手法の内部実装は自由だが、入出力を揃える。

**代替案**: 各手法を独立スクリプトとして実行 → 評価の一貫性が保てない、却下

### 3. 評価は4メトリクスの複合スコア

**選択**: 以下の4メトリクスを独立に測定し、レーダーチャートで可視化

| メトリクス | 測定方法 |
|-----------|---------|
| スコア改善幅 | LLM CoT 評価の before/after 差分 |
| 変異生存率 | 変異体がオリジナルを上回った回数 / 総試行数 |
| 変異完全性 | 出力が途切れず完全なスキルになった率 |
| LLM コスト | API 呼び出し回数（`claude -p` 実行回数） |

**理由**: 単一スコアでは手法の特性が見えない。例えば TextGrad はスコア改善幅が高いがコストも高い、といった tradeoff を可視化する。

### 4. Phase 分けで段階的に実装する

**選択**:
- Phase 1: Self-Refine + GEPA-lite + 現行GA（pip 依存なし、`claude -p` のみ）
- Phase 2: TextGrad + DSPy 追加（pip 依存追加）
- Phase 3: Layer A 汎用ベンチマーク + PromptAgent

**理由**: Phase 1 で最小限のベンチマークを動かし、早期に価値のある比較結果を得る。Phase 2 以降は Phase 1 の結果を見て判断。

### 5. テスト対象スキルは3サイズ x 複数ドメイン

**選択**: 短（〜20行）、中（〜50行）、長（〜100行）の3サイズ。rl-anything 内のスキルと汎用スキルを混在。

**理由**: サイズによって手法の適性が変わる可能性がある（GA の自壊問題は長いスキルで顕著）。

### 6. LLM 呼び出しは `claude -p` に統一する

**選択**: 全手法で `claude -p --output-format text` を使用（Phase 1）。Phase 2 の TextGrad/DSPy はそれぞれのフレームワーク経由の API 呼び出し。

**理由**: Phase 1 で API キー不要、rl-anything と同じ実行環境で比較できる。

## Risks / Trade-offs

**[LLM コスト]** 3手法 x 3スキル x 5回 = 45+ 回の `claude -p` 呼び出し。Self-Refine/GEPA は内部で複数回呼ぶため実質100回超え。
→ ドライランモードを実装し、LLM 呼び出しをモックできるようにする。本番実行は手動トリガー。

**[評価の公平性]** LLM CoT 評価自体が「見た目品質」を測る問題は残る。
→ Layer B のテストタスク評価（実タスク実行）で補完する。

**[再現性]** LLM の出力は非決定的。同じ手法でもランごとにスコアが変動する。
→ N=5 以上の試行で統計的に比較。平均・標準偏差・信頼区間を算出。

**[Phase 2 依存の互換性]** TextGrad/DSPy のバージョンアップで API が変わる可能性。
→ adapter パターンで薄いラッパーを挟み、フレームワーク本体への依存を最小化。
