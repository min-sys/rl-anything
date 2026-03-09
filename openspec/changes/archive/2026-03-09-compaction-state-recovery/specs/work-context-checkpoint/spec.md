## ADDED Requirements

### Requirement: CLAUDE.md に Compaction Instructions セクションが存在する
CLAUDE.md に `## Compaction Instructions` セクションを追加し、コンパクション時にサマリーに保持すべき情報を SHALL 明示する。以下の項目を含む:
- 完了済みタスクと未完了タスクの区別
- 呼び出されたスキルの実行結果（完了/未完了）
- 変更したファイルの一覧
- ユーザーの最後の指示

#### Scenario: CLAUDE.md に Compaction Instructions セクションが含まれている
- **WHEN** CLAUDE.md を読み込む
- **THEN** `## Compaction Instructions` セクションが存在し、上記4項目が記載されている

### Requirement: PreCompact hook が作業コンテキストを保存する
`save_state.py` の PreCompact hook は、既存の evolve_state/corrections_snapshot に加えて、作業コンテキスト（`work_context`）を checkpoint.json に SHALL 保存する。`work_context` には以下を含む:
- `recent_commits`: `git log --oneline -5` で取得した直近5コミット
- `uncommitted_files`: `git status --short` で取得した未コミット変更ファイル一覧（最大30件）
- `git_branch`: 現在のブランチ名

定数 `_MAX_UNCOMMITTED_FILES=30`, `_MAX_RECENT_COMMITS=5`, `_GIT_TIMEOUT_SECONDS=2` を `save_state.py` モジュール先頭に定義する。

#### Scenario: PreCompact 時に作業コンテキストが保存される
- **WHEN** PreCompact イベントが発火する
- **THEN** checkpoint.json に `work_context` フィールドが含まれ、`recent_commits`、`uncommitted_files`、`git_branch` が記録されている

#### Scenario: git コマンドの失敗時にも保存が完了する
- **WHEN** git コマンドがエラーを返す（git リポジトリ外など）
- **THEN** `work_context` の該当フィールドは空文字列または空リストとなり、checkpoint.json の保存自体は SHALL 成功する

#### Scenario: uncommitted_files が30件を超える場合
- **WHEN** `git status --short` の結果が30件を超える
- **THEN** 先頭30件のみが `uncommitted_files` に保存される

### Requirement: SessionStart hook が作業コンテキストを復元する
`restore_state.py` の SessionStart hook は、checkpoint.json に `work_context` が存在する場合、committed（完了）と uncommitted（作業中）を分離した人間可読サマリーを stdout に SHALL 出力する。

#### Scenario: 作業コンテキスト付き checkpoint の復元
- **WHEN** checkpoint.json に `work_context` フィールドが存在する状態で SessionStart が発火する
- **THEN** stdout に `[rl-anything:restore_state]` プレフィックス付きで、ブランチ名・完了コミット一覧・作業中ファイル一覧を区別したサマリーが出力される

#### Scenario: work_context なしの checkpoint の復元（後方互換）
- **WHEN** checkpoint.json に `work_context` フィールドが存在しない状態で SessionStart が発火する
- **THEN** 既存の動作（JSON 出力のみ）が維持され、エラーは発生しない

### Requirement: hook の実行時間が timeout 内に収まる
save_state.py / restore_state.py の実行は 5000ms の timeout 内に SHALL 完了する。git コマンドの subprocess 呼び出しには個別に `_GIT_TIMEOUT_SECONDS`（2s）の timeout を設定する。全 git コマンドの合計実行時間が 3.5s を超過した場合、残りのコマンドを skip する。

#### Scenario: 正常な git リポジトリでの実行時間
- **WHEN** 通常サイズの git リポジトリ（10000ファイル以下）で PreCompact/SessionStart が発火する
- **THEN** 処理が 2000ms 以内に完了する

#### Scenario: git コマンドの個別 timeout
- **WHEN** git コマンドが `_GIT_TIMEOUT_SECONDS`（2s）以内に応答しない
- **THEN** subprocess が timeout で終了し、該当フィールドはデフォルト値となる

#### Scenario: 合計 timeout ガード
- **WHEN** git コマンドの合計実行時間が 3.5s を超過する
- **THEN** 残りの git コマンドは skip され、取得済みのフィールドのみで `work_context` が構成される
