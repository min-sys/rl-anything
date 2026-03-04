## ADDED Requirements

### Requirement: reflect 出力に memory_update_candidates を含めなければならない（MUST）

reflect.py の `build_output()` は corrections と既存 MEMORY エントリを照合し、既存エントリの更新が必要な候補を `memory_update_candidates` フィールドとして JSON 出力に含めなければならない（MUST）。キーワード抽出には `scripts/lib/similarity.py` の `tokenize()` を再利用する。ストップワードは `reflect.py` の定数 `_MEMORY_STOP_WORDS` で定義し、英語一般語（the, a, is, to, use, for, in, on, with, and, or, of, it, that, this）および短い技術汎用語（file, code, run, set, get, add）を含める。マッチ閾値は定数 `MIN_KEYWORD_MATCH`（デフォルト 3）で定義する。

#### Scenario: corrections が既存 MEMORY エントリと関連する

- **WHEN** correction に "bun を使う" という message があり、MEMORY.md に "npm でパッケージ管理" というエントリがある
- **THEN** memory_update_candidates に correction_message、memory_file、memory_line、suggested_action: "update" を含む候補が出力される

#### Scenario: corrections と MEMORY に関連なし

- **WHEN** correction の message が MEMORY の全エントリとキーワードマッチしない
- **THEN** memory_update_candidates は空配列となる

#### Scenario: duplicate_found の correction は除外

- **WHEN** correction に `duplicate_found: true` が設定されている
- **THEN** その correction は memory_update_candidates の照合対象から除外される

#### Scenario: MIN_KEYWORD_MATCH 未満のマッチは候補にしない

- **WHEN** correction と MEMORY エントリの共通キーワード（ストップワード除外後）が `MIN_KEYWORD_MATCH`（デフォルト 3）未満
- **THEN** memory_update_candidates の候補にはならない

### Requirement: SKILL.md で memory_update_candidates を対話表示しなければならない（MUST）

reflect の SKILL.md は promotion_candidates 表示の後に memory_update_candidates を「MEMORY 更新候補」として一覧表示しなければならない（MUST）。更新の実行はユーザー判断に委ねる。

#### Scenario: memory_update_candidates がある場合の表示

- **WHEN** reflect 出力に memory_update_candidates が 2件ある
- **THEN** SKILL.md の手順に従い「MEMORY 更新候補」セクションとして各候補の correction_message、memory_file、memory_line を表示する

#### Scenario: memory_update_candidates が空の場合

- **WHEN** reflect 出力の memory_update_candidates が空配列である
- **THEN** 「MEMORY 更新候補」セクションは表示しない
