# Phase 4: Prune（淘汰）

不要になったスキル/ルールを検出し、アーカイブを提案する。

## 4つの判断基準

| 基準 | 手法 | 根拠 |
|------|------|------|
| **Dead glob** | rules の `paths:` 対象がどのファイルにもマッチしない | claude-rules-doctor パターン |
| **Zero invocation** | N日間使用ゼロのスキル/ルール | 32世代実験: 使用回数が見えると自然に淘汰が起きる |
| **Duplicate** | 意味的に重複するルール/スキルを検出 | claude-reflect `--dedupe` パターン |
| **Plugin Unused** | プラグインが提供するスキルのうち、プロジェクトで一度も使われていないもの | Usage Registry ベースの cross-PJ 判定 |

### 推薦ラベル判定チェックリスト

Prune 候補に対して以下のラベルを付与:

| ラベル | 条件 | アクション |
|--------|------|-----------|
| `archive` | 30日以上未使用、参照なし | `.claude/rl-anything/archive/` に移動 |
| `merge` | 由来ペア（Reorganize で検出）の統合候補 | 統合案を生成して提案 |
| `keep` | 他スキル/ルールから参照あり、または cross-PJ で使用中 | 淘汰しない |
| `downgrade` | global スキルだが1PJのみで使用 | project スコープへの降格を提案 |

## 淘汰 ≠ 削除

- 「削除」ではなく **「アーカイブ提案」**
- `.claude/rl-anything/archive/` に移動
- 人間が承認して初めて実行
- いつでも復元可能

## 安全設計

| ガード | 内容 |
|--------|------|
| 30日ルール | 最終使用から30日以上経過しないと候補にしない |
| 参照チェック | 他のスキル/ルールから参照されているものは候補にしない |
| memory 除外 | memory/*.md は淘汰対象外（圧縮のみ提案） |
| CLAUDE.md 除外 | CLAUDE.md は淘汰対象外（圧縮のみ提案） |

## 出力例

```
Prune candidates (3):
  1. rules/old-deploy.md — glob matches 0 files [dead glob]
     → archive? [y/N]

  2. skills/legacy-migrate — 0 invocations (60日) [zero invocation]
     → archive? [y/N]

  3. rules/test-order.md ≈ rules/ci-flow.md (87% similar) [duplicate]
     → merge into ci-flow.md? [y/N]
```

## 重複検出の詳細

意味的類似度で判定:

1. 両方のルール/スキルを LLM に投入
2. 「同じ意図を表現しているか」を判定
3. 87% 以上の類似度で候補に
4. 統合案を生成して提案

統合時は、両方の内容を保持しつつ構造的制約（rules: 3行以内、skills: 500行以内）内に収める。
