# Roadmap

rl-anything の将来計画。現在の実装状況は [README.md](../README.md) を参照。

---

## To-be: 理想の姿

6レイヤー（CLAUDE.md / Rules / Skills / Memory / Hooks / Subagents）が **自律的に進化し続ける** 環境。

```
┌─────────────────────────────────────────────────────────┐
│                    理想の進化ループ                       │
│                                                         │
│   Observe ──▶ Measure ──▶ Diagnose ──▶ Evolve ──┐      │
│       ▲        (#15)       (VSM)       (#16)     │      │
│       │                                          │      │
│       └──────────────────────────────────────────┘      │
│                                                         │
│   6レイヤーすべてが:                                     │
│   ✓ 品質を測定できる（レイヤー別 fitness）               │
│   ✓ 問題を自動検出できる（drift, 脅威, 劣化）           │
│   ✓ 改善案を自動生成できる（反省, 調停, 直接パッチ最適化）│
│   ✓ 安全に自動適用できる（信頼度ベースの段階的自律化）  │
└─────────────────────────────────────────────────────────┘
```

## As-is: 現状

Skill の最適化だけが完全なループを持ち、他の5レイヤーは進化メカニズムが不足している。

| レイヤー | 観測 | 測定 | 進化 | 状態 |
|---------|:----:|:----:|:----:|------|
| **Skills** | ✅ usage.jsonl | ✅ skill_quality | ✅ /optimize | **完全ループ** |
| **Rules** | ✅ corrections | ✅ diagnose (orphan/stale) | △ discover 提案 | 観測+診断あり、進化は提案のみ |
| **Memory** | △ 参照なし | ✅ diagnose (stale/duplicate) | △ reflect ルーティング | 診断追加、進化は手動 |
| **Hooks** | ✅ 自己記録 | △ diagnose (設定チェック) | ✗ なし | 観測+簡易診断 |
| **CLAUDE.md** | ✗ なし | ✅ diagnose (phantom/section) | △ reflect 反映のみ | 診断追加、進化は手動 |
| **Subagents** | △ 一部 | ✗ なし | ✗ なし | 未着手 |

**できていること**: 7 hooks による観測、14 スキルによるパイプライン、Skill の直接パッチ最適化、全レイヤーの診断（Coherence Score + layer_diagnose）、テレメトリ駆動の効果測定（Telemetry Score + Environment Fitness）、原則ベースの LLM Judge 評価（Constitutional Score + Chaos Testing）
**できていないこと**: 自己進化

## Problem: 埋めるべきギャップ

```
         理想                    現状                 ギャップ
         ────                    ────                 ────────
測定     全レイヤーの fitness     Skill のみ        ──▶ Gap 1: 環境全体の測定 (#15)
進化     全レイヤーが自律進化     Skill の /optimize ──▶ Gap 2: 進化メカニズム (#16)
スケール 大規模 Skill にも対応   MPO コール爆発    ──▶ Gap 3: 大規模最適化 (#13)
自動化   ゼロタッチ実行          手動 /evolve       ──▶ Gap 4: 自動トリガー
健全性   自動で肥大化を防止      audit レポートのみ ──▶ Gap 5: 自動圧縮
共有     PJ 間でスキルを共有     PJ ごとに独立     ──▶ Gap 6: Plugin Bundling
```

## Solution: ロードマップ

ギャップを「安価な proxy から始めて段階的に高精度へ」の原則で埋めていく。

### 全体像

```
Phase 0        Phase 1        Phase 2        Phase 3
構造品質        行動実績        原則評価        タスク実行
(静的分析)     (テレメトリ)    (LLM Judge)    (実行+進化)
コスト:ゼロ    コスト:ゼロ     コスト:低       コスト:高
   │              │              │              │
   ▼              ▼              ▼              ▼
┌──────┐     ┌──────┐      ┌──────┐      ┌──────┐
│#15   │     │#15   │      │#15   │      │#15   │
│測定  │────▶│測定  │─────▶│測定  │─────▶│測定  │
│      │     │      │      │      │      │      │
│#16   │     │#16   │      │#16   │      │#16   │
│進化  │────▶│進化  │─────▶│進化  │─────▶│進化  │
└──────┘     └──────┘      └──────┘      └──────┘
  E2,E10       E1,E4,E6      E2,E7         E3,E8,E9
 調停+診断    反省+免疫+痕跡  調停+パス     層間+集中+市場
```

