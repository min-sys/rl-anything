# memory-semantic-audit Specification

## Purpose
audit 実行時に MEMORY（auto-memory / global CLAUDE.md）の各セクションをコードベース・OpenSpec archive と LLM で突合し、整合性レポート（CONSISTENT / MISLEADING / STALE の3段階判定）を出力する。

## Requirements
### Requirement: audit.py は MEMORY セクションの検証用コンテキストを構造化出力しなければならない（MUST）

`build_memory_verification_context(project_dir)` は、MEMORY の各セクション（`## ` 見出し単位）を分割し、各セクションのキーワードでコードベースを grep した結果（関連ファイルのスニペット）と、OpenSpec archive でのメンション情報を収集して JSON 形式で出力しなければならない（MUST）。

対象 MEMORY:
- project auto-memory（`~/.claude/projects/<encoded>/memory/*.md`）
- global memory（`~/.claude/CLAUDE.md`）— PJ 固有の記述を含むセクションのみ

セクションの分割は `## ` プレフィックスの行を境界とする。見出しのないファイル先頭部分は `_header` セクションとして扱う。

キーワード抽出では一般的なストップワード（冠詞、前置詞、助動詞等）と短すぎる単語（2文字以下）を除外しなければならない（MUST）。

#### Scenario: project auto-memory のセクション分割と証拠収集

- **WHEN** MEMORY.md に `## doc-ci-cd-pipeline` セクションがあり、その中に `full-regen` `差分更新` `force_all` というキーワードが含まれる
- **THEN** 出力 JSON の `sections` 配列に `heading: "doc-ci-cd-pipeline"` のエントリが含まれ、`codebase_evidence` にコードベースから `full-regen` を含むファイルのスニペットが含まれる

#### Scenario: OpenSpec archive メンションの収集

- **WHEN** `openspec/changes/archive/` 配下に `optimize-fullregen-cost` というアーカイブがあり、MEMORY セクションのキーワード `fullregen` とマッチする
- **THEN** 出力 JSON の該当セクションの `archive_mentions` に `"optimize-fullregen-cost"` が含まれる

#### Scenario: global memory の PJ 固有セクション検出

- **WHEN** `~/.claude/CLAUDE.md` に `## docs-platform` セクションがあり、現在の PJ が docs-platform である
- **THEN** 出力 JSON の `sections` 配列に global memory の該当セクションが含まれる

#### Scenario: global memory の汎用セクションは除外

- **WHEN** `~/.claude/CLAUDE.md` に `## コーディング規約` という汎用セクションがある
- **THEN** 出力 JSON の `sections` 配列にこのセクションは含まれない

#### Scenario: 読み取りエラー時のスキップ

- **WHEN** MEMORY ファイルの読み取りで OSError が発生する
- **THEN** エラーを stderr に警告出力し、そのファイルをスキップして処理を継続する

### Requirement: SKILL.md の検証ステップは3段階判定で結果を表示しなければならない（MUST）

audit SKILL.md の LLM 検証ステップで、`build_memory_verification_context()` の出力をもとに Claude Code 自身が各セクションを検証し、以下の3段階で判定を表示しなければならない（MUST）:

- **CONSISTENT**: コードベースと整合。変更不要
- **MISLEADING**: 正確だが誤解を招く表現。書き換え案を提示
- **STALE**: コードベースと矛盾。更新/削除を推奨

判定結果はセクションごとに表示し、MISLEADING と STALE には具体的な修正提案を含めなければならない（MUST）。

#### Scenario: CONSISTENT 判定

- **WHEN** MEMORY の `## チーム運用の教訓` セクションの内容がコードベースの実態と矛盾せず、誤解を招く表現もない
- **THEN** 判定結果に `CONSISTENT` と表示し、修正提案は表示しない

#### Scenario: MISLEADING 判定

- **WHEN** MEMORY に `full-regen は差分更新済み...force_all: true で手動フルリジェネも可能` と記載されており、コードベースでは差分更新がデフォルトである
- **THEN** 判定結果に `MISLEADING` と表示し、「デフォルトは差分更新であることを冒頭に明記すべき」等の書き換え案を提示する

#### Scenario: STALE 判定

- **WHEN** MEMORY に `npm を使用` と記載されているが、コードベースでは bun に移行済みである
- **THEN** 判定結果に `STALE` と表示し、「bun に更新すべき」という修正提案を表示する

#### Scenario: 検証対象セクションが0件の場合

- **WHEN** auto-memory が空で global memory に PJ 固有セクションがない
- **THEN** 「検証対象の MEMORY セクションがありません」と表示し、検証ステップをスキップする
