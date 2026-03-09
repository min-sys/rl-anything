## ADDED Requirements

### Requirement: ファイル位置基準の相対パス解決を行う

stale_ref および stale_rule 判定時、プロジェクトルート基準で `Path.exists()` が失敗した場合、参照元ファイルの親ディレクトリ基準でもパス解決を試みなければならない（MUST）。両方で存在しない場合のみ stale_ref / stale_rule とする。

#### Scenario: スキル内の相対パスがスキルディレクトリ基準で存在する（stale_ref）
- **WHEN** `.claude/skills/evolve/SKILL.md` 内に `references/docs-map.md` という参照があり、`.claude/skills/evolve/references/docs-map.md` が存在する
- **THEN** stale_ref として検出されない

#### Scenario: プロジェクトルート基準でのみ存在するパスは正常
- **WHEN** `CLAUDE.md` 内に `scripts/lib/layer_diagnose.py` という参照があり、プロジェクトルートからそのパスが存在する
- **THEN** stale_ref として検出されない

#### Scenario: どちらの基準でも存在しないパスは stale_ref
- **WHEN** ファイル内に `nonexistent/path.py` という参照があり、プロジェクトルート基準でもファイル位置基準でも存在しない
- **THEN** stale_ref として検出される

#### Scenario: ルールファイル内の相対パスがルールディレクトリ基準で存在する（stale_rule）
- **WHEN** `.claude/rules/my-rule.md` 内に `references/policy.md` という参照があり、`.claude/rules/references/policy.md` が存在する
- **THEN** stale_rule として検出されない

### Requirement: プロジェクトに存在しないトップレベルディレクトリへの参照を除外する

パス候補の最初のセグメントがプロジェクトルートに存在しないディレクトリであり、かつ KNOWN_DIR_PREFIXES にも含まれない場合、stale_ref 候補から除外しなければならない（MUST）。外部リポジトリのファイル参照（`src/github/token.ts` 等）の FP を防ぐ。

#### Scenario: プロジェクトに src/ がない場合の外部参照は除外される
- **WHEN** テキスト内に `src/github/token.ts` があるが、プロジェクトルートに `src/` ディレクトリが存在しない
- **THEN** stale_ref として検出されない

#### Scenario: プロジェクトに存在するディレクトリへの参照は通常通り検証
- **WHEN** テキスト内に `scripts/nonexistent.py` があり、プロジェクトルートに `scripts/` ディレクトリが存在する
- **THEN** 通常の stale_ref 検証が行われる
