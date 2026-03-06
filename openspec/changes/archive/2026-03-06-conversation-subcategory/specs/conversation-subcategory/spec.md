## ADDED Requirements

### Requirement: Conversation subcategory classification（MUST）
`classify_prompt()` は conversation にマッチするプロンプトを5つのサブカテゴリ（`conversation:approval`, `conversation:confirmation`, `conversation:question`, `conversation:direction`, `conversation:thanks`）に細分化して分類しなければならない（MUST）。

#### Scenario: Approval prompt classified
- **WHEN** プロンプトが "はい" または "ok" または "いいよ" または "いいえ" を含む
- **THEN** `classify_prompt()` は `conversation:approval` を返す

#### Scenario: Confirmation prompt classified
- **WHEN** プロンプトが "お願い" または "やって" または "進めて" を含む
- **THEN** `classify_prompt()` は `conversation:confirmation` を返す

#### Scenario: Question prompt classified
- **WHEN** プロンプトが "？" または "教えて" または "なぜ" を含む
- **THEN** `classify_prompt()` は `conversation:question` を返す

#### Scenario: Direction prompt classified
- **WHEN** プロンプトが "こうして" または "やめて" または "変えて" を含む
- **THEN** `classify_prompt()` は `conversation:direction` を返す

#### Scenario: Thanks prompt classified
- **WHEN** プロンプトが "ありがと" または "感謝" または "thanks" を含む
- **THEN** `classify_prompt()` は `conversation:thanks` を返す

### Requirement: Subcategory backward compatibility（MUST）
既存の `conversation` ラベルは有効なカテゴリとして残さなければならず（MUST）、サブカテゴリに分類できないプロンプトは `conversation` のまま返す。

フォールバック発生条件:
1. LLM reclassify で `conversation`（サブカテゴリなし）が返された場合
2. 既存データの `conversation` ラベル（サブカテゴリ導入前の記録）

> **NOTE**: `classify_prompt()` では全 conversation キーワードがサブカテゴリに分配されるため、キーワードマッチではフォールバックは発生しない。フォールバックは上記2条件でのみ発生する。

#### Scenario: Unclassifiable conversation fallback
- **WHEN** プロンプトが conversation キーワードにマッチするがサブカテゴリのどれにも該当しない
- **THEN** `classify_prompt()` は `conversation` を返す

### Requirement: VALID_CATEGORIES includes subcategories（MUST）
`reclassify.py` の `VALID_CATEGORIES` は5つのサブカテゴリと既存の `conversation` の両方を含まなければならない（MUST）。

#### Scenario: LLM reclassification with subcategory
- **WHEN** LLM が "other" プロンプトを `conversation:approval` に再分類する
- **THEN** reclassify が有効なカテゴリとして受け入れる

### Requirement: Analyze aggregated display（MUST）
`analyze.py` のレポートは `conversation:*` サブカテゴリを集約表示し、合計行と内訳行の両方を出力しなければならない（MUST）。

#### Scenario: Report shows conversation breakdown
- **WHEN** usage データに `conversation:approval` が 50件、`conversation:confirmation` が 30件、`conversation` が 10件ある
- **THEN** レポートに `conversation (total): 90` と各サブカテゴリの内訳が表示される

### Requirement: Subcategory match priority（MUST）
複数サブカテゴリにマッチするプロンプトは、`PROMPT_CATEGORIES` の挿入順で最初にマッチしたサブカテゴリを返さなければならない（MUST）。

#### Scenario: Multiple subcategory match
- **WHEN** プロンプトが「はい、お願いします」で `conversation:approval` と `conversation:confirmation` の両方にマッチする
- **THEN** `classify_prompt()` は挿入順で先に登録された `conversation:approval` を返す
