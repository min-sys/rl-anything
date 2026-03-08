## MODIFIED Requirements

### Requirement: Compile ステージはパッチ生成とメモリルーティングを統合する
Compile ステージは optimize（パッチ生成 + regression gate）、remediation（audit 違反の自動修正）、reflect（corrections → メモリルーティング）を1ステージとして実行しなければならない（MUST）。

#### Scenario: corrections がある場合
- **WHEN** corrections.jsonl に未処理の corrections が存在する
- **THEN** optimize（パッチ生成）→ remediation → reflect の順に実行される

#### Scenario: corrections がない場合
- **WHEN** corrections.jsonl に未処理の corrections が存在しない
- **THEN** optimize はスキップされ、remediation → reflect のみ実行される

#### Scenario: Diagnose の診断結果を入力として受け取る
- **WHEN** Diagnose ステージが全レイヤー（Skill + Rules + Memory + Hooks + CLAUDE.md）の問題リストを出力している
- **THEN** Compile ステージはその診断結果を remediation の入力として使用する

## ADDED Requirements

### Requirement: remediation は新レイヤーの issue type を分類できる
`classify_issue()` は、全レイヤー診断由来の issue type（`orphan_rule`, `stale_rule`, `stale_memory`, `memory_duplicate`, `hooks_unconfigured`, `claudemd_phantom_ref`, `claudemd_missing_section`）に対して適切な `confidence_score` を算出しなければならない（MUST）。

#### Scenario: orphan_rule の confidence_score
- **WHEN** `orphan_rule` issue が分類される
- **THEN** `confidence_score` は 0.4〜0.6 の範囲で算出される（孤立判定は不確実性があるため）

#### Scenario: stale_rule の confidence_score
- **WHEN** `stale_rule` issue（参照先ファイルが存在しない）が分類される
- **THEN** `confidence_score` は 0.9 以上で算出される（ファイル不存在は確実）

#### Scenario: claudemd_phantom_ref の confidence_score
- **WHEN** `claudemd_phantom_ref` issue が分類される
- **THEN** `confidence_score` は 0.85 以上で算出される（スキル/ルールの実在確認は確実性が高い）

#### Scenario: stale_memory の confidence_score
- **WHEN** `stale_memory` issue が分類される
- **THEN** `confidence_score` は 0.5〜0.7 の範囲で算出される（セマンティックパターン検出の不確実性があるため）

#### Scenario: memory_duplicate の confidence_score
- **WHEN** `memory_duplicate` issue が分類される
- **THEN** `confidence_score` は 0.6〜0.8 の範囲で算出される（Jaccard 係数ベースの類似度判定の精度に依存）

#### Scenario: claudemd_missing_section の confidence_score
- **WHEN** `claudemd_missing_section` issue が分類される
- **THEN** `confidence_score` は 0.9 以上で算出される（セクション有無は確実に判定可能）

#### Scenario: hooks_unconfigured の confidence_score
- **WHEN** `hooks_unconfigured` issue が分類される
- **THEN** `confidence_score` は 0.3〜0.5 の範囲で算出される（hooks 未設定は意図的な場合もあるため）

### Requirement: remediation は新レイヤーの issue type に rationale を生成できる
`generate_rationale()` は、全レイヤー診断由来の issue type に対して日本語の修正理由テキストを生成しなければならない（MUST）。

#### Scenario: orphan_rule の rationale
- **WHEN** `orphan_rule` issue の rationale を生成する
- **THEN** 「ルール「{name}」はどのスキル・CLAUDE.md からも参照されていません。」のようなテキストが返される

#### Scenario: claudemd_phantom_ref の rationale
- **WHEN** `claudemd_phantom_ref` issue の rationale を生成する
- **THEN** 「CLAUDE.md 内で言及された{ref_type}「{name}」が存在しません。」のようなテキストが返される

#### Scenario: stale_memory の rationale
- **WHEN** `stale_memory` issue の rationale を生成する
- **THEN** 「MEMORY.md 内の「{path}」への言及は実体が見つかりません。エントリの更新または削除を検討してください。」のようなテキストが返される

#### Scenario: memory_duplicate の rationale
- **WHEN** `memory_duplicate` issue の rationale を生成する
- **THEN** 「MEMORY.md のセクション「{sections[0]}」と「{sections[1]}」は内容が重複しています（類似度: {similarity}）。統合を検討してください。」のようなテキストが返される

#### Scenario: claudemd_missing_section の rationale
- **WHEN** `claudemd_missing_section` issue の rationale を生成する
- **THEN** 「CLAUDE.md に {section} セクションがありませんが、{skill_count} 個のスキルが存在します。セクションの追加を検討してください。」のようなテキストが返される

#### Scenario: hooks_unconfigured の rationale
- **WHEN** `hooks_unconfigured` issue の rationale を生成する
- **THEN** 「hooks 設定が見つかりません。observe hooks の設定を検討してください。」のようなテキストが返される
