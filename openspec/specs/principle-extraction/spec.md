## ADDED Requirements

### Requirement: Principle extraction from CLAUDE.md and Rules
`principles.py` の `extract_principles()` は CLAUDE.md と Rules ファイルを入力として、`claude -p` 経由で LLM に PJ 固有の原則リストを抽出させなければならない（MUST）。各原則は `id`（kebab-case）、`text`（原則の記述）、`source`（抽出元ファイルパス）、`category`（quality/safety/performance/convention のいずれか）を含まなければならない（MUST）。

#### Scenario: CLAUDE.md から原則を抽出
- **WHEN** CLAUDE.md に「LLMコール最小化」「べき等性保証」「ユーザー承認なしに変更しない」が記述されている
- **THEN** 少なくとも 3 つの原則が抽出され、各原則に id, text, source, category が含まれる

#### Scenario: Rules からも原則を抽出
- **WHEN** `.claude/rules/commit-version.md` に「version bump 要否を確認」が記述されている
- **THEN** 該当 Rule から原則が抽出され、source にルールファイルのパスが含まれる

### Requirement: Seed principles
`extract_principles()` は LLM 抽出結果に加え、5つの普遍的シード原則をデフォルトで含めなければならない（MUST）。シード原則は `"seed": true` フラグを持ち、`--refresh` 時にも常に含まれなければならない（MUST）。

シード原則:
1. `single-responsibility` — 各スキル/ルールは単一の責務を持つ
2. `graceful-degradation` — 外部依存の失敗時にフォールバックする
3. `user-consent` — 破壊的操作の前にユーザー確認を取る
4. `idempotency` — 同じ操作の繰り返しで副作用が増大しない
5. `minimal-llm-cost` — LLM 呼び出しを最小化する

#### Scenario: CLAUDE.md が空でもシード原則が利用可能
- **WHEN** CLAUDE.md が存在しない、または内容が空である
- **THEN** 5つのシード原則が返され、各原則に `"seed": true` が含まれる

#### Scenario: LLM 抽出原則とシード原則のマージ
- **WHEN** LLM が 3 つの原則を抽出する
- **THEN** シード原則 5 + LLM 抽出 3 = 計 8 原則が返される（重複する場合は LLM 抽出が優先）

### Requirement: Principle quality scoring
`extract_principles()` は各抽出原則の品質を specificity（具体性: 0.0-1.0）と testability（検証可能性: 0.0-1.0）で評価しなければならない（MUST）。品質スコアが `THRESHOLDS["min_principle_quality"]`（デフォルト 0.3）未満の原則は Constitutional eval から除外しなければならない（MUST）。品質スコアは LLM 抽出と同一の呼び出し内で算出する（追加 LLM コストなし）。

#### Scenario: 高品質原則の通過
- **WHEN** 原則「Skill 内で claude -p を使用してはならない」が抽出される
- **THEN** specificity >= 0.7, testability >= 0.7 で品質スコアが閾値を超え、Constitutional eval に含まれる

#### Scenario: 低品質原則の除外
- **WHEN** 原則「コードはきれいに書く」が抽出される
- **THEN** specificity < 0.3 で品質スコアが閾値未満となり、`excluded_low_quality` リストに含まれる

#### Scenario: シード原則は品質チェックをバイパス
- **WHEN** シード原則が品質スコア評価される
- **THEN** シード原則は品質チェックを常にパスし、除外されない

### Requirement: Principle caching
`extract_principles()` の結果は `.claude/principles.json` にキャッシュしなければならない（MUST）。キャッシュが存在する場合は LLM を呼ばずにキャッシュを返さなければならない（MUST）。`--refresh` フラグでキャッシュを再生成できなければならない（MUST）。

#### Scenario: キャッシュ存在時は LLM を呼ばない
- **WHEN** `.claude/principles.json` が存在し、`--refresh` が指定されていない
- **THEN** `claude -p` を呼ばず、キャッシュされた原則リストを返す

#### Scenario: --refresh でキャッシュ再生成
- **WHEN** `--refresh` フラグが指定された
- **THEN** 既存キャッシュを無視して LLM で再抽出し、`.claude/principles.json` を上書きする

### Requirement: Cache staleness detection
`.claude/principles.json` に CLAUDE.md + Rules 全ファイルのコンテンツハッシュ（SHA-256）を `source_hash` として保存しなければならない（MUST）。キャッシュロード時にハッシュが不一致の場合、`stale_cache: true` を返却 dict に含めなければならない（MUST）。LLM は呼ばず、キャッシュされた原則をそのまま返す（コストゼロ）。

#### Scenario: ソースファイル変更によるキャッシュ陳腐化検出
- **WHEN** `.claude/principles.json` が存在し、キャッシュ後に CLAUDE.md が編集された
- **THEN** ハッシュ不一致により `stale_cache: true` が返却に含まれ、キャッシュされた原則がそのまま返される

#### Scenario: ソースファイル未変更時
- **WHEN** `.claude/principles.json` が存在し、CLAUDE.md と Rules が未変更
- **THEN** `stale_cache: false` が返却に含まれる

### Requirement: User-editable principles
`.claude/principles.json` はユーザーが手動編集可能な JSON フォーマットでなければならない（MUST）。ユーザーが追加した原則（`"user_defined": true`）は `--refresh` 時にも保持されなければならない（MUST）。

#### Scenario: ユーザー定義原則の保持
- **WHEN** `.claude/principles.json` に `"user_defined": true` の原則が含まれ、`--refresh` が実行される
- **THEN** LLM 再抽出後の結果にユーザー定義原則がマージされて保持される

### Requirement: Graceful fallback when LLM unavailable
LLM 呼び出しが失敗した場合、`extract_principles()` はシード原則のみを返さなければならない（MUST）。例外を発生させてはならない（MUST NOT）。警告メッセージを stderr に出力しなければならない（MUST）。

#### Scenario: LLM 呼び出し失敗時
- **WHEN** `claude -p` がタイムアウトまたはエラーで失敗する
- **THEN** シード原則 5 件が返され、stderr に警告が出力される
