# Phase 2: Discover（発見）

観測データからスキル/ルール候補を発見する。

## 入力ソース

| ソース | 何がわかるか | 優先度 |
|--------|-------------|--------|
| usage.jsonl | 繰り返しパターン、未使用アーティファクト | 高 |
| errors.jsonl | 「同じエラーが3回以上」→ ルール候補 | 高 |
| rejection_reason (history.jsonl) | 「人間が繰り返し却下するパターン」→ ルール候補 | 高 |
| corrections.jsonl (高信頼度) | 明示的な修正フィードバック | 高 |
| corrections.jsonl | 蓄積された修正フィードバック → ルール/スキル候補 | 中 |
| sessions.jsonl | セッション横断の行動パターン | 中 |
| Session logs (JSONL) | 無意識の癖、フラストレーション | 低（重い） |

## 発見ロジック

### パターン1: 繰り返し行動 → スキル候補

usage.jsonl と sessions.jsonl を横断分析。同じ手順を繰り返していれば自動化候補。

```
検出例:
  「PR作成時に毎回: ブランチ名確認 → diff確認 → gh pr create」が 7回
  → スキル候補: create-pr
```

### パターン2: 繰り返しエラー → ルール候補

errors.jsonl から同じエラーパターンの頻度を集計。

```
検出例:
  「tsc --noEmit でエラー → 修正 → 再実行」が 4回
  → ルール候補: "コード変更後は tsc --noEmit を先に実行"
```

### パターン3: 繰り返し却下 → ルール候補

history.jsonl の rejection_reason を集計。同じ理由が繰り返されるなら、
それは「暗黙のルール」が言語化されていない証拠。

```
検出例:
  rejection_reason: "冗長すぎる" が 4回
  → ルール候補: "スキルの指示文は簡潔に。冗長な前置きを避ける"
```

### パターン4: corrections.jsonl の蓄積 → ルール候補

corrections.jsonl（correction_detect hook + backfill で収集）に蓄積された修正フィードバックが N 件以上になったら、共通の根本原因を抽出してルール候補に。

### パターン5: 修正パターンの取り込み

correction_detect hook が検出した修正パターン（「いや」「no, use X」「actually...」等）を corrections.jsonl から取り込み。

## 候補の分類

| 分類 | 説明 | 例 |
|------|------|------|
| **Contextualized** | 既存スキル/ルールの改善提案。Enrich フェーズで既存との照合後に生成 | 「bot-create に personality 設定チェックを追加」 |
| **Ad-hoc** | 新規スキル/ルール候補。既存に対応がないパターン | 「PR作成の定型手順をスキル化」 |

## トリガー閾値

Homunculus と claude-reflect の実証から:

| 候補タイプ | 閾値 | 根拠 |
|-----------|------|------|
| スキル候補 | 同じパターンが **5回以上** | Homunculus: 5+ instincts でクラスタ |
| ルール候補 | 同じエラー/修正/却下が **3回以上** | claude-reflect: 3件で提案 |
| 観測中 | 閾値未満 | キューに留めて次回の evolve で再評価 |

## 出力例

```
Discoveries (5 candidates):
  [SKILL] 「PR作成の定型手順」 (7回, confidence 0.85)
     → .claude/skills/create-pr/SKILL.md を生成しますか？

  [RULE]  「tsc --noEmit を先に実行」 (4回, confidence 0.72)
     → .claude/rules/pre-build-check.md を生成しますか？

  [RULE]  「テスト前にlint」 (claude-reflect経由, 3件)
     → .claude/rules/lint-before-test.md を生成しますか？

  [RULE]  「冗長な前置きを避ける」 (却下理由から, 4件)
     → .claude/rules/concise-skill-writing.md を生成しますか？

  [RULE]  「エラーハンドリング必須」 (corrections.jsonlから, 3件)
     → .claude/rules/error-handling.md を生成しますか？

Observing (not yet threshold):
  「デプロイ前のチェック手順」 (2回, need 3 more)
  「テストデータの初期化」 (1回, need 4 more)
```

## 生成ルール

スキル/ルール候補を生成する際の構造的制約:

| アーティファクト | 制約 |
|-----------------|------|
| SKILL.md | 500行以下。frontmatter + トリガー + フロー指示 |
| rules/*.md | **3行以内**（rules-style.md と一致）|

制約を超える生成物は reject → 圧縮版を再生成。
