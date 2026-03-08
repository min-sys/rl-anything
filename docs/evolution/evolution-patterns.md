# 10の進化パターン — 詳細設計

> Source: [GitHub Issue #16](https://github.com/min-sys/rl-anything/issues/16) Parts 3, 4, 6

調査知見を統合し、6レイヤーの進化ループを閉じる10パターンを提案する。E1-E5 は AI/ML・制御理論・組織学習寄り、E6-E10 は群知能・コンパイラ理論・統計学・経済学・サイバネティクス寄り。

---

## Pattern E1: Reflective Trajectory Evolution — トラジェクトリ反省による進化

```
着想: GEPA (ICLR 2026), Meta-Rewarding LMs, 組織学習のダブルループ
═══════════════════════════════════════════════════════════════════

「スコアが低い」ではなく「なぜ失敗したか」を言語化して改善する

┌──────────────────────────────────────────────────────┐
│  Session 実行                                        │
│  [Rule A 適用] → [Skill B 使用] → [修正発生] → 完了  │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  トラジェクトリ収集                                    │
│  usage.jsonl + corrections.jsonl + sessions.jsonl    │
│  → 「何が起きたか」の時系列再構成                     │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  LLM 反省 (Reflect)                                  │
│                                                      │
│  "Session #42 で /commit Skill 使用後にユーザーが     │
│   テスト追加を手動で行った。Rule 'テスト必須' が      │
│   /commit Skill に反映されていないことが原因。        │
│   推奨: /commit Skill にテスト実行ステップを追加"    │
│                                                      │
│  ★ スカラースコアではなく自然言語の診断              │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  改善アクション生成                                    │
│  1. Skill 修正案を生成（/commit にテスト手順追加）    │
│  2. 関連レイヤーの波及チェック                         │
│  3. 人間承認                                         │
│  4. 適用 + 回帰テスト                                │
└──────────────────────────────────────────────────────┘
```

**なぜこれが最も重要か**:
- GEPA の知見: 自然言語反省は RL の **35 倍サンプル効率**
- 既存の `reflect` スキルの自然な拡張
- corrections.jsonl のデータを最大限活用
- ダブルループ学習: 同じ修正が 3+ 回 → ルール自体を再設計

**レイヤー別適用**:

| レイヤー | 反省のトリガー | 改善アクション |
|---------|-------------|-------------|
| CLAUDE.md | 方針と実態の乖離が繰り返し検出 | セクション更新提案 |
| Rules | 同種 correction が 3+ 回 | Rule 修正/新規提案 |
| Skills | Skill 使用後に修正が頻発 | Skill 内容の修正案 |
| Memory | Memory 参照後に誤った判断 | Memory エントリ修正 |
| Hooks | Hook 発火後にエラー | Hook パラメータ調整 |
| Subagents | Subagent 出力の品質低下 | プロンプト修正案 |

**既存資産**: reflect スキル、corrections.jsonl、usage.jsonl、sessions.jsonl

---

## Pattern E2: Reconciliation Loop — 宣言的状態への自動調停

```
着想: K8s Self-Healing, GitOps, Agentic Operator, 適応制御 (MRAC)
═══════════════════════════════════════════════════════════════════

「あるべき状態」を宣言し、ドリフトを自動検出・修正する

┌──────────────────┐
│  Desired State    │ ← CLAUDE.md + Rules + Constitutional 原則
│  (あるべき姿)     │    「テストは必ず書く」
└────────┬─────────┘    「日本語で応答する」
         │              「LLM コールを最小化する」
         │  定期的に比較
         ▼
┌──────────────────┐
│  Actual State     │ ← 実際の環境スキャン
│  (実際の姿)       │    Skills: /commit にテスト手順なし
└────────┬─────────┘    Hooks: test 実行 hook なし
         │
         ▼
┌──────────────────┐
│  Drift Detection  │ ← 差分を検出
│  (ドリフト検出)   │
│                   │    Gap 1: Skill /commit ← テスト手順なし
│                   │    Gap 2: Hooks ← test hook なし
│                   │    Gap 3: Memory ← テスト方針なし
└────────┬─────────┘
         ▼
┌──────────────────┐
│  Reconciliation   │ ← 差分を修正するアクションを生成
│  (調停)           │
│                   │    [人間承認] → [適用] → [再スキャンで確認]
└──────────────────┘
```

**K8s との対比**:

| K8s | rl-anything |
|-----|-------------|
| Deployment YAML | CLAUDE.md + Rules（desired state） |
| Running Pods | Skills + Memory + Hooks（actual state） |
| Controller | reconciliation engine（新規） |
| kubectl diff | coherence checker (#15 Phase 0) |

**なぜこれが強力か**:
- **冪等**: 何度実行しても同じ結果
- **自己修復**: ドリフトが発生するたびに自動修正
- **#15 Phase 0 (Coherence) がそのまま drift detector になる**

**既存資産**: audit, #15 Phase 0 (coherence)

---

## Pattern E3: Interleaved Multi-Layer Optimization — 層間インターリーブ最適化

```
着想: MASS (Google 2025), 生物学的共進化, ゲームバランス調整
═══════════════════════════════════════════════════════════════════

6レイヤーを1つずつ順番に最適化し、他を固定する

Round 1: CLAUDE.md ★最適化 → Rules 固定 → Skills 固定 → ...
Round 2: CLAUDE.md 固定 → Rules ★最適化 → Skills 固定 → ...
  ...
Round 7: 環境全体を再評価 → 次の最適化対象をバンディットで選択
```

**バンディットによるレイヤー選択 (SEC)**:

```python
layer_selector = ThompsonSampling(
    arms=["claude_md", "rules", "skills", "memory", "hooks", "subagents"]
)

for round in evolution_rounds:
    layer = layer_selector.select()
    before = compute_layer_fitness(layer)
    evolve_layer(layer)
    after = compute_layer_fitness(layer)
    layer_selector.update(layer, after - before > 0)
```

**共生ペアの考慮**:
```
Rules + Hooks      → Rule を変えたら Hook も調整
Skills + Memory    → Skill が参照する Memory も更新
CLAUDE.md + Rules  → 方針を変えたら Rule も追従
```

**既存資産**: /optimize, discover, Thompson Sampling

---

## Pattern E4: Immune System — 脅威検出と抗体生成

```
着想: 適応免疫系, Chaos Engineering, Red Teaming, カイゼン
═══════════════════════════════════════════════════════════════════

問題を「脅威」として検出し、「抗体」（修正ルール/スキル）を生成する

┌────────────────────────────────────────────────────────┐
│  自然免疫（即座の反応）= Rules + Hooks                  │
│  ★ 既に hooks で実装済み。LLM コストゼロ。              │
└────────────────────────┬───────────────────────────────┘
                         │ 新種の脅威（未知パターン）
                         ▼
┌────────────────────────────────────────────────────────┐
│  適応免疫（学習して対応）= Skills + Memory + Subagents  │
│  1. 抗原提示: 新しいエラーパターンを分析               │
│  2. クローン選択: 複数の修正案を生成（遺伝的多様性）   │
│  3. 負の選択: 既知の正常セッションで回帰テスト         │
│  4. メモリ B 細胞: 修正パターンを Memory に記録         │
└────────────────────────────────────────────────────────┘
```

**負の選択が鍵**: 新しい Rule/Skill を**既存の正常セッションで回帰テスト**し、正常ケースを壊すものは除去する。

**既存資産**: hooks, corrections.jsonl, discover, optimize

---

## Pattern E5: Graduated Autonomy — 段階的自律化

```
着想: HITL ベストプラクティス, Constitutional AI, SEAgent カリキュラム
═══════════════════════════════════════════════════════════════════

改善アクションの信頼度に応じて自律度を段階的に上げる

Level 0: 完全手動 — 全変更に人間承認
Level 1: 提案モード — 候補を提示し人間が accept/reject（現在の evolve）
Level 2: 信頼度ベースの自動承認 — 高信頼度+低リスク→自動適用
Level 3: 完全自律（安全なカテゴリのみ）— stale Memory 削除等
```

**信頼度の計算**:
```python
confidence = f(
    change_type,              # Rule削除 vs Memory更新 vs Skill修正
    historical_approval_rate, # このタイプの過去の承認率
    blast_radius,             # 影響を受けるレイヤー数
    regression_risk,          # 回帰テスト結果
)

if confidence > 0.9 and blast_radius <= 1:
    auto_apply(change)
elif confidence > 0.7:
    propose_with_diff(change)
else:
    propose_with_explanation(change)
```

**レベル昇格条件**:
- Level 0 → 1: ユーザーが evolve を 3 回以上使用
- Level 1 → 2: 同カテゴリの変更が 10 回連続承認
- Level 2 → 3: 自動適用が 30 回連続で回帰なし

**既存資産**: accept/reject 履歴

---

## Pattern E6: Stigmergic Evolution — フェロモン痕跡による間接協調進化

```
着想: Model Swarms (ICML 2025), Emergent Collective Memory (2025),
      SwarmPrompt (ICAART 2025)
═══════════════════════════════════════════════════════════════════

「直接指示」ではなく「環境に残された痕跡」から進化方向を決定する

┌───────────────────────────────────────────────────────────┐
│  Layer A: Skill 実行 → フェロモン堆積                      │
│  usage.jsonl に痕跡: {skill, outcome, context}             │
└──────────────────────────┬────────────────────────────────┘
                           │ フェロモン蒸発 (30日で半減)
                           ▼
┌───────────────────────────────────────────────────────────┐
│  環境（共有媒体）                                          │
│  usage.jsonl    ←── 使用頻度フェロモン (半減期 30日)       │
│  errors.jsonl   ←── エラーフェロモン (半減期 7日)          │
│  corrections.jsonl ← 修正フェロモン (半減期 60日)          │
│  workflows.jsonl ← ワークフローフェロモン (半減期 90日)    │
└──────────────────────────┬────────────────────────────────┘
                           │ フェロモン読み取り
                           ▼
┌───────────────────────────────────────────────────────────┐
│  discover / evolve が痕跡を解釈                            │
│  1. 高フェロモン濃度パターン → 統合 Skill 提案             │
│  2. 負フェロモン回避 → 問題 Skill を優先改善               │
│  3. 弱→強遷移 (Model Swarms: 56.9%)                       │
└───────────────────────────────────────────────────────────┘
```

**レイヤー別適用**:

| レイヤー | 堆積するフェロモン | 読み取るフェロモン | 進化アクション |
|---------|------------------|------------------|-------------|
| CLAUDE.md | — | 全フェロモンの集約 | 方針更新提案 |
| Rules | 遵守/違反パターン | Skill のエラーフェロモン | 違反が多い領域に Rule 追加 |
| Skills | 使用頻度 + 成功率 | 修正フェロモン | 負フェロモン集中 Skill を優先改善 |
| Memory | 参照頻度 | ワークフローフェロモン | 未参照エントリの蒸発 |
| Hooks | 発火率 + エラー率 | 使用フェロモン | 発火しない Hook の除去 |
| Subagents | 呼び出し頻度 + 品質 | エラーフェロモン | 低品質 Subagent のプロンプト改善 |

**既存資産**: usage.jsonl, errors.jsonl, corrections.jsonl, workflows.jsonl, telemetry_query.py

---

## Pattern E7: Compiler Pass Pipeline — 合成可能な最適化パスの連鎖

```
着想: AFlow (ICLR 2025 Oral), SAMMO (EMNLP 2024), Compiler-R1 (NeurIPS 2025)
═══════════════════════════════════════════════════════════════════

固定パイプラインではなく、合成可能なパスの最適な順序を探索する

パス定義（各パスは冪等・合成可能・独立テスト可能）:
  P1: DeadCodeElimination  — 未使用 Skill/Rule の除去
  P2: ConstantFolding      — ハードコード値の外部化
  P3: InlineExpansion      — 短い Rule を Skill に統合
  P4: LoopUnrolling        — 繰り返しパターンの Skill 化
  P5: CommonSubexpression  — 重複 Skill/Rule の統合
  P6: StrengthReduction    — 高コスト表現の低コスト化
  P7: RegisterAllocation   — Memory スロットの最適配分
  P8: PeepholeOptimization — 局所的な表現改善

パス順序の探索（AFlow の MCTS アプローチ）:
  固定順序:  P1 → P5 → P3 → P2 → P8
                  vs
  探索順序:  P5 → P1 → P8 → P3 → P2  ← MCTS が発見

  AFlow の知見: 探索順序は固定比 5.7% 改善
  Compiler-R1: RL でパス順序を学習 → 8.46% 改善
```

**プロジェクト状態に応じた適応的パス選択**:
- 新規 PJ: P4(パターン Skill 化) → P8(表現改善) 中心
- 成熟 PJ: P1(除去) → P5(統合) → P6(効率化) 中心
- 肥大 PJ: P1(除去) → P5(統合) → P7(Memory 整理) 中心

**現在の evolve との対応**:

| evolve フェーズ | コンパイラパス相当 |
|---------------|------------------|
| Discover | P4 LoopUnrolling |
| Enrich | P8 Peephole |
| Optimize | P6 StrengthReduction |
| Reorganize | P3 InlineExpansion |
| Prune | P1 DeadCodeElimination + P5 CSE |

**既存資産**: evolve パイプライン, audit, prune

---

## Pattern E8: Boosted Error Correction — エラー重み付き反復改善

```
着想: LLMBoost (2025), Boosted Prompt Ensembles (2023),
      Boosting of Thoughts (ICLR 2024), AdaBoost (1997)
═══════════════════════════════════════════════════════════════════

「全体を均等に改善」ではなく「最も失敗する箇所に集中」して反復する

Round 1: 全 Skill/Rule を均等重みで評価
  Skill A: ✓ 成功   weight: 1.0 → 0.5 (下げる)
  Skill B: ✗ 失敗   weight: 1.0 → 2.0 (上げる)  ← 注力対象
  Rule X:  ✗ 失敗   weight: 1.0 → 2.0            ← 注力対象

Round 2: 高重み（=前回失敗）に集中して改善
  Skill B の失敗分析 → 変異方向: エラーハンドリング強化に特化

Round 3: さらに残る高重みに集中
  ...

最終: 各 Round の最良を重み付き投票で統合
```

**AdaBoost 式の重み更新ルール**:

```python
def update_weights(components, outcomes):
    for comp, outcome in zip(components, outcomes):
        if outcome == "fail":
            comp.weight *= 2.0
        elif outcome == "success":
            comp.weight *= 0.5
    total = sum(c.weight for c in components)
    for c in components:
        c.weight /= total
```

**レイヤー別適用**:

| レイヤー | 「失敗」の定義 | 重み増加トリガー |
|---------|-------------|---------------|
| Rules | correction で上書き | 同 Rule 違反が 2+ 回 |
| Skills | 使用後に修正発生 | 修正率 > 30% |
| Memory | 参照後に誤判断 | 誤判断率が上昇 |
| Hooks | 発火後にエラー | エラー率 > 10% |
| CLAUDE.md | 方針に反する行動 | 乖離検出 3+ 回 |

**既存資産**: corrections.jsonl, genetic-prompt-optimizer, fitness 関数

---

## Pattern E9: Market-Based Resource Allocation — オークション機構による進化資源配分

```
着想: Token Auction (WWW 2024 Best Paper), DALA (2025),
      Market Making for Multi-Agent (2025), VCG メカニズム
═══════════════════════════════════════════════════════════════════

「固定予算配分」ではなく「入札による動的配分」で進化資源を最適化する

入札フェーズ:
  Skill A: bid = 0.8  (fitness 0.4, 修正多数, 使用頻度高)
  Skill B: bid = 0.2  (fitness 0.9, 修正なし, 安定)
  Rule X:  bid = 0.6  (違反率 40%, 新しい, 改善余地大)

VCG オークション (予算: LLM コール 10回分):
  Skill A: 4 コール (最高入札)
  Rule X:  3 コール
  Skill B: 1 コール (最低入札)

実行 + 市場フィードバック:
  ROI が次回の入札関数パラメータを更新
```

**入札関数の設計**:

```python
def compute_bid(component, telemetry, days=30):
    improvement_room = 1.0 - component.fitness_score
    usage_frequency = telemetry.usage_rate(component, days)
    failure_rate = telemetry.failure_rate(component, days)
    dependents = len(component.dependent_components)

    bid = (improvement_room * 0.3
           + usage_frequency * 0.2
           + failure_rate * 0.3
           + min(dependents / 10, 0.2))
    return bid
```

**既存資産**: telemetry_query.py, fitness 関数, audit の severity 分類

---

## Pattern E10: Viable System Diagnosis — 組織サイバネティクスによる生存能力診断

```
着想: Stafford Beer の Viable System Model (1972),
      Ashby の必要多様性の法則 (1956), 良い制御器定理 (1970),
      MAPE-K (IBM 2003), AWARE (FSE 2025)
═══════════════════════════════════════════════════════════════════

環境を「生存可能なシステム」として診断し、欠損を特定する

Beer の VSM → Claude Code 環境マッピング:

  S5: Policy (アイデンティティ)    → CLAUDE.md の最上位方針
  S4: Intelligence (未来適応)      → discover + research 機能
  S3: Control (内部統制)           → audit + evolve パイプライン
  S2: Coordination (レイヤー間調整) → Hooks + Rules
  S1: Operations (価値を生む実行)   → Skills + Subagents
```

**3つのサイバネティック法則の適用**:

1. **必要多様性** (Ashby 1956): audit が検出する問題の種類数 ≤ 修正アクション数か？
2. **良い制御器定理** (Conant & Ashby 1970): evolve は依存関係グラフを保持しているか？
3. **共通/特殊原因区別** (Deming): fitness スコアの変動は管理図 (μ ± 2σ) 内か？

**VSM 診断スコア**:

```python
def vsm_diagnosis(project_dir):
    return {
        "s1_operations": check_skill_coverage(),
        "s2_coordination": check_layer_consistency(),
        "s3_control": check_audit_remediation_parity(),
        "s4_intelligence": check_discover_alignment(),
        "s5_policy": check_claude_md_completeness(),
        "requisite_variety": count_problems() <= count_actions(),
    }
```

**既存資産**: audit (S3相当), discover (S4相当), CLAUDE.md (S5相当), Hooks (S2相当)

---

## レイヤー別マッピング

### レイヤー × パターンの適用マップ

|  | E1 Reflective | E2 Reconciliation | E3 Interleaved | E4 Immune | E5 Graduated |
|---|---|---|---|---|---|
| **CLAUDE.md** | 方針と実態の乖離を反省 | desired state の定義元 | Round 1 で最適化 | — | Level 2+ で自動更新 |
| **Rules** | corrections 3+ 回でルール再設計 | drift から新 Rule 生成 | Round 2 で最適化 | 自然免疫の本体 | Level 1 で提案 |
| **Skills** | 使用後修正パターンから改善 | desired vs actual の差分修正 | Round 3 で最適化 | クローン選択で候補生成 | Level 2 で高信頼度は自動 |
| **Memory** | 誤判断の原因をドリフトに帰属 | PJ構造との drift 検出 | Round 4 で最適化 | メモリ B 細胞 | Level 2 で stale 削除自動 |
| **Hooks** | Hook 発火後エラーの原因分析 | 設定の過不足を検出 | Round 5 で最適化 | 自然免疫の検出器 | Level 0-1 のみ（リスク高） |
| **Subagents** | 出力品質低下の原因反省 | 期待出力との diff | Round 6 で最適化 | 適応免疫の実行器 | Level 1 で提案のみ |

|  | E6 Stigmergic | E7 Compiler Pass | E8 Boosted | E9 Market | E10 VSM |
|---|---|---|---|---|---|
| **CLAUDE.md** | 全フェロモン集約で方針更新 | — | 乖離検出で重み増加 | — | S5 Policy 診断 |
| **Rules** | 違反フェロモンで追加 | P3 InlineExpansion | 違反率で重み増加 | 改善余地で入札 | S2 Coordination 診断 |
| **Skills** | 負フェロモンで優先改善 | P6 StrengthReduction | 修正率で重み増加 | ROI で配分 | S1 Operations 診断 |
| **Memory** | 未参照エントリ蒸発 | P7 RegisterAllocation | 誤判断で重み増加 | — | S4 Intelligence 診断 |
| **Hooks** | 未発火 Hook 除去 | — | エラー率で重み増加 | — | S2 Coordination 診断 |
| **Subagents** | 品質フェロモンで改善 | — | 品質低下で重み増加 | ROI で配分 | S1 Operations 診断 |

### Cross-Layer 進化: 波及チェッカー

```
         CLAUDE.md ──defines──▶ Rules
              │                  │
         references          enforced-by
              │                  │
              ▼                  ▼
         Skills ◀──uses──── Memory
              │                  │
         triggers           recorded-by
              │                  │
              ▼                  ▼
          Hooks ◀──monitors── Subagents

変更波及ルール:
  CLAUDE.md 変更 → Rules, Skills, Memory をチェック
  Rule 変更     → Skills, Hooks をチェック
  Skill 変更    → Memory, Subagents をチェック
  Memory 変更   → Skills をチェック
  Hook 変更     → (影響は局所的)
  Subagent 変更 → (影響は局所的)
```
