## Pre-flight Check

**実行前に `references/pitfalls.md` を読み、Active かつ Pre-flight対応=Yes の項目を確認してください。**

該当する pitfall がある場合は、その回避策を適用してから本タスクを実行してください。

## Self-Update Rules

| 更新対象 | 判断基準 |
|----------|---------|
| `references/pitfalls.md` | エラー発生・リトライ・ユーザー訂正・再発時 |
| `## Success Patterns` | 特に効果的だったアプローチの発見時（最大2件） |
| Pitfall ステータス | ワークフローへの統合完了時に Graduated へ |

## Failure-triggered Learning

以下のトリガーで `references/pitfalls.md` に記録してください。

| トリガー | アクション | ステータス |
|----------|-----------|-----------|
| エラー発生 | 根本原因カテゴリ付きで記録 | Candidate（初回）/ New（2回目同一原因） |
| リトライ発生 | 何が不足していたか記録 | Candidate |
| ユーザー訂正 | 訂正内容と正しいアプローチを記録 | Active（ゲートスキップ） |
| 既知 pitfall 再発 | Avoidance-count をリセット、Last-seen 更新 | 既存ステータス維持 |

**根本原因カテゴリ**: 記録時に以下のいずれかを付与してください。
- `memory`: コンテキスト消失、前の情報の忘却
- `planning`: 手順の誤り、依存関係の見落とし
- `action`: コマンドミス、パラメータ誤り
- `tool_use`: ツール選択ミス、API仕様の誤解
- `context_loss`: 圧縮による情報消失
- `instruction`: スキル指示への違反（MUST/禁止行の読み飛ばし）

## Pitfall Lifecycle Management

```
Candidate → New → Active → Graduated → Pruned
    ↑                ↑
    └─ 初回エラー     └─ ユーザー訂正（ゲートスキップ）
```

- **Candidate**: 初回エラー。Pre-flight 対象外。同一根本原因が2回目で New に昇格
- **New**: 正式 pitfall。Pre-flight 対象外。再発 or ユーザー承認で Active に昇格
- **Active**: Pre-flight 対象（Pre-flight対応=Yes の場合）。Hot 層は上位5件
- **Graduated**: ワークフローに統合済み。Pre-flight 対象外
- **Pruned**: N回連続回避で削除候補

## Success Patterns

<!-- 特に効果的だったアプローチを1-2件記録 -->

_まだ記録がありません。成功パターンを発見したら追記してください。_
