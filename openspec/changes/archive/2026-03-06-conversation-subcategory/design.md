## Context

`hooks/common.py` の `PROMPT_CATEGORIES` で `conversation` は11カテゴリの1つとして定義されている。キーワードマッチで分類され、`reclassify.py` の LLM 再分類でも有効なターゲットカテゴリ。`analyze.py` では他カテゴリと同列にカウント表示されるだけで、内訳の洞察がない。

現在の conversation キーワード: `お願い`, `続けて`, `ありがと`, `よろしく`, `はい`, `いいえ`, `ok`, `いいよ`, `やって`, `進めて`, `対応して`

## Goals / Non-Goals

**Goals:**
- conversation を5つのサブカテゴリに細分化し、ユーザー対話パターンの洞察を得る
- 既存データ（`conversation` ラベル）との後方互換を維持
- analyze レポートで集約表示 + 内訳表示

**Non-Goals:**
- 既存の usage.jsonl データの自動マイグレーション（新規記録のみサブカテゴリ化）
- サブカテゴリに基づく自動アクション（将来課題）

## Decisions

### 1. サブカテゴリ体系

`conversation:{subcategory}` のコロン区切りフォーマットを採用。

| サブカテゴリ | キーワード例 | 説明 |
|-------------|-------------|------|
| `conversation:approval` | はい, いいえ, ok, いいよ, よろしく, 採用, accept | 承認・同意（否認含む） |
| `conversation:confirmation` | お願い, やって, 進めて, 対応して, 続けて | 確認応答・実行指示 |
| `conversation:question` | なに, どう, なぜ, 教えて, ？ | 質問 |
| `conversation:direction` | こうして, やめて, 変えて, 代わりに, ではなく | 方針指示・修正依頼 |
| `conversation:thanks` | ありがと, 感謝, サンクス, thx, thanks | 感謝表現 |

**根拠**: 既存 conversation キーワード11個の意味的クラスタリングから5クラスタが自然に分離。`clarification` は `question` と `direction` に吸収。

**採用しないパターン**:
- **(A) 3分類統合案**: response（approval+confirmation）/ question / direction — 却下理由: approval（受動的同意）と confirmation（能動的実行指示）は分析価値が異なる
- **(B) thanks を独立カテゴリ化** — 却下理由: conversation の文脈内でのみ意味を持ち、トップレベルカテゴリとしては分析頻度が低い

### 2. classify_prompt() の変更方式

`PROMPT_CATEGORIES` の `conversation` エントリをサブカテゴリごとに分割し、`conversation:approval`, `conversation:confirmation` 等として登録。マッチ優先度は辞書の挿入順で制御（他カテゴリより後に配置）。

**代替案**: conversation マッチ後に2段階目の分類を行う → 却下: ロジックが複雑化し、common.py の単純なキーワードマッチ設計に合わない。

**サブカテゴリの挿入順序**: approval → confirmation → question → direction → thanks
**根拠**: 短いキーワード（「はい」「ok」）を持つ approval を先にマッチさせ、より長文のプロンプトは後続のサブカテゴリで捕捉する。

### 3. 後方互換

- `VALID_CATEGORIES` にサブカテゴリを追加しつつ、`conversation` も残す
- analyze.py で `conversation:*` をグルーピングし、合計行 + 内訳行で表示
- `conversation` ラベルのまま残る既存データも集約表示に含める

**マイグレーション不採用の理由**:
- 既存データは `reclassify.py` の LLM 再分類フローでサブカテゴリ化可能（段階的対応）
- キーワードのみの自動マイグレーションはプロンプト全文 context なしで精度が低い
- 代替案: (A) reclassify 既存フローで段階的再分類（推奨）→ 追加実装不要 / (B) マイグレーションスクリプト → 過剰

## Risks / Trade-offs

- **キーワード重複リスク**: 一部のキーワード（「はい」等）が短く、他カテゴリのプロンプトにも出現する可能性 → conversation サブカテゴリは引き続き最後にマッチさせることで軽減
- **LLM reclassify の精度**: サブカテゴリが増えることで LLM の分類精度がわずかに低下する可能性 → reclassify プロンプトにサブカテゴリの説明を追加
