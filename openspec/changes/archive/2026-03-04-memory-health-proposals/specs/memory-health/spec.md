## ADDED Requirements

### Requirement: audit レポートに Memory Health セクションを含めなければならない（MUST）

audit.py の `generate_report()` は MEMORY ファイル（プロジェクトローカル `project_dir/.claude/memory/` および auto-memory `~/.claude/projects/<encoded>/memory/`）の内容を分析し、陳腐化参照・肥大化警告・改善提案を含む "## Memory Health" セクションをレポートに出力しなければならない（MUST）。auto-memory ファイルの探索には `reflect_utils.read_auto_memory()` を利用する。

#### Scenario: 陳腐化参照の検出

- **WHEN** MEMORY.md に `skills/update/` というパス参照があり、そのディレクトリがディスク上に存在しない
- **THEN** Memory Health セクションの "Stale References" に該当ファイルと行番号とパスが表示される

#### Scenario: 複数ファイルの陳腐化参照

- **WHEN** MEMORY.md に存在しないパスが 1件、debugging.md に存在しないパスが 1件ある
- **THEN** Memory Health セクションに 2件の Stale References が表示される

#### Scenario: コードブロック内のパスは除外

- **WHEN** MEMORY.md のコードブロック（``` ``` ）内に存在しないパス `/fake/example/path` がある
- **THEN** そのパスは Stale References に含まれない

#### Scenario: 陳腐化参照なし

- **WHEN** MEMORY ファイル内の全パス参照がディスク上に存在する
- **THEN** "Stale References" サブセクションは表示されない

#### Scenario: auto-memory ファイルの検査

- **WHEN** auto-memory パス（`~/.claude/projects/<encoded>/memory/`）に MEMORY.md が存在し、陳腐化参照がある
- **THEN** プロジェクトローカル memory と同様に Stale References として検出される

#### Scenario: MEMORY ファイルの読み取りエラー

- **WHEN** MEMORY ファイルの読み取りに失敗した場合（権限エラー、エンコーディングエラー等）
- **THEN** そのファイルをスキップし stderr に警告を出力する（SHALL）

### Requirement: MEMORY.md の肥大化を早期警告しなければならない（MUST）

MEMORY.md が行数上限の `NEAR_LIMIT_RATIO`（定数、デフォルト 0.8）以上に達した場合、"Near Limit" として警告し、トピックファイルへの分離を提案しなければならない（MUST）。閾値はハードコードせず `audit.py` の定数 `NEAR_LIMIT_RATIO` で定義する。

#### Scenario: NEAR_LIMIT_RATIO 超過の警告

- **WHEN** MEMORY.md が 180行（上限200行の90%、NEAR_LIMIT_RATIO=0.8 を超過）である
- **THEN** Memory Health セクションに "Near Limit" 警告と行数・パーセンテージが表示される

#### Scenario: NEAR_LIMIT_RATIO 未満の正常

- **WHEN** MEMORY.md が 100行（上限200行の50%、NEAR_LIMIT_RATIO=0.8 未満）である
- **THEN** "Near Limit" 警告は表示されない

#### Scenario: トピックファイルへの分離提案

- **WHEN** MEMORY.md が NEAR_LIMIT_RATIO 以上で Near Limit 警告が出る
- **THEN** Suggestions に「Split large MEMORY.md entries into topic files」が含まれる

### Requirement: Memory Health セクションに問題がない場合は非表示にしなければならない（MUST）

陳腐化参照なし・肥大化警告なしの場合、Memory Health セクション自体をレポートに含めてはならない（MUST NOT）。

#### Scenario: 問題なし

- **WHEN** MEMORY ファイルに陳腐化参照がなく、行数が NEAR_LIMIT_RATIO 未満である
- **THEN** レポートに "## Memory Health" セクションは含まれない
