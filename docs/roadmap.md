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
│   ✓ 改善案を自動生成できる（反省, 調停, 遺伝的最適化）  │
│   ✓ 安全に自動適用できる（信頼度ベースの段階的自律化）  │
└─────────────────────────────────────────────────────────┘
```

## As-is: 現状

Skill の最適化だけが完全なループを持ち、他の5レイヤーは進化メカニズムが不足している。

| レイヤー | 観測 | 測定 | 進化 | 状態 |
|---------|:----:|:----:|:----:|------|
| **Skills** | ✅ usage.jsonl | ✅ skill_quality | ✅ /optimize | **完全ループ** |
| **Rules** | ✅ corrections | △ audit のみ | △ discover 提案 | 観測はあるが進化が弱い |
| **Memory** | △ 参照なし | ✗ なし | △ reflect ルーティング | ほぼ手動 |
| **Hooks** | ✅ 自己記録 | ✗ なし | ✗ なし | 観測のみ |
| **CLAUDE.md** | ✗ なし | ✗ なし | △ reflect 反映のみ | ほぼ手動 |
| **Subagents** | △ 一部 | ✗ なし | ✗ なし | 未着手 |

**できていること**: 7 hooks による観測、14 スキルによるパイプライン、Skill の遺伝的最適化
**できていないこと**: 環境全体の品質測定、Skill 以外の進化、自動トリガー

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

| Phase | 内容 | コスト | 状態 |
|-------|------|--------|------|
| 0 | 構造の整合性チェック（Coherence + KG Quality） | ゼロ | 未着手 |
| 1 | テレメトリ駆動の効果測定（Telemetry + Implicit Reward） | ゼロ | 未着手 |
| 2 | 原則ベースの自動評価（Constitutional + Chaos） | LLM | 未着手 |
| 3 | タスク実行による成果測定（Task Exec + Eureka + Elo） | LLM | 未着手 |

詳細は [docs/fitness/](./fitness/) を参照。

### Gap 2: 環境全体の進化ループ ([#16](https://github.com/min-sys/rl-anything/issues/16))

「環境をどう改善するか？」— Pattern B（Observe → Diagnose → Compile）ベースの段階的実装。

| Phase | 内容 | パターン | 状態 |
|-------|------|---------|------|
| 1 | **パイプライン簡素化** — 8ステージ→3ステージ（Diagnose→Compile→Housekeeping） | #21 Pattern B | **実装中** |
| 2 | **全層 Diagnose** — Skill 以外のレイヤー（Rules/Memory/Hooks）も診断対象に | E2 + E10 VSM | 未着手 |
| 3 | **全層 Compile** — 診断結果から全レイヤーのパッチを生成 | E3 + E7 Compiler Pass | 未着手 |
| 4 | **自己進化** — パイプライン自身の改善を自律的に提案 | E5-E10 | 未着手 |
| 5 | **Graduated Autonomy** — 信頼度ベースの段階的自律化 | E1 Reflective + E4 Immune | 未着手 |

詳細は [docs/evolution/](./evolution/) を参照。

### Gap 3: 大規模スキル最適化 ([#13](https://github.com/min-sys/rl-anything/issues/13))

#19 により GA 廃止、DirectPatchOptimizer に置換済み。LLM 1パスパッチにより MPO コール数問題は解消。
残課題: long skill での survival rate 改善（pitfall patterns + regression gate 強化で対応中）。

### Gap 4: 自動トリガー（Zero-Touch Auto Evolve）

現状は `/evolve` を手動で呼ぶ必要がある。

| トリガー | タイミング | やること |
|---------|-----------|---------|
| スキル変更検知 | `.claude/skills/*/SKILL.md` 編集時 | `/optimize --dry-run` でスコア計測 |
| セッション終了時 | Claude Code セッション終了時 | git diff で変更スキル検出 |
| 定期スコア計測 | 月1回 | 全スキルスコア計測 → 劣化報告 |
| corrections 蓄積閾値 | N 件蓄積時 | 関連スキルの再最適化提案 |

### Gap 5: 自動圧縮トリガー

bloat check レポートは audit スキルで実装済み。以下は自動化の将来計画:

| トリガー | アクション |
|---------|-----------|
| rules 総数 > 100 | 重複検出 + 統合提案を自動実行 |
| skill 総数 > 30 | 使用頻度分析 + archive 提案を自動実行 |
| MEMORY.md > 150行 | トピック別ファイルへの分割を自動提案 |

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
     │ #16 Ph A-B │  │   #13     │  │ 自動化    │
     └──────┬─────┘  └───────────┘  └───────────┘
            │                 独立して並行可能
            ▼
     ┌────────────┐
     │ Gap 4: 自動│ ← Gap 1+2 が安定してから
     │ トリガー   │
     └──────┬─────┘
            ▼
     ┌────────────┐
     │ Gap 6:     │ ← 運用データ蓄積後
     │ Bundling   │
     └────────────┘
```

**今すぐ始められること**: Gap 1 Phase 0（構造の整合性チェック）— LLM コストゼロ、既存の audit を拡張するだけ。
