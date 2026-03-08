# 比較表・横断原則・統合提案

> Source: [GitHub Issue #16](https://github.com/min-sys/rl-anything/issues/16) Parts 5, 7

## 10パターンの比較

|  | E1 Reflective | E2 Reconciliation | E3 Interleaved | E4 Immune | E5 Graduated |
|---|---|---|---|---|---|
| **何をするか** | トラジェクトリを反省して改善 | desired/actual の差分を修正 | 1レイヤーずつ順番に最適化 | 脅威検出→抗体生成 | 信頼度で自律度を調整 |
| **フィードバック信号** | 自然言語反省 | diff (構造的差分) | fitness スコア変化量 | corrections パターン | 承認率履歴 |
| **LLM コスト** | 中 $$ | 低 $ | 中〜高 $$$ | 低 $ | ゼロ〜低 |
| **対応レイヤー** | 全6レイヤー | 全6レイヤー | 全6レイヤー | Rules+Skills+Memory | メタレイヤー（制御） |
| **既存資産** | reflect, corrections | audit (#15 Phase 0) | /optimize, discover | hooks, corrections | accept/reject 履歴 |
| **リスク** | 反省の質に依存 | desired state の定義が難 | 計算コスト | 偽陽性 | 自律化の速度制御 |
| **着想元** | GEPA, ダブルループ学習 | K8s, GitOps, MRAC | MASS, 共進化 | 免疫系, カイゼン | HITL, Constitutional |

|  | E6 Stigmergic | E7 Compiler Pass | E8 Boosted Error | E9 Market | E10 VSM |
|---|---|---|---|---|---|
| **何をするか** | 痕跡で間接協調 | パス順序を探索 | 失敗箇所に集中 | 入札で資源配分 | 生存能力を診断 |
| **フィードバック信号** | フェロモン濃度 | fitness 変化量 | エラー重み | 入札額 + ROI | VSM 診断スコア |
| **LLM コスト** | ゼロ | 低〜中 $-$$ | 中 $$ | ゼロ〜低 | ゼロ |
| **対応レイヤー** | 全6レイヤー | 全6レイヤー | Rules+Skills+Hooks | 全6レイヤー | メタレイヤー（診断） |
| **既存資産** | telemetry JSONL | evolve パイプライン | corrections.jsonl | telemetry_query | audit |
| **リスク** | 蒸発率の調整が難 | 探索コスト | 過剰適合 | 入札関数の設計 | 抽象的すぎる危険 |
| **着想元** | Model Swarms, PSO | AFlow, SAMMO | LLMBoost, AdaBoost | Token Auction, DALA | Beer VSM, Ashby |

## ポジショニングマップ

```
          反応的 ◀──────────────────────────▶ 予防的
          (問題が起きてから)                    (問題が起きる前に)

  安い    E4 Immune         E2 Reconciliation
  │       E5 Graduated      E10 VSM Diagnosis
  │       E6 Stigmergic     E9 Market
  │
  │       E1 Reflective     E7 Compiler Pass
  │       E8 Boosted
  │
  高い    E3 Interleaved

  ←─── 個別レイヤー ────→←── レイヤー横断 ──→
```

## E1-E5 と E6-E10 の関係

E6-E10 は独立パターンではなく、E1-E5 を**補完・強化**する関係にある:

```
E1 Reflective ◀──── E8 Boosted Error
              反省の対象をエラー重み付きで選択

E2 Reconciliation ◀──── E10 VSM Diagnosis
              desired state を VSM の5システムで体系化

E3 Interleaved ◀──── E7 Compiler Pass + E9 Market
              レイヤー選択をパス順序探索 + 入札で最適化

E4 Immune ◀──── E6 Stigmergic
              脅威シグナルをフェロモン蒸発で自然減衰

E5 Graduated ◀──── E9 Market
              自律度判定に ROI ベースの客観指標を導入
```

---

## #15 (Fitness) との統合

### 測定 × 改善のマッピング

| #15 Phase | Fitness (測定) | E1-E5 (改善) | E6-E10 (強化) |
|-----------|---------------|-------------|--------------|
| Phase 0 | coherence_score() | E2 Reconciliation | **E10 VSM** — 構造を5システムで診断 |
| Phase 1 | telemetry_score() | E4 Immune | **E6 Stigmergic** — テレメトリをフェロモンとして活用 |
| Phase 1 | implicit_reward() | E1 Reflective | **E8 Boosted** — 反省対象をエラー重みで選択 |
| Phase 2 | constitutional_score() | E2 Reconciliation | **E10 VSM** — 原則 = S5 Policy |
| Phase 3 | task_execution_score() | E3 Interleaved | **E7 Compiler Pass** — パス順序を探索 |
| 全 Phase | — | E5 Graduated | **E9 Market** — ROI で自律度判定 |

```
Fitness (#15)                Evolution (#16)
─────────────                ───────────────
Phase 0: coherence ────────▶ E2: drift 検出 → 修正
                             E10: VSM 5システム診断
Phase 1: telemetry ────────▶ E4: パターン → 抗体
                             E6: フェロモン → 間接協調
Phase 1: implicit  ────────▶ E1: 反省 → 改善
                             E8: エラー重み → 集中改善
Phase 2: constitutional ───▶ E2: 原則 → 調停
Phase 3: task exec ────────▶ E3: スコア → レイヤー選択
                             E7: パス順序 → 適応的パイプライン
                   ────────▶ E5 + E9: 自律度 + 資源配分（横断）
```

### レイヤー別 Fitness → Evolution の接続

```json
{
  "overall": 0.78,
  "layers": {
    "claude_md":  {"score": 0.9, "issues": ["3ヶ月更新なし"]},
    "rules":      {"score": 0.7, "issues": ["2件矛盾", "5件未遵守"]},
    "skills":     {"score": 0.85, "issues": ["2件未使用"]},
    "memory":     {"score": 0.6, "issues": ["PJ構造がドリフト"]},
    "hooks":      {"score": 0.8, "issues": ["error hook 未設定"]},
    "subagents":  {"score": 0.75, "issues": ["scorer の精度低下"]}
  },
  "recommended_actions": [
    {"layer": "memory", "action": "drift_fix", "priority": "high"},
    {"layer": "rules", "action": "resolve_conflict", "priority": "medium"}
  ]
}
```

この `recommended_actions` が **evolution ループへの入力** になる。

---

## 横断原則: 10パターンから抽出した7つの教訓

### 原則1: 弱者の価値を捨てるな
> Model Swarms: 初期最弱の56.9%が最終的に最強に

低 fitness の Skill を即座に除去するのは早計。Prune の前に「パーツ分解→良い部分の救出」フェーズを入れるべき。

### 原則2: ノイズに反応するな（タンパリング）
> Deming: 共通原因変動への反応はシステムを悪化させる

fitness スコアの通常変動範囲（管理図: μ ± 2σ）を設定し、範囲内の変動では optimize を走らせない。**今すぐ実装可能**で高インパクト。

### 原則3: 制御の多様性 ≥ 問題の多様性
> Ashby の必要多様性の法則

audit が N 種類の問題を検出するなら、evolve は N 種類以上の修正アクションを持つ必要がある。

### 原則4: 痕跡は蒸発すべし
> Stigmergy: フェロモンは時間とともに蒸発する

古いテレメトリデータと新しいデータを同等に扱うのは間違い。半減期ベースの減衰重みを導入する。

### 原則5: パス順序は性能を決定する
> AFlow (ICLR 2025 Oral): 順序探索で 5.7% 改善

evolve パイプラインの固定順序を、プロジェクト状態に応じて適応的に変更する。

### 原則6: 失敗に集中せよ
> AdaBoost: 各反復が前回の失敗ケースに集中

genetic-prompt-optimizer の変異を均一ではなく、corrections.jsonl の頻出パターンに重み付けする。

### 原則7: 制御器はシステムのモデルを含め
> Conant & Ashby の良い制御器定理

evolve が効果的に進化を制御するには、Skill/Rule/Memory の依存関係グラフを明示的に保持する必要がある。

---

## 実装ロードマップ

### Phase A: 既存の evolve を拡張（E4 Immune + E1 Reflective の基盤）

```
A.1  corrections.jsonl の分析強化（パターン分類、頻度カウント）
A.2  既存 reflect をダブルループ対応に拡張
     （同種 correction 3+ 回 → Rule/Skill 再設計提案）
A.3  discover をルール品質改善にも適用
A.4  /optimize を Subagent プロンプトにも適用可能に
```

### Phase B: Reconciliation Loop（E2 の実装）

```
B.1  #15 Phase 0 (coherence) を実装（drift detector として兼用）
B.2  desired state の定義フォーマット
B.3  drift → recommended_actions の自動生成
B.4  波及チェッカー（変更が他レイヤーに影響するかの分析）
B.5  カナリアデプロイ（1 PJ で検証 → 全 PJ に展開）
```

### Phase C: Interleaved Optimization（E3 の実装）

```
C.1  レイヤー別 fitness 関数の整備（#15 のレイヤー別診断）
C.2  バンディットによるレイヤー選択（SEC 方式）
C.3  共生ペア（Rules+Hooks, Skills+Memory）の同時最適化
C.4  evolution round の自動実行パイプライン
```

### Phase D: Graduated Autonomy + 強化パターン（E5-E10）

```
D.1  変更カテゴリ × 承認率の追跡
D.2  信頼度計算ロジック
D.3  E8 Boosted: corrections をエラー重みで分析
D.4  E9 Market: 改善 ROI 追跡と入札関数
D.5  E6 Stigmergic: テレメトリの半減期ベース減衰
D.6  E10 VSM: 必要多様性の監査
D.7  E7 Compiler Pass: パス順序の適応的選択
```