### Gap 1: 環境全体の Fitness 評価 ([#15](https://github.com/min-sys/rl-anything/issues/15))

「環境の品質をどう測るか？」— 10パターン (P1-P10) のフェーズドアプローチ。

| Phase | 内容 | コスト | 状態 | change 名 |
|-------|------|--------|------|-----------|
| 0 | 構造の整合性チェック（Coherence + KG Quality） | ゼロ | **完了** | `env-coherence-score` |
| 1 | テレメトリ駆動の効果測定（Telemetry + Implicit Reward） | ゼロ | **完了** | `env-telemetry-score` |
| 2 | 原則ベースの自動評価（Constitutional + Chaos） | LLM | **完了** | `env-constitutional-eval` |
| 3 | タスク実行による成果測定（Task Exec + Eureka + Elo） | LLM | 未着手 | Phase 0-2 安定後に計画 |

詳細は [docs/fitness/](./fitness/) を参照。

### Gap 2: 環境全体の進化ループ ([#16](https://github.com/min-sys/rl-anything/issues/16))

「環境をどう改善するか？」— Pattern B（Observe → Diagnose → Compile）ベースの段階的実装。

| Phase | 内容 | パターン | 状態 | change 名 |
|-------|------|---------|------|-----------|
| 1 | **パイプライン簡素化** — 8ステージ→3ステージ（Diagnose→Compile→Housekeeping） | #21 Pattern B | **完了** | `2026-03-08-simplify-pipeline-pattern-b` |
| 2 | **全層 Diagnose** — Skill 以外のレイヤー（Rules/Memory/Hooks/CLAUDE.md）も診断対象に。Hooks はテレメトリデータ不足のため設定存在チェックのみ（テレメトリベース診断は Gap 1 Ph1 以降で対応） | E2 + E10 VSM | **完了** | `all-layer-diagnose` |
| 3 | **全層 Compile** — 診断結果から全レイヤーのパッチを生成 | E3 + E7 Compiler Pass | **完了** | `all-layer-compile` |
| 4 | **自己進化** — パイプライン自身の改善を自律的に提案（trajectory分析+EWA calibration+adjustment proposals） | E5-E10 | **完了** | `self-evolution` |
| 5 | **Graduated Autonomy** — 信頼度ベースの段階的自律化 | E1 Reflective + E4 Immune | 未着手 | Phase 4 完了後 |

詳細は [docs/evolution/](./evolution/) を参照。

### Gap 3: 大規模スキル最適化 ([#13](https://github.com/min-sys/rl-anything/issues/13))

#19 により GA 廃止、DirectPatchOptimizer に置換済み。LLM 1パスパッチにより MPO コール数問題は解消。
残課題: long skill での survival rate 改善（pitfall patterns + regression gate 強化で対応中）。

### Gap 4: 自動トリガー（Zero-Touch Auto Evolve） — **完了**

`auto-evolve-trigger` change で実装済み。`scripts/lib/trigger_engine.py` が4条件（セッション数/経過日数/corrections蓄積/audit overdue）を評価し、session_summary (Stop hook) → pending-trigger.json → restore_state (SessionStart hook) の遅延配信でユーザーに提案する。

| トリガー | タイミング | デフォルト閾値 | 状態 |
|---------|-----------|---------------|------|
| セッション数 | セッション終了時 | ≥ 10 | **実装済み** |
| 経過日数 | セッション終了時 | ≥ 7日 | **実装済み** |
| corrections 蓄積 | correction 検出時 | ≥ 10件 | **実装済み** |
| audit overdue | セッション終了時 | ≥ 30日 | **実装済み** |
| スキル変更検出 | セッション終了時 | git diff | **実装済み** |

