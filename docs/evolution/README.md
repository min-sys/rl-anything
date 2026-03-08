# 進化ループ — 6レイヤー環境の改善メカニズム

Claude Code 環境（CLAUDE.md / Rules / Skills / Memory / Hooks / Subagents）を**どう改善するか**の調査・設計ドキュメント。

## 背景

[#15](https://github.com/min-sys/rl-anything/issues/15) で環境品質の**測定**手法（10パターン）を提案した。しかし Fitness はフィードバック信号であって、それ自体は環境を改善しない。

```
#15 で解決した問い:         本ドキュメントの問い:
「環境の品質をどう測るか？」  「環境をどう改善するか？」

  ┌─────────┐                ┌─────────┐
  │ Measure  │───────────▶  │  Evolve  │
  │ (観測)   │    gap!       │ (進化)   │
  └─────────┘                └─────────┘
```

## 6レイヤーそれぞれの「進化」とは何か

| レイヤー | 進化 = 何が変わる？ | 難しさ | 現状 |
|---------|-------------------|--------|------|
| **CLAUDE.md** | セクション追加/削除/書き換え | 中（影響範囲広い） | reflect が修正反映のみ |
| **Rules** | ルール追加/修正/削除 | 低（1ルール3行） | discover 提案 + prune のみ |
| **Skills** | プロンプト最適化/分割/統合 | 中 | /optimize がある |
| **Memory** | 記憶の追加/修正/削除/再構造化 | 高（正確性が命） | reflect ルーティングのみ |
| **Hooks** | フック追加/パラメータ調整/削除 | 高（壊れると全体影響） | なし |
| **Subagents** | プロンプト改善/ツール構成変更 | 中（独立性高い） | なし |

## 特に難しい問題: レイヤー間の連鎖的影響

```
例: Rule 変更の波及

  Rule を追加: "テストは必ず書く"
      │
      ├──▶ Skill /commit にテスト手順を追加すべき
      ├──▶ CLAUDE.md のワークフローセクションを更新すべき
      ├──▶ Hook に test 実行チェックを追加すべき
      └──▶ Memory に testing 方針を記録すべき

  1箇所変えたら 4箇所に波及する
```

## ドキュメント

| ファイル | 内容 |
|---------|------|
| [research-survey.md](research-survey.md) | 50+ 文献の調査知見サマリ |
| [evolution-patterns.md](evolution-patterns.md) | 10パターンの詳細設計（E1-E10）+ レイヤー別マッピング |
| [comparison.md](comparison.md) | 比較表 + 横断原則 + #15統合 + 実装ロードマップ |

## 10パターン概要

| パターン | 着想元 | 何をするか | コスト |
|---------|--------|-----------|--------|
| E1 Reflective Trajectory | GEPA, ダブルループ学習 | トラジェクトリを反省して改善 | 中 $$ |
| E2 Reconciliation Loop | K8s, GitOps, MRAC | desired/actual の差分を修正 | 低 $ |
| E3 Interleaved Multi-Layer | MASS, 共進化 | 1レイヤーずつ順番に最適化 | 中〜高 $$$ |
| E4 Immune System | 免疫学, カイゼン | 脅威検出→抗体生成 | 低 $ |
| E5 Graduated Autonomy | HITL, Constitutional AI | 信頼度で自律度を調整 | ゼロ〜低 |
| E6 Stigmergic Evolution | Model Swarms, PSO | 痕跡で間接協調 | ゼロ |
| E7 Compiler Pass Pipeline | AFlow, SAMMO | パス順序を探索 | 低〜中 $-$$ |
| E8 Boosted Error Correction | LLMBoost, AdaBoost | 失敗箇所に集中改善 | 中 $$ |
| E9 Market-Based Allocation | Token Auction, DALA | 入札で資源配分 | ゼロ〜低 |
| E10 Viable System Diagnosis | Beer VSM, Ashby | 生存能力を診断 | ゼロ |

## 関連

- [GitHub Issue #16](https://github.com/min-sys/rl-anything/issues/16) — 原本（コメントで詳細）
- [docs/fitness/](../fitness/) — 測定側（#15）
- [roadmap.md](../roadmap.md) — 全体ロードマップ