設定は `evolve-state.json` の `trigger_config` でカスタマイズ可能。全トリガーは「提案」のみ（自動実行は Gap 2 Ph5 Graduated Autonomy で対応）。

### Gap 5: 自動圧縮トリガー — **完了**

`auto-compression-trigger` change で実装済み。`trigger_engine.py` に `_evaluate_bloat()` を追加し、`bloat_check()` の結果に基づいてセッション終了時に肥大化を自動検出して `/rl-anything:evolve` を提案する。

| トリガー | 閾値 (bloat_control.BLOAT_THRESHOLDS) | 状態 |
|---------|---------------------------------------|------|
| MEMORY.md 行数超過 | > 150行 | **実装済み** |
| rules 総数超過 | > 100 | **実装済み** |
| skills 総数超過 | > 30 | **実装済み** |
| CLAUDE.md 行数超過 | > 150行 | **実装済み** |

設定: `trigger_config.triggers.bloat.enabled` で有効/無効を制御。閾値は `bloat_control.BLOAT_THRESHOLDS` が single source of truth。クールダウンは reason `"bloat"` で24h。

詳細は [bloat-control.md](./evolve/bloat-control.md) を参照。

### Gap 6: Plugin Bundling

evolve が「常に一緒に使われるスキル群」を検出したら plugin 化を提案する機能。運用データが十分に蓄積された後に着手予定。

詳細は [bloat-control.md](./evolve/bloat-control.md#layer-3-plugin-bundling将来計画--未実装) を参照。

---

## 優先順位と依存関係

```
                    ┌───────────────┐
                    │ Gap 1: 測定   │ ← 最初に着手
                    │ #15 Phase 0-1 │   （コストゼロ、全ての基盤）
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
     ┌────────────┐  ┌───────────┐  ┌───────────┐
     │ Gap 2: 進化│  │Gap 3: MPO │  │Gap 5: 圧縮│
     │ #16 Ph A-B │  │   #13     │  │ ✅ 完了   │
     └──────┬─────┘  └───────────┘  └───────────┘
            │                 独立して並行可能
            ▼
     ┌────────────┐
     │ Gap 4: 自動│ ✅ 完了
     │ トリガー   │
     └──────┬─────┘
            ▼
     ┌────────────┐
     │ Gap 6:     │ ← 運用データ蓄積後
     │ Bundling   │
     └────────────┘
```

**今すぐ始められること**: Gap 2 Phase 5（graduated-autonomy）— 信頼度ベースの段階的自律化。Gap 1 Phase 3（env-task-exec-eval）— タスク実行による成果測定。

---

## Change 作成ガイド

各 Gap/Phase を OpenSpec change として管理する。change の命名と作成順序は以下の通り。

### 推奨する change 作成順序

```
1. env-coherence-score        ← Gap 1 Ph0 ✅ 完了
2. all-layer-diagnose          ← Gap 2 Ph2 ✅ 完了
3. env-telemetry-score         ← Gap 1 Ph1 ✅ 完了
4. all-layer-compile           ← Gap 2 Ph3 ✅ 完了
5. env-constitutional-eval     ← Gap 1 Ph2 ✅ 完了
6. auto-evolve-trigger         ← Gap 4 (Gap 1+2 安定後) ✅ 完了
7. auto-compression-trigger    ← Gap 5 ✅ 完了
8. env-task-exec-eval          ← Gap 1 Ph3 (Ph2 安定後)
9. self-evolution              ← Gap 2 Ph4 ✅ 完了
10. graduated-autonomy         ← Gap 2 Ph5 (Ph4 完了後)
11. plugin-bundling            ← Gap 6 (運用データ蓄積後)
```

### change 作成の判断基準

| 条件 | アクション |
|------|-----------|
| 前の Phase の change が archive 済み | 次の Phase の change を `/openspec-propose` で作成 |
| 前の Phase の運用で知見が得られた | 知見を反映して次の change の scope を調整 |
| 独立した Gap（3, 5）| 依存なし、いつでも change 作成可能 |
| Phase 2 以降（LLM コスト発生）| Phase 0-1 の運用実績を見てから scope を決定 |
